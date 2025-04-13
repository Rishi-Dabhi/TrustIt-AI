"""
Portia integration for TrustIt-AI fact-checking workflow.
Implements the fact-checking pipeline using Portia's multi-agent planning and execution.
"""

import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import re
import yaml
import pusher
import json
import uuid
import time

from portia import (
    Config,
    LLMModel,
    LLMProvider,
    Portia,
    example_tool_registry,
    ExecutionContext
)

# Import existing agents/services to reuse their functionality
from .agents import QuestionGeneratorAgent, FactCheckingAgent, JudgeAgent
from .tools import TavilySearchTool

# ------ Pusher Integration ------
class PusherClient:
    """Client for streaming real-time updates via Pusher"""
    
    def __init__(self, config):
        self.enabled = config.get("enable_pusher", True)
        
        if self.enabled:
            try:
                self.client = pusher.Pusher(
                    app_id=config.get("pusher_app_id", "1973936"),
                    key=config.get("pusher_key", "4cdf071584bc2fb15aa8"),
                    secret=config.get("pusher_secret", "0ac70eebeef0516264fe"),
                    cluster=config.get("pusher_cluster", "eu"),
                    ssl=True
                )
            except Exception as e:
                import logging
                logging.error(f"Failed to initialize Pusher: {e}")
                self.enabled = False
    
    def send_update(self, session_id, event_type, data):
        """Send an update to the client via Pusher"""
        if not self.enabled:
            return
            
        try:
            self.client.trigger(
                f'fact-check-{session_id}',
                event_type,
                data
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send Pusher update: {e}")

# ------ Custom Tool Definitions ------

class QuestionGeneratorArgs(BaseModel):
    """Arguments for question generation tool"""
    content: str = Field(description="The content to generate questions about")
    num_questions: int = Field(description="Number of questions to generate", default=3)

class FactCheckArgs(BaseModel):
    """Arguments for fact checking tool"""
    question: str = Field(description="The question to fact check")
    content: str = Field(description="The original content being fact-checked")

class JudgmentArgs(BaseModel):
    """Arguments for judgment tool"""
    fact_checks: List[Dict[str, Any]] = Field(description="List of fact check results to judge")

# ------ Tool Implementations ------

class QuestionGeneratorTool:
    """Tool to generate questions for fact-checking"""
    
    def __init__(self, config):
        self.args_schema = QuestionGeneratorArgs
        self.id = "question_generator"
        self.name = "Question Generator"
        self.description = "Generates specific questions to fact-check content"
        self.output_schema = ("list", "list of generated questions")
        self.should_summarize = False
        self.question_generator = QuestionGeneratorAgent(config)
    
    def run(self, args=None, **kwargs):
        """Generate questions from content"""
        if args and hasattr(args, 'content'):
            content = args.content
            num_questions = getattr(args, 'num_questions', 3)
        else:
            content = kwargs.get("content", "")
            num_questions = kwargs.get("num_questions", 3)
        
        questions = self.question_generator.generate_questions(
            initial_query=content, 
            num_questions=num_questions
        )
        
        # Handle "not enough context" case
        if questions == ["not enough context"]:
            return questions
        
        return questions

class FactCheckTool:
    """Tool to check facts based on questions"""
    
    def __init__(self, config):
        self.args_schema = FactCheckArgs
        self.id = "fact_checker"
        self.name = "Fact Checker"
        self.description = "Checks factual claims by searching for evidence"
        self.output_schema = ("dict", "fact checking results")
        self.should_summarize = True
        self.fact_checker = FactCheckingAgent(config)
    
    def run(self, args=None, **kwargs):
        """Run fact checking on a question"""
        import asyncio
        
        if args and hasattr(args, 'question'):
            question = args.question
            content = getattr(args, 'content', "")
        else:
            question = kwargs.get("question", "")
            content = kwargs.get("content", "")
        
        # Prepare input data in format expected by fact_checker
        input_data = {
            "questions": [{"question": question}],
            "content": content,
            "metadata": {"timestamp": "2024-03-20T12:00:00Z"}
        }
        
        # Process the fact checking - use asyncio.run to handle the async call synchronously
        try:
            # Create a new event loop for this call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async function and get the result
            result = loop.run_until_complete(self.fact_checker.process(input_data))
            loop.close()
            
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

class JudgmentTool:
    """Tool to make a judgment based on fact checks"""
    
    def __init__(self, config):
        self.args_schema = JudgmentArgs
        self.id = "judge"
        self.name = "Judge"
        self.description = "Makes a final judgment based on fact check results"
        self.output_schema = ("dict", "judgment result")
        self.should_summarize = True
        self.judge = JudgeAgent(config)
    
    def run(self, args=None, **kwargs):
        """Make judgment based on fact check results"""
        if args and hasattr(args, 'fact_checks'):
            fact_checks = args.fact_checks
        else:
            fact_checks = kwargs.get("fact_checks", [])
        
        judgment = self.judge.judge(fact_checks)
        return judgment

# ------ Portia Integration ------

class PortiaFactChecker:
    """Main class for Portia-based fact checking"""
    
    def __init__(self, config):
        self.config = config
        # Initialize agents directly, Portia will only be used for question generation planning
        self.question_generator_agent = QuestionGeneratorAgent(config)
        self.fact_checking_agent = FactCheckingAgent(config)
        self.judge_agent = JudgeAgent(config)
        self._initialize_portia_for_questions() # Renamed initialization
        self.pusher = PusherClient(config)
    
    def _initialize_portia_for_questions(self):
        """Initialize Portia with only the QuestionGeneratorTool for planning"""
        portia_config = Config.from_default(
            llm_provider=LLMProvider.GOOGLE_GENERATIVE_AI,
            llm_model_name=LLMModel.GEMINI_2_0_FLASH,
            google_api_key=self.config["google_api_key"]
        )
        
        # Try to register callbacks to monitor Portia's execution flow if supported
        try:
            # Check if callback registration is supported
            if hasattr(portia_config, "register_exec_callback"):
                portia_config.register_exec_callback("pre_generate_plan", self._on_plan_generation_start)
                portia_config.register_exec_callback("post_generate_plan", self._on_plan_generation_complete)
                portia_config.register_exec_callback("pre_run_step", self._on_step_execution_start)
                portia_config.register_exec_callback("post_run_step", self._on_step_execution_complete)
                portia_config.register_exec_callback("pre_run_plan", self._on_plan_execution_start)
                portia_config.register_exec_callback("post_run_plan", self._on_plan_execution_complete)
                self.callbacks_enabled = True
            else:
                import logging
                logging.warning("Portia SDK version doesn't support execution callbacks. Using manual status updates instead.")
                self.callbacks_enabled = False
        except Exception as e:
            import logging
            logging.warning(f"Failed to register Portia callbacks: {e}")
            self.callbacks_enabled = False
        
        # Load portia_agent personality
        try:
            personality_path = "backend/config/personalities/portia_agent.yaml"
            with open(personality_path, "r") as f:
                self.personality = yaml.safe_load(f)
        except Exception as e:
            import logging
            logging.warning(f"Failed to load portia_agent personality: {e}")
            self.personality = None
        
        # Only include Question Generator tool for Portia planning phase
        tools = [
            QuestionGeneratorTool(self.config) 
        ]
        
        # Create Portia instance configured only for question generation planning
        self.portia_planner = Portia(config=portia_config, tools=tools)
        
    # Portia execution callbacks
    def _on_plan_generation_start(self, ctx, *args, **kwargs):
        """Called when Portia starts generating a plan"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': 'Analyzing content and deciding on strategy',
                'detail': 'Portia is reasoning about how to approach the fact-checking task',
                'operation': 'reasoning',
                'stage': 'planning',
                'progress': 17
            })
    
    def _on_plan_generation_complete(self, ctx, plan, *args, **kwargs):
        """Called when Portia completes plan generation"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            # Extract steps and tool selections from the plan
            steps = []
            tools = set()
            
            if hasattr(plan, 'steps'):
                for step in plan.steps:
                    steps.append(step.description if hasattr(step, 'description') else str(step))
                    if hasattr(step, 'tool_name') and step.tool_name:
                        tools.add(step.tool_name)
            
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': 'Created a detailed execution plan',
                'detail': f'Planned {len(steps)} steps using {len(tools)} tools',
                'operation': 'planning_complete',
                'tools_selected': list(tools),
                'steps_planned': steps[:5],  # Include first 5 steps for brevity
                'stage': 'planning',
                'progress': 22
            })
    
    def _on_plan_execution_start(self, ctx, plan, *args, **kwargs):
        """Called when Portia starts executing a plan"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': 'Starting question generation execution',
                'detail': 'Portia is beginning to follow the plan to generate factual questions',
                'operation': 'execution_start',
                'stage': 'processing',
                'progress': 25
            })
    
    def _on_step_execution_start(self, ctx, step, *args, **kwargs):
        """Called when Portia starts executing a step"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            step_desc = step.description if hasattr(step, 'description') else str(step)
            tool_name = step.tool_name if hasattr(step, 'tool_name') else "unknown tool"
            
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': f'Using {tool_name} tool',
                'detail': f'Executing step: {step_desc}',
                'operation': 'using_tool',
                'tool': tool_name,
                'step': step_desc,
                'stage': 'tool_execution',
                'progress': 28
            })
    
    def _on_step_execution_complete(self, ctx, step, output, *args, **kwargs):
        """Called when Portia completes executing a step"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            step_desc = step.description if hasattr(step, 'description') else str(step)
            tool_name = step.tool_name if hasattr(step, 'tool_name') else "unknown tool"
            
            # Try to get a reasonable output summary
            output_summary = str(output)
            if hasattr(output, 'get_value'):
                try:
                    value = output.get_value()
                    if isinstance(value, list) and len(value) > 0:
                        output_summary = f"Generated {len(value)} items"
                    elif isinstance(value, str):
                        output_summary = f"{value[:50]}..." if len(value) > 50 else value
                except:
                    pass
            
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': f'Completed task with {tool_name}',
                'detail': f'Result: {output_summary}',
                'operation': 'tool_result',
                'tool': tool_name,
                'step': step_desc,
                'stage': 'processing',
                'progress': 32
            })
    
    def _on_plan_execution_complete(self, ctx, result, *args, **kwargs):
        """Called when Portia completes executing a plan"""
        if hasattr(self, 'current_session_id') and self.current_session_id:
            # Try to get a summary of the result
            status = result.state if hasattr(result, 'state') else "Unknown"
            
            self.pusher.send_update(self.current_session_id, 'portia_internal', {
                'message': 'Planning execution complete',
                'detail': f'Status: {status}',
                'operation': 'execution_complete',
                'status': status,
                'stage': 'processing',
                'progress': 35
            })
    
    def _clean_verification_status(self, status):
        """Remove prefix from verification status and normalize the value."""
        if not status:
            return "UNCERTAIN"
        
        # Remove "Verification Status: " prefix if present
        if "Verification Status:" in status:
            status = status.split("Verification Status:", 1)[1].strip()
        
        # Normalize values to expected formats
        status_mapping = {
            "verified": "VERIFIED",
            "true": "VERIFIED",
            "correct": "VERIFIED",
            "accurate": "VERIFIED",
            "confirmed": "VERIFIED",
            "real": "VERIFIED",
            
            "partially true": "PARTIALLY TRUE",
            "partially false": "PARTIALLY TRUE",
            
            "false": "FALSE",
            "incorrect": "FALSE",
            "untrue": "FALSE",
            "misleading": "MISLEADING",
            "fake": "FALSE",
            
            "unsubstantiated": "UNCERTAIN",
            "uncertain": "UNCERTAIN",
            "unknown": "UNCERTAIN",
            "unable to verify": "UNCERTAIN",
            "insufficient evidence": "UNCERTAIN",
            "unclear": "UNCERTAIN",
            "ambiguous": "UNCERTAIN"
        }
        
        return status_mapping.get(status.lower(), status.upper())
    
    async def process_content(self, content: str, session_id: str = None) -> Dict[str, Any]:
        """Process content through fact-checking pipeline: QGen (Portia Plan) -> FactCheck (Manual Loop) -> Judge (Manual Call)"""
        import logging
        import asyncio

        # Generate a session ID if none is provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Store the session ID for callbacks
        self.current_session_id = session_id
            
        try:
            # Send initial status update
            self.pusher.send_update(session_id, 'process_started', {
                'status': 'started',
                'message': 'Starting fact-checking process',
                'detail': 'Initializing Portia multi-agent system',
                'stage': 'initialization',
                'timestamp': time.time()
            })

            # === Step 1: Generate Questions using Portia Planner ===
            logging.info("Step 1: Generating questions using Portia Planner...")
            # Update status
            self.pusher.send_update(session_id, 'status_update', {
                'status': 'in_progress',
                'message': 'Generating questions to fact check',
                'detail': 'Analyzing content for factual claims',
                'stage': 'question_generation',
                'progress': 10
            })
            
            # Prompt focused only on question generation or "not enough context"
            question_prompt = (
                f"First, critically evaluate the following content: '{content}'.\n"
                f"STEP 1: Determine if this content contains ANY factual claims or assertions that could potentially be misinformation or disinformation. A factual claim is any statement presented as fact rather than opinion, even if subtle or implied.\n\n"
                f"If the content contains NO factual claims whatsoever (e.g., it's purely opinion, a personal question, hypothetical scenario, or just requesting information), OR if it already only contains 'not enough context', respond ONLY with: 'not enough context'.\n\n" 
                f"STEP 2: If the content DOES contain factual claims, identify the most important claims that would need verification to determine if the content contains misinformation.\n\n"
                f"STEP 3: Generate exactly 3 specific, direct questions that would help determine if the content contains misinformation. These questions should:\n"
                f"- Target the key factual claims present in the content\n"
                f"- Be phrased neutrally to avoid search bias\n"
                f"- Focus on verifiable aspects (dates, statistics, events, relationships between entities)\n"
                f"- Help establish the overall truthfulness of the content\n\n"
                f"Return ONLY the generated questions without any numbering, commentary, or explanation. Each question should be on a new line."
            )
            
            # Share with frontend that planning has started
            self.pusher.send_update(session_id, 'portia_planning', {
                'message': 'Planning question generation strategy',
                'detail': 'Portia is identifying factual claims and designing verification questions',
                'stage': 'planning',
                'progress': 15
            })
            
            # If callbacks aren't available, send simulated internal updates
            if not getattr(self, 'callbacks_enabled', False):
                # Simulate reasoning update
                self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Analyzing content and deciding on strategy',
                    'detail': 'Portia is reasoning about how to approach the fact-checking task',
                    'operation': 'reasoning',
                    'stage': 'planning',
                    'progress': 17
                })
                
                # Small delay to make updates more natural
                await asyncio.sleep(0.5)
            
            # Generate and run the plan for question generation
            plan = self.portia_planner.plan(query=question_prompt)
            
            # Share the plan with frontend
            self.pusher.send_update(session_id, 'portia_plan_created', {
                'message': 'Question generation plan created',
                'detail': 'Portia has created a sequence of steps to generate verification questions',
                'plan': str(plan),
                'stage': 'plan_execution',
                'progress': 25
            })
            
            # If callbacks aren't available, send more simulated updates
            if not getattr(self, 'callbacks_enabled', False):
                # Simulate tool selection
                self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Using Question Generator tool',
                    'detail': 'Executing steps to extract factual claims and generate targeted questions',
                    'operation': 'using_tool',
                    'tool': 'Question Generator',
                    'stage': 'tool_execution',
                    'progress': 28
                })
                
                # Small delay to make updates more natural
                await asyncio.sleep(0.5)
            
            # Execute plan with progress updates
            result = self.portia_planner.run_plan(plan)
            
            # If callbacks aren't available, send completion update
            if not getattr(self, 'callbacks_enabled', False):
                # Simulate execution completion
                self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Completed question generation',
                    'detail': 'Successfully extracted key factual claims and generated verification questions',
                    'operation': 'tool_result',
                    'tool': 'Question Generator',
                    'stage': 'processing',
                    'progress': 32
                })
            
            # Update on plan completion
            self.pusher.send_update(session_id, 'portia_plan_complete', {
                'message': 'Question generation complete',
                'detail': 'Portia has finished generating verification questions',
                'stage': 'questions_ready',
                'progress': 35
            })
            
            logging.info(f"Portia Question Gen Plan: {plan}")
            logging.info(f"Portia Question Gen Result State: {result.state}")

            questions = []
            if result.state == "COMPLETE" and hasattr(result.outputs, "step_outputs"):
                step_outputs = list(result.outputs.step_outputs.values())
                if step_outputs and hasattr(step_outputs[0], 'get_value'):
                    output_value = step_outputs[0].get_value()
                    if isinstance(output_value, list):
                        questions = output_value
                    elif isinstance(output_value, str):
                         # Handle "not enough context" or newline-separated questions
                        if "not enough context" in output_value.lower():
                             logging.info("Detected 'not enough context' from question generation.")
                             self.pusher.send_update(session_id, 'not_enough_context', {
                                'message': 'Not enough factual claims to verify',
                                'detail': 'The content appears to be opinion, a question, or lacks factual assertions',
                                'stage': 'complete',
                                'progress': 100
                             })
                             return {
                                "initial_questions": [], "fact_checks": [], "follow_up_questions": [], "recommendations": [],
                                "judgment": "Not enough context",
                                "judgment_reason": "The content doesn't contain factual claims that can be verified.",
                                "metadata": {"confidence_scores": {"question_generator": 0.5, "fact_checking": 0.0, "follow_up_generator": 0.0, "judge": 0.5}}
                             }
                        else:
                            questions = [q.strip() for q in output_value.split('\n') if q.strip()]
            
            if not questions:
                 logging.warning("No questions generated or extracted from Portia plan.")
                 # Update frontend about error
                 self.pusher.send_update(session_id, 'error', {
                    'message': 'Failed to generate questions',
                    'detail': 'Portia was unable to identify factual claims requiring verification',
                    'stage': 'error',
                    'progress': 100
                 })
                 # Decide if this is an error or "not enough context" based on earlier check potentially missed
                 return {
                     "initial_questions": [], "fact_checks": [], "follow_up_questions": [], "recommendations": [],
                     "judgment": "ERROR", "judgment_reason": "Failed to generate questions.",
                     "metadata": {"confidence_scores": {"question_generator": 0.0, "fact_checking": 0.0, "follow_up_generator": 0.0, "judge": 0.0}}
                 }

            logging.info(f"Generated questions: {questions}")
            
            # Send generated questions to frontend
            self.pusher.send_update(session_id, 'questions_generated', {
                'message': 'Questions generated successfully',
                'detail': f'Generated {len(questions)} specific questions to verify factual claims',
                'questions': questions,
                'stage': 'fact_checking_prep',
                'progress': 40
            })

            # === Step 2: Fact-Check Each Question Manually ===
            logging.info(f"Step 2: Manually fact-checking {len(questions)} questions...")
            self.pusher.send_update(session_id, 'fact_checking_started', {
                'message': f'Starting fact-checking for {len(questions)} questions',
                'detail': 'Searching for evidence and evaluating factual claims',
                'stage': 'fact_checking',
                'progress': 45
            })
            
            fact_checks_results = []
            fact_checking_tasks = []

            # Prepare async tasks for fact-checking each question
            for i, q in enumerate(questions):
                 input_data = {
                     "questions": [{"question": q}],
                     "content": content,
                     "metadata": {"timestamp": "now"} # Simplified timestamp
                 }
                 # Update frontend about which question is being processed
                 self.pusher.send_update(session_id, 'checking_question', {
                    'message': f'Fact-checking question {i+1}/{len(questions)}',
                    'detail': f'Searching for evidence about: "{q}"',
                    'question': q,
                    'question_number': i+1,
                    'stage': 'fact_checking',
                    'progress': 45 + (i * (20 / len(questions)))
                 })
                 
                 # Send simulated updates about the fact-checking process
                 self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Running search for evidence',
                    'detail': f'Searching for reliable sources to verify: "{q}"',
                    'operation': 'evidence_gathering',
                    'question': q,
                    'stage': 'searching',
                    'progress': 45 + (i * (20 / len(questions)))
                 })
                 
                 # Use the agent directly
                 fact_checking_tasks.append(self.fact_checking_agent.process(input_data))
                 
                 # If callbacks aren't enabled, add a simulated search completion update
                 if i < len(questions)-1 and not getattr(self, 'callbacks_enabled', False):
                     # Small delay to make updates more natural
                     await asyncio.sleep(0.5)
                     
                     # Simulate search completion
                     self.pusher.send_update(session_id, 'portia_internal', {
                         'message': 'Found relevant evidence',
                         'detail': f'Discovered multiple sources with information about: "{q}"',
                         'operation': 'search_complete',
                         'question': q,
                         'stage': 'evidence_processing',
                         'progress': 45 + (i * (20 / len(questions))) + 5
                     })

            # Run fact-checking tasks concurrently
            raw_fact_check_outputs = await asyncio.gather(*fact_checking_tasks)
            
            # Update frontend that fact-checking is complete
            self.pusher.send_update(session_id, 'fact_checking_complete', {
                'message': 'Fact-checking complete for all questions',
                'detail': 'All evidence has been gathered and analyzed',
                'stage': 'analyzing_results',
                'progress': 70
            })
            
            # Process results
            formatted_fact_checks = []
            for i, output in enumerate(raw_fact_check_outputs):
                 q = questions[i]
                 # Extract details from the FactCheckingAgent's output structure
                 # Assuming output is a dict like {'fact_checks': [{'question': ..., 'analysis': ...}]}
                 analysis_data = {}
                 if isinstance(output, dict) and 'fact_checks' in output and output['fact_checks']:
                     analysis_data = output['fact_checks'][0].get('analysis', {})
                 
                 # Send reasoning update
                 self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Analyzing evidence',
                    'detail': f'Evaluating reliability and relevance of sources for: "{q}"',
                    'operation': 'evidence_analysis',
                    'question': q,
                    'stage': 'reasoning',
                    'progress': 70 + (i * (5 / len(questions)))
                 })
                 
                 # Get clean verification status without prefix
                 raw_status = analysis_data.get("verification_status", "UNCERTAIN")
                 clean_status = self._clean_verification_status(raw_status)
                 
                 # Basic formatting, adjust based on actual FactCheckingAgent output structure
                 formatted_check = {
                     "question": {"question": q},
                     "analysis": {
                         "verification_status": clean_status,
                         "raw_verification_status": raw_status,  # Keep original for debugging
                         "confidence_score": analysis_data.get("confidence_score", 0.5),
                         "sources": analysis_data.get("sources", []),
                         "supporting_evidence": analysis_data.get("supporting_evidence", []),
                         "contradicting_evidence": analysis_data.get("contradicting_evidence", [])
                     }
                 }
                 formatted_fact_checks.append(formatted_check)
                 
                 # Stream individual fact check results as they're processed
                 self.pusher.send_update(session_id, 'fact_check_result', {
                    'message': f'Fact check result for question {i+1}',
                    'detail': f'Verification status: {clean_status}',
                    'question_number': i+1,
                    'question': q,
                    'result': formatted_check,
                    'stage': 'fact_check_results',
                    'progress': 70 + (i * (10 / len(questions)))
                 })
                 
                 # If callbacks aren't enabled, add a simulated reasoning completion update after slight delay
                 if i < len(questions)-1 and not getattr(self, 'callbacks_enabled', False):
                     # Small delay to make updates more natural
                     await asyncio.sleep(0.5)
            
            logging.info(f"Finished fact-checking. Results count: {len(formatted_fact_checks)}")

            # === Step 3: Make Final Judgment Manually ===
            logging.info("Step 3: Manually calling Judge Agent...")
            self.pusher.send_update(session_id, 'judging_started', {
                'message': 'Making final judgment based on fact-checks',
                'detail': 'Analyzing all evidence to determine overall veracity',
                'stage': 'judging',
                'progress': 85
            })
            
            # Add detailed update about reasoning process
            self.pusher.send_update(session_id, 'portia_internal', {
                'message': 'Reasoning about overall truthfulness',
                'detail': 'Weighing evidence, considering source reliability, and evaluating confidence levels',
                'operation': 'final_reasoning',
                'stage': 'meta_analysis',
                'progress': 87
            })
            
            # If callbacks aren't enabled, add another simulation of the judgment process
            if not getattr(self, 'callbacks_enabled', False):
                # Small delay to make updates more natural
                await asyncio.sleep(0.8)
                
                # Simulate detailed judgment process
                self.pusher.send_update(session_id, 'portia_internal', {
                    'message': 'Synthesizing fact check results',
                    'detail': 'Evaluating overall pattern of evidence across all verification questions',
                    'operation': 'result_synthesis',
                    'stage': 'judgment_process',
                    'progress': 92
                })
            
            # Prepare input for the judge agent (expects list of analysis dicts)
            judge_input = [fc['analysis'] for fc in formatted_fact_checks if 'analysis' in fc]
            
            # Use the judge agent directly
            judge_result = self.judge_agent.judge(judge_input) # Assuming judge agent takes list of analyses

            # Extract judgment details from the JudgeAgent's output structure
            # Assuming judge_result is a dict like {"judgment": "REAL", "confidence_score": 0.9, "reason": "..."}
            final_judgment = judge_result.get("judgment", "UNCERTAIN")
            final_confidence = judge_result.get("confidence_score", 0.5)
            judgment_reason = judge_result.get("reason", "")

            # Map judgment to frontend expected values (reuse existing map)
            frontend_judgment_map = {
                "REAL": "REAL", "TRUE": "REAL", "VERIFIED": "REAL",
                "FALSE": "FAKE", "FAKE": "FAKE",
                "PARTIALLY TRUE": "MISLEADING", "MISLEADING": "MISLEADING", "PARTIALLY FALSE": "MISLEADING",
                "UNCERTAIN": "UNCERTAIN", "UNSUBSTANTIATED": "UNCERTAIN"
            }
            final_judgment_mapped = frontend_judgment_map.get(final_judgment.upper(), "UNCERTAIN")
            # Ensure confidence is within bounds
            final_confidence = max(0.5, min(1.0, final_confidence))

            logging.info(f"Judge result: Judgment={final_judgment_mapped}, Confidence={final_confidence}")
            
            # Send judgment to frontend
            self.pusher.send_update(session_id, 'judgment_complete', {
                'message': 'Final judgment complete',
                'detail': f'Verdict: {final_judgment_mapped.upper()} with {int(final_confidence*100)}% confidence',
                'judgment': final_judgment_mapped,
                'confidence': final_confidence,
                'reason': judgment_reason,
                'stage': 'complete',
                'progress': 100
            })

            # === Step 4: Format and Return Final Response ===
            final_result = {
                "initial_questions": questions,
                "fact_checks": formatted_fact_checks, # Use the formatted checks from Step 2
                "follow_up_questions": [], # Placeholder
                "recommendations": [], # Placeholder
                "judgment": final_judgment_mapped,
                "judgment_reason": judgment_reason,
                "metadata": {
                    "confidence_scores": {
                        # Assign reasonable confidence, maybe improve later
                        "question_generator": 0.8 if questions else 0.0, 
                        # Use average fact check confidence or judge confidence? Use judge's confidence.
                        "fact_checking": final_confidence, 
                        "follow_up_generator": 0.0, 
                        "judge": final_confidence
                    }
                }
            }
            
            # Send complete result
            self.pusher.send_update(session_id, 'process_complete', {
                'message': 'Fact-checking process complete',
                'detail': 'All analysis steps have been completed successfully',
                'result': final_result,
                'stage': 'complete',
                'progress': 100
            })
            
            return final_result
            
        except Exception as e:
            import traceback
            logging.error(f"Error in Portia processing: {str(e)}")
            traceback.print_exc()
            
            # Send error to frontend
            self.pusher.send_update(session_id, 'error', {
                'message': f'Error in fact-checking process: {str(e)}',
                'detail': 'An error occurred during the fact-checking pipeline',
                'error': str(e),
                'stage': 'error',
                'progress': 100
            })
            
            # Return detailed error
            return {
                "initial_questions": [], "fact_checks": [], "follow_up_questions": [], "recommendations": [],
                "judgment": "ERROR", "judgment_reason": f"Fact-checking pipeline failed: {str(e)}",
                "metadata": {"confidence_scores": {"question_generator": 0.0, "fact_checking": 0.0, "follow_up_generator": 0.0, "judge": 0.0}}
            } 