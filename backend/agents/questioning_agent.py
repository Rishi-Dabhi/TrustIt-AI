from typing import Dict, Any, List
from .base_agent import BaseAgent

class QuestioningAgent(BaseAgent):
    """Agent that reviews and enhances analysis from other agents"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "questioning")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review reports from other agents and generate targeted questions.
        
        Args:
            input_data: Dictionary containing:
                - linguistic_analysis: Report from linguistic analysis
                - fact_checks: Report from fact checking
                - sentiment_analysis: Report from sentiment analysis
                - content: Original content being analyzed
        
        Returns:
            Dictionary containing:
                - follow_up_questions: Questions for each agent
                - identified_gaps: Gaps in current analysis
                - recommendations: Suggestions for deeper analysis
        """
        # Extract reports from input
        linguistic_analysis = input_data.get("linguistic_analysis", {})
        fact_checks = input_data.get("fact_checks", {})
        sentiment_analysis = input_data.get("sentiment_analysis", {})
        content = input_data.get("content", "")
        
        # Generate review prompt
        review_prompt = self._create_review_prompt(
            content,
            linguistic_analysis,
            fact_checks,
            sentiment_analysis
        )
        
        try:
            # Generate analysis review
            response = self.model.generate_content(
                self._create_agent_prompt(review_prompt)
            )
            
            if not response.text:
                return {
                    "error": "Failed to generate review",
                    "follow_up_questions": []
                }
            
            # Parse and structure the review
            review_results = self._parse_review(response.text)
            
            # Generate targeted questions for each agent
            questions = await self._generate_targeted_questions(
                review_results,
                linguistic_analysis,
                fact_checks,
                sentiment_analysis
            )
            
            return {
                "follow_up_questions": questions,
                "identified_gaps": review_results["gaps"],
                "recommendations": review_results["recommendations"],
                "agent_info": {
                    "name": self.personality["name"],
                    "role": self.personality["role"],
                    "confidence_level": self.personality["confidence_level"]
                }
            }
            
        except Exception as e:
            print(f"Error in questioning agent: {e}")
            return {
                "error": str(e),
                "follow_up_questions": []
            }
    
    def _create_review_prompt(
        self,
        content: str,
        linguistic_analysis: Dict[str, Any],
        fact_checks: Dict[str, Any],
        sentiment_analysis: Dict[str, Any]
    ) -> str:
        """Create a prompt for reviewing the current analysis"""
        return f"""Review the following analysis reports for the content:

Content:
{content}

Linguistic Analysis:
{self._format_dict(linguistic_analysis)}

Fact Checks:
{self._format_dict(fact_checks)}

Sentiment Analysis:
{self._format_dict(sentiment_analysis)}

Please:
1. Identify any gaps or inconsistencies in the analysis
2. Note areas that need deeper investigation
3. Highlight potential biases or overlooked aspects
4. Consider cross-references between different analyses
5. Evaluate the comprehensiveness of the verification

Provide your review in a structured format with clear sections for:
- Gaps Identified
- Inconsistencies
- Areas Needing Investigation
- Cross-Reference Insights
- Recommendations"""

    def _parse_review(self, text: str) -> Dict[str, Any]:
        """Parse the review response into structured data"""
        review = {
            "gaps": [],
            "inconsistencies": [],
            "investigation_areas": [],
            "cross_references": [],
            "recommendations": []
        }
        
        current_section = None
        try:
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                # Identify sections
                lower_line = line.lower()
                if "gaps" in lower_line:
                    current_section = "gaps"
                elif "inconsistencies" in lower_line:
                    current_section = "inconsistencies"
                elif "investigation" in lower_line:
                    current_section = "investigation_areas"
                elif "cross-reference" in lower_line:
                    current_section = "cross_references"
                elif "recommendations" in lower_line:
                    current_section = "recommendations"
                elif current_section and line.strip("-*"):
                    review[current_section].append(line)
                    
        except Exception as e:
            print(f"Error parsing review: {e}")
            
        return review
    
    async def _generate_targeted_questions(
        self,
        review: Dict[str, Any],
        linguistic_analysis: Dict[str, Any],
        fact_checks: Dict[str, Any],
        sentiment_analysis: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Generate specific questions for each agent based on the review"""
        questions = {
            "linguistic": [],
            "fact_checking": [],
            "sentiment": []
        }
        
        # Create prompt for generating targeted questions
        questions_prompt = f"""Based on the review findings:

Gaps: {', '.join(review['gaps'])}
Inconsistencies: {', '.join(review['inconsistencies'])}
Areas Needing Investigation: {', '.join(review['investigation_areas'])}

Generate specific questions for each agent to address these issues:
1. Questions for Linguistic Analysis Agent
2. Questions for Fact-Checking Agent
3. Questions for Sentiment Analysis Agent

Each question should:
- Target a specific gap or inconsistency
- Be answerable with the agent's capabilities
- Help deepen the analysis
- Cross-reference findings where relevant"""

        try:
            response = self.model.generate_content(
                self._create_agent_prompt(questions_prompt)
            )
            
            if response.text:
                # Parse questions for each agent
                current_agent = None
                for line in response.text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                        
                    lower_line = line.lower()
                    if "linguistic" in lower_line:
                        current_agent = "linguistic"
                    elif "fact" in lower_line:
                        current_agent = "fact_checking"
                    elif "sentiment" in lower_line:
                        current_agent = "sentiment"
                    elif current_agent and "?" in line:
                        questions[current_agent].append(line)
                        
        except Exception as e:
            print(f"Error generating targeted questions: {e}")
            
        return questions
    
    def _format_dict(self, d) -> str:
        """Format a dictionary or list for display in prompts"""
        if isinstance(d, list):
            return "\n".join([self._format_dict(item) for item in d])
        elif isinstance(d, dict):
            formatted = []
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    formatted.append(f"{k}:\n{self._format_dict(v)}")
                else:
                    formatted.append(f"{k}: {v}")
            return "\n".join(formatted)
        else:
            return str(d) 