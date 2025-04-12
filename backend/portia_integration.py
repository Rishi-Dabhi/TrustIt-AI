"""
Portia integration for TrustIt-AI fact-checking workflow.
Implements the fact-checking pipeline using Portia's multi-agent planning and execution.
"""

import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import re

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
    
    def _initialize_portia_for_questions(self):
        """Initialize Portia with only the QuestionGeneratorTool for planning"""
        portia_config = Config.from_default(
            llm_provider=LLMProvider.GOOGLE_GENERATIVE_AI,
            llm_model_name=LLMModel.GEMINI_2_0_FLASH,
            google_api_key=self.config["google_api_key"]
        )
        
        # Only include Question Generator tool for Portia planning phase
        tools = [
            QuestionGeneratorTool(self.config) 
        ]
        
        # Create Portia instance configured only for question generation planning
        self.portia_planner = Portia(config=portia_config, tools=tools)
    
    async def process_content(self, content: str) -> Dict[str, Any]:
        """Process content through fact-checking pipeline: QGen (Portia Plan) -> FactCheck (Manual Loop) -> Judge (Manual Call)"""
        import logging
        import asyncio

        try:
            # === Step 1: Generate Questions using Portia Planner ===
            logging.info("Step 1: Generating questions using Portia Planner...")
            # Prompt focused only on question generation or "not enough context"
            question_prompt = f"""
            Critically evaluate the following content: '{content}'
            Determine if it contains factual claims suitable for investigation or if it's subjective, unverifiable, nonsensical, or too vague.
            If unsuitable for fact-checking, return ONLY the exact text: 'not enough context'.
            Otherwise, generate 3 specific, concise questions targeting the main factual claims. Return ONLY the questions, each on a new line.
            """
            
            # Generate and run the plan for question generation
            plan = self.portia_planner.plan(query=question_prompt)
            result = self.portia_planner.run_plan(plan)
            
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
                 # Decide if this is an error or "not enough context" based on earlier check potentially missed
                 return {
                     "initial_questions": [], "fact_checks": [], "follow_up_questions": [], "recommendations": [],
                     "judgment": "ERROR", "judgment_reason": "Failed to generate questions.",
                     "metadata": {"confidence_scores": {"question_generator": 0.0, "fact_checking": 0.0, "follow_up_generator": 0.0, "judge": 0.0}}
                 }

            logging.info(f"Generated questions: {questions}")

            # === Step 2: Fact-Check Each Question Manually ===
            logging.info(f"Step 2: Manually fact-checking {len(questions)} questions...")
            fact_checks_results = []
            fact_checking_tasks = []

            # Prepare async tasks for fact-checking each question
            for q in questions:
                 input_data = {
                     "questions": [{"question": q}],
                     "content": content,
                     "metadata": {"timestamp": "now"} # Simplified timestamp
                 }
                 # Use the agent directly
                 fact_checking_tasks.append(self.fact_checking_agent.process(input_data)) 

            # Run fact-checking tasks concurrently
            raw_fact_check_outputs = await asyncio.gather(*fact_checking_tasks)
            
            # Process results
            formatted_fact_checks = []
            for i, output in enumerate(raw_fact_check_outputs):
                 q = questions[i]
                 # Extract details from the FactCheckingAgent's output structure
                 # Assuming output is a dict like {'fact_checks': [{'question': ..., 'analysis': ...}]}
                 analysis_data = {}
                 if isinstance(output, dict) and 'fact_checks' in output and output['fact_checks']:
                     analysis_data = output['fact_checks'][0].get('analysis', {})
                 
                 # Basic formatting, adjust based on actual FactCheckingAgent output structure
                 formatted_check = {
                     "question": {"question": q},
                     "analysis": {
                         "verification_status": analysis_data.get("verification_status", "UNCERTAIN"),
                         "confidence_score": analysis_data.get("confidence_score", 0.5),
                         "sources": analysis_data.get("sources", []),
                         "supporting_evidence": analysis_data.get("supporting_evidence", []),
                         "contradicting_evidence": analysis_data.get("contradicting_evidence", [])
                     }
                 }
                 formatted_fact_checks.append(formatted_check)
            
            logging.info(f"Finished fact-checking. Results count: {len(formatted_fact_checks)}")


            # === Step 3: Make Final Judgment Manually ===
            logging.info("Step 3: Manually calling Judge Agent...")
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

            # === Step 4: Format and Return Final Response ===
            return {
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
            
        except Exception as e:
            import traceback
            logging.error(f"Error in Portia processing: {str(e)}")
            traceback.print_exc()
            # Return detailed error
            return {
                "initial_questions": [], "fact_checks": [], "follow_up_questions": [], "recommendations": [],
                "judgment": "ERROR", "judgment_reason": f"Fact-checking pipeline failed: {str(e)}",
                "metadata": {"confidence_scores": {"question_generator": 0.0, "fact_checking": 0.0, "follow_up_generator": 0.0, "judge": 0.0}}
            } 