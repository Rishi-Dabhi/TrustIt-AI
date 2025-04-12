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
        self._initialize_portia()
    
    def _initialize_portia(self):
        """Initialize Portia with custom tools"""
        portia_config = Config.from_default(
            llm_provider=LLMProvider.GOOGLE_GENERATIVE_AI,
            llm_model_name=LLMModel.GEMINI_2_0_FLASH,
            google_api_key=self.config["google_api_key"]
        )
        
        # Create our custom tools
        tools = [
            QuestionGeneratorTool(self.config),
            FactCheckTool(self.config),
            JudgmentTool(self.config)
        ]
        
        # Try to create a Tavily search tool if we can
        try:
            from portia.open_source_tools.search import SearchTool
            # If we can import SearchTool, create it and add to tools
            if "tavily_api_key" in self.config:
                tavily_tool = SearchTool(tavily_api_key=self.config["tavily_api_key"])
                tools.append(tavily_tool)
        except ImportError:
            # If we can't import SearchTool, just continue with our custom tools
            pass
            
        # Create Portia with just the tools list
        self.portia = Portia(config=portia_config, tools=tools)
    
    async def process_content(self, content: str) -> Dict[str, Any]:
        """Process content through Portia-based fact-checking pipeline"""
        try:
            # Define prompt for planning the fact-checking process
            prompt = f"""
            I need to fact-check the following content: '{content}'
            
            My fact-checking workflow should:
            1. Generate specific questions about the factual claims in the content
            2. For each question, find evidence through search
            3. Analyze the evidence to determine if claims are true, false, or misleading
            4. Make a final judgment about the overall reliability of the content
            
            If the content doesn't contain factual claims or is too vague, indicate that it's "not enough context" to fact-check.
            """
            
            # Generate plan
            plan = self.portia.plan(query=prompt)
            
            # Execute plan
            result = self.portia.run_plan(plan)
            
            # Debug info - safely log step information without assuming attributes
            import logging
            logging.info(f"Portia plan: {plan}")
            logging.info(f"Portia result state: {result.state}")
            
            # Check if there were clarifications needed (which would indicate an error)
            if result.state == "CLARIFICATION" and hasattr(result, "clarifications"):
                logging.warning(f"Portia requested clarifications: {result.clarifications}")
                # Return a meaningful error response
                return {
                    "initial_questions": [],
                    "fact_checks": [],
                    "follow_up_questions": [],
                    "recommendations": [],
                    "judgment": "ERROR",
                    "judgment_reason": f"Fact-checking failed: Portia requested clarification: {result.clarifications[0].user_guidance if result.clarifications else 'Unknown error'}",
                    "metadata": {
                        "confidence_scores": {
                            "question_generator": 0.0,
                            "fact_checking": 0.0,
                            "follow_up_generator": 0.0,
                            "judge": 0.0
                        }
                    }
                }
            
            # Extract correct data from step outputs if they exist
            step_outputs = []
            if hasattr(result.outputs, "step_outputs"):
                step_outputs = list(result.outputs.step_outputs.values())
                logging.info(f"Step outputs count: {len(step_outputs)}")
            
            # Extract questions from first step (should be step 0)
            questions = []
            if len(step_outputs) > 0:
                first_output = step_outputs[0]
                if hasattr(first_output, 'get_value'):
                    output_value = first_output.get_value()
                    if isinstance(output_value, list):
                        questions = output_value
                    elif isinstance(output_value, str):
                        # Try to split on newlines if it's a string
                        questions = [q.strip() for q in output_value.split('\n') if q.strip()]
                    logging.info(f"Extracted questions: {questions}")
            
            # Extract fact checks from Portia's outputs
            fact_checks_data = []
            raw_fact_checks = []
            
            # If there's a direct fact_checks property, use it
            if hasattr(result.outputs, 'fact_checks'):
                raw_fact_checks = result.outputs.fact_checks
            # Otherwise check for step outputs (second step should be fact checks)
            elif len(step_outputs) > 1:
                # Look at second step output for fact check results
                second_output = step_outputs[1]
                if hasattr(second_output, 'get_value'):
                    value = second_output.get_value()
                    # Sometimes it's a list directly
                    if isinstance(value, list):
                        raw_fact_checks = value
                    # Sometimes it's a dict with fact_checks inside
                    elif isinstance(value, dict) and 'fact_checks' in value:
                        raw_fact_checks = value['fact_checks']
                    # Sometimes it's a single fact check
                    elif isinstance(value, dict) and ('analysis' in value or 'question' in value):
                        raw_fact_checks = [value]
                    # Sometimes it's the first item in a list
                    elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                        raw_fact_checks = value
            
            # Extract final judgment
            judgment = "UNCERTAIN"
            judge_confidence = 0.5
            judgment_reason = ""

            for output in step_outputs:
                if hasattr(output, 'get_value') and isinstance(output.get_value(), str):
                    output_str = output.get_value()
                    
                    # Look for final judgment in the output
                    judgment_match = re.search(r"\[\s*JUDGE\s*\]\s*Final\s*judgment:\s*(\w+)\s*\(confidence:\s*([\d.]+)\)", output_str, re.IGNORECASE)
                    if judgment_match:
                        judgment = judgment_match.group(1).upper()
                        judge_confidence = float(judgment_match.group(2))
                        logging.info(f"Extracted judgment: {judgment} with confidence {judge_confidence}")
                    
                    # Look for judgment reason
                    reason_match = re.search(r"\[\s*JUDGE\s*\]\s*Reason:\s*(.+?)(?:\n\[|\Z)", output_str, re.DOTALL | re.IGNORECASE)
                    if reason_match:
                        judgment_reason = reason_match.group(1).strip()
            
            # Create properly formatted fact check objects for the frontend
            formatted_fact_checks = []
            
            # First, process any raw fact checks we found to extract their data
            for fc in raw_fact_checks:
                if isinstance(fc, dict):
                    # Extract the question
                    question = ""
                    if 'question' in fc and isinstance(fc['question'], dict):
                        question = fc['question'].get('question', "")
                    elif 'question' in fc and isinstance(fc['question'], str):
                        question = fc['question']
                    
                    # Extract the analysis
                    analysis = {}
                    if 'analysis' in fc and isinstance(fc['analysis'], dict):
                        analysis = fc['analysis']
                    
                    # Extract verification status and confidence
                    verification_status = "UNCERTAIN"
                    confidence_score = 0.5
                    
                    if 'verification_status' in analysis:
                        status = analysis['verification_status']
                        if "TRUE" in status.upper() or "REAL" in status.upper() or "VERIFIED" in status.upper():
                            verification_status = "REAL"
                            confidence_score = 1.0
                        elif "FALSE" in status.upper() or "FAKE" in status.upper():
                            verification_status = "FAKE"
                            confidence_score = 1.0
                        elif "PARTIALLY" in status.upper() or "MISLEADING" in status.upper():
                            verification_status = "MISLEADING"
                            confidence_score = 0.7
                        elif "UNCERTAIN" in status.upper() or "UNSUBSTANTIATED" in status.upper():
                            verification_status = "UNCERTAIN"
                            confidence_score = 0.5
                    
                    if 'confidence_score' in analysis:
                        confidence_score = float(analysis['confidence_score'])
                    
                    # Look for YES/NO evaluations in source_evaluations to calculate confidence
                    if 'source_evaluations' in analysis:
                        yes_count = 0
                        no_count = 0
                        total_sources = 0
                        
                        for src in analysis['source_evaluations']:
                            if 'verdict' in src:
                                total_sources += 1
                                if src['verdict'].upper() == 'YES':
                                    yes_count += 1
                                elif src['verdict'].upper() == 'NO':
                                    no_count += 1
                        
                        # Calculate confidence based on agreement ratio
                        if total_sources > 0:
                            if verification_status in ["REAL", "VERIFIED"]:
                                confidence_score = yes_count / total_sources
                            elif verification_status == "FAKE":
                                confidence_score = no_count / total_sources
                            elif verification_status == "MISLEADING":
                                # For misleading, we'll use a mix of yes/no
                                confidence_score = 0.5 + ((yes_count - no_count) / (2 * total_sources))
                            # Ensure confidence is in range [0.5, 1.0]
                            confidence_score = max(0.5, min(1.0, confidence_score))
                    
                    # Extract sources, supporting and contradicting evidence
                    sources = []
                    if 'sources' in analysis:
                        sources = analysis['sources']
                    elif 'source_evaluations' in analysis:
                        for src in analysis['source_evaluations']:
                            if 'source' in src:
                                sources.append(src['source'])
                    
                    supporting_evidence = []
                    if 'supporting_evidence' in analysis:
                        supporting_evidence = analysis['supporting_evidence']
                    
                    contradicting_evidence = []
                    if 'contradicting_evidence' in analysis:
                        contradicting_evidence = analysis['contradicting_evidence']
                    
                    # Add to the fact_checks_data
                    fact_checks_data.append({
                        'question': question,
                        'verification_status': verification_status,
                        'confidence_score': confidence_score,
                        'sources': sources,
                        'supporting_evidence': supporting_evidence,
                        'contradicting_evidence': contradicting_evidence
                    })
            
            # If we couldn't extract fact checks, use questions to create placeholders
            if len(fact_checks_data) == 0 and questions:
                for q in questions:
                    fact_checks_data.append({
                        'question': q,
                        'verification_status': "UNCERTAIN",
                        'confidence_score': judge_confidence,
                        'sources': [],
                        'supporting_evidence': [],
                        'contradicting_evidence': []
                    })
            
            # Now create properly formatted fact checks for the frontend
            for check_data in fact_checks_data:
                formatted_fact_checks.append({
                    "question": {"question": check_data['question']},
                    "analysis": {
                        "verification_status": check_data['verification_status'],
                        "confidence_score": check_data['confidence_score'],
                        "sources": check_data['sources'],
                        "supporting_evidence": check_data['supporting_evidence'],
                        "contradicting_evidence": check_data['contradicting_evidence']
                    }
                })
            
            # If we still have no fact checks but do have questions, create simple ones
            if not formatted_fact_checks and questions:
                for q in questions:
                    formatted_fact_checks.append({
                        "question": {"question": q},
                        "analysis": {
                            "verification_status": "UNCERTAIN",
                            "confidence_score": judge_confidence,
                            "sources": [],
                            "supporting_evidence": [],
                            "contradicting_evidence": []
                        }
                    })
            
            # Map judgment to frontend expected values
            frontend_judgment_map = {
                "REAL": "REAL",
                "TRUE": "REAL",
                "VERIFIED": "REAL",
                "FALSE": "FAKE",
                "FAKE": "FAKE",
                "PARTIALLY TRUE": "MISLEADING",
                "MISLEADING": "MISLEADING",
                "PARTIALLY FALSE": "MISLEADING",
                "UNCERTAIN": "UNCERTAIN",
                "UNSUBSTANTIATED": "UNCERTAIN"
            }
            
            # First, check if we have a strong signal from Portia's built-in judgment
            final_judgment = frontend_judgment_map.get(judgment, "UNCERTAIN")
            final_confidence = max(0.5, min(1.0, judge_confidence))
            
            # Check if we need to process any special raw outputs from Portia
            # For some fact checks, Portia will only analyze one question in detail
            analyzed_questions = set()
            
            # Parse all outputs looking for detailed analysis that might be missed
            for output in step_outputs:
                if hasattr(output, 'get_value') and isinstance(output.get_value(), str):
                    output_str = output.get_value()
                    
                    # Check if this is a fact check output with detailed results
                    for q in questions:
                        # Short question version for matching in text
                        short_q = q[:50] if len(q) > 50 else q
                        
                        # If this output contains analysis for one of our questions
                        if short_q in output_str and q not in analyzed_questions:
                            analyzed_questions.add(q)
                            
                            # Extract status and confidence
                            status_match = re.search(r"status:\s*(\w+)", output_str, re.IGNORECASE)
                            if status_match:
                                status = status_match.group(1).upper()
                                
                                # Update fact check for this question
                                for fc in formatted_fact_checks:
                                    if fc["question"]["question"] == q:
                                        # Map status to frontend value
                                        if "REAL" in status or "TRUE" in status or "VERIFIED" in status:
                                            fc["analysis"]["verification_status"] = "REAL" 
                                        elif "FAKE" in status or "FALSE" in status:
                                            fc["analysis"]["verification_status"] = "FAKE"
                                        elif "MISLEADING" in status or "PARTIALLY" in status:
                                            fc["analysis"]["verification_status"] = "MISLEADING"
                                        else:
                                            fc["analysis"]["verification_status"] = "UNCERTAIN"
                                        
                                        # Extract confidence
                                        conf_match = re.search(r"confidence:\s*([\d\.]+)", output_str, re.IGNORECASE)
                                        if conf_match:
                                            try:
                                                fc["analysis"]["confidence_score"] = float(conf_match.group(1))
                                            except ValueError:
                                                fc["analysis"]["confidence_score"] = 0.5
                            
                            # Extract supporting evidence
                            supp_evidence = []
                            supp_match = re.search(r"supporting evidence:(.+?)(?:contradicting evidence:|$)", 
                                                output_str, re.IGNORECASE | re.DOTALL)
                            if supp_match:
                                evidence_text = supp_match.group(1).strip()
                                supp_evidence = [e.strip() for e in evidence_text.split('\n') if e.strip()]
                            
                            # Extract contradicting evidence
                            contra_evidence = []
                            contra_match = re.search(r"contradicting evidence:(.+?)(?:sources|$)", 
                                                   output_str, re.IGNORECASE | re.DOTALL)
                            if contra_match:
                                evidence_text = contra_match.group(1).strip()
                                contra_evidence = [e.strip() for e in evidence_text.split('\n') if e.strip()]
                            
                            # Extract sources
                            sources = []
                            sources_match = re.search(r"sources:(.+?)(?:\n\n|\Z)", output_str, re.IGNORECASE | re.DOTALL)
                            if sources_match:
                                sources_text = sources_match.group(1).strip()
                                sources = [s.strip() for s in sources_text.split('\n') if s.strip() and 'http' in s]
                            
                            # Add parsed data to the formatted fact checks
                            for fc in formatted_fact_checks:
                                if fc["question"]["question"] == q:
                                    if supp_evidence:
                                        fc["analysis"]["supporting_evidence"] = supp_evidence
                                    if contra_evidence:
                                        fc["analysis"]["contradicting_evidence"] = contra_evidence
                                    if sources:
                                        fc["analysis"]["sources"] = sources
            
            # If questions were generated but no fact checks were processed for some questions,
            # create fact checks for all questions to ensure all are displayed
            question_map = {}
            for fc in formatted_fact_checks:
                question_text = fc["question"]["question"]
                question_map[question_text] = fc
            
            # Ensure all questions have a fact check entry
            complete_fact_checks = []
            for question in questions:
                if question in question_map:
                    complete_fact_checks.append(question_map[question])
                else:
                    # Create a default fact check for this question
                    complete_fact_checks.append({
                        "question": {"question": question},
                        "analysis": {
                            "verification_status": "UNCERTAIN",
                            "confidence_score": 0.5,
                            "sources": [],
                            "supporting_evidence": [],
                            "contradicting_evidence": []
                        }
                    })
            
            # Calculate the average confidence score based on all fact checks
            total_confidence = 0.0
            real_count = 0
            fake_count = 0
            misleading_count = 0
            uncertain_count = 0
            
            for fc in complete_fact_checks:
                total_confidence += fc["analysis"]["confidence_score"]
                status = fc["analysis"]["verification_status"]
                if status == "REAL":
                    real_count += 1
                elif status == "FAKE":
                    fake_count += 1
                elif status == "MISLEADING":
                    misleading_count += 1
                else:
                    uncertain_count += 1
            
            # Average confidence based on all questions
            if complete_fact_checks:
                average_confidence = total_confidence / len(complete_fact_checks)
                # Ensure confidence stays in reasonable bounds
                average_confidence = max(0.5, min(1.0, average_confidence))
            else:
                average_confidence = 0.5
                
            # Update the final judgment based on all fact checks
            # Previous algorithm:
            # - If all are REAL -> REAL
            # - If any are FAKE -> FAKE (unless others are REAL, then MISLEADING)
            # - If mixed or mostly uncertain -> UNCERTAIN
            if real_count > 0 and fake_count == 0 and misleading_count == 0:
                # All or mostly REAL claims
                final_judgment = "REAL" 
            elif fake_count > 0 and real_count == 0:
                # All or mostly FAKE claims
                final_judgment = "FAKE"
            elif fake_count > 0 and real_count > 0:
                # Mix of REAL and FAKE -> MISLEADING
                final_judgment = "MISLEADING"
            elif misleading_count > 0:
                # Any MISLEADING claims
                final_judgment = "MISLEADING"
            else:
                # Default to UNCERTAIN
                final_judgment = "UNCERTAIN"
            
            # If Portia's judgment seems confident, use that instead
            if judge_confidence >= 0.8:
                final_judgment = frontend_judgment_map.get(judgment, "UNCERTAIN")
            
            # If no questions were generated or it's a "not enough context" case
            if (not questions or 
                (len(step_outputs) > 0 and hasattr(step_outputs[0], 'get_value') and 
                 isinstance(step_outputs[0].get_value(), str) and 
                 "not enough context" in step_outputs[0].get_value().lower())):
                return {
                    "initial_questions": [],
                    "fact_checks": [],
                    "follow_up_questions": [],
                    "recommendations": [],
                    "judgment": "Not enough context",
                    "judgment_reason": "The content doesn't contain factual claims that can be verified.",
                    "metadata": {
                        "confidence_scores": {
                            "question_generator": 0.5,
                            "fact_checking": 0.0,
                            "follow_up_generator": 0.0,
                            "judge": 0.5
                        }
                    }
                }
            
            return {
                "initial_questions": questions,
                "fact_checks": complete_fact_checks,
                "follow_up_questions": [],  # Not implemented in this version
                "recommendations": [],  # Not implemented in this version
                "judgment": final_judgment,
                "judgment_reason": judgment_reason,
                "metadata": {
                    "confidence_scores": {
                        "question_generator": 0.7,
                        "fact_checking": average_confidence,
                        "follow_up_generator": 0.0,  # Not implemented
                        "judge": average_confidence
                    }
                }
            }
            
        except Exception as e:
            import traceback
            import logging
            error_msg = str(e)
            traceback.print_exc()
            logging.error(f"Error in Portia processing: {error_msg}")
            return {
                "initial_questions": [],
                "fact_checks": [],
                "follow_up_questions": [],
                "recommendations": [],
                "judgment": "ERROR",
                "judgment_reason": f"Fact-checking failed: {error_msg}",
                "metadata": {
                    "confidence_scores": {
                        "question_generator": 0.0,
                        "fact_checking": 0.0,
                        "follow_up_generator": 0.0,
                        "judge": 0.0
                    }
                }
            } 