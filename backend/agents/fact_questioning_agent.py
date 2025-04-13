import google.generativeai as genai
import traceback
from typing import List, Dict, Any
from .base_agent import BaseAgent
from .personalities import AgentPersonalities

class FactQuestioningAgent(BaseAgent):
    """Agent that generates specific yes/no questions for fact verification"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "fact_questioning")
        
    def _configure_gemini(self):
        """Configure the Google Generative AI client."""
        try:
            genai.configure(api_key=self.config["google_api_key"])
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            print(f"Gemini configured successfully for {self.personality['name']} ({self.personality['role']}).")
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
            raise

    def _get_personality_prompt(self) -> str:
        """Generate a prompt that incorporates the agent's personality"""
        return (
            f"You are {self.personality['name']}, a {self.personality['role']} with the following characteristics:\n"
            f"Traits: {', '.join(self.personality['traits'])}\n"
            f"Communication Style: {self.personality['communication_style']}\n"
            f"Expertise: {', '.join(self.personality['expertise'])}\n"
            f"Tone: {self.personality['tone']}\n"
            f"Biases to be aware of: {', '.join(self.personality['biases'])}\n"
            f"Confidence Level: {self.personality['confidence_level']}\n"
            f"Skepticism Level: {self.personality['skepticism_level']}\n"
            f"Thoroughness Level: {self.personality['thoroughness_level']}\n\n"
        )

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate specific yes/no questions based on news content.
        
        Args:
            input_data: Dictionary containing:
                - content: The news content to analyze
                - metadata: Additional context about the news
        
        Returns:
            Dictionary containing:
                - questions: List of generated questions
                - context: Additional context for each question
                - confidence_scores: Confidence score for each question
        """
        content = input_data.get("content", "")
        metadata = input_data.get("metadata", {})
        
        # Create the task prompt
        task_prompt = f"""Analyze the following news content and generate specific yes/no questions that would help verify its authenticity:

Content:
{content}

Context/Metadata:
{metadata}

Generate questions that:
1. Focus on verifiable facts and claims
2. Can be answered through external sources
3. Help identify potential misinformation
4. Cover different aspects of the content

For each question, provide:
- The specific claim being questioned
- Context about why this question is important
- Suggested sources for verification"""

        try:
            # Generate questions using the model
            response = self.model.generate_content(
                self._create_agent_prompt(task_prompt)
            )
            
            if not response.text:
                return {
                    "questions": [],
                    "error": "Failed to generate questions"
                }
            
            # Process and structure the response
            questions = self._parse_questions(response.text)
            
            return {
                "questions": questions,
                "agent_info": {
                    "name": self.personality['name'],
                    "role": self.personality['role'],
                    "confidence_level": self.personality['confidence_level']
                },
                "metadata": {
                    "content_length": len(content),
                    "timestamp": input_data.get("timestamp"),
                    "source": input_data.get("source")
                }
            }
            
        except Exception as e:
            print(f"Error generating questions: {e}")
            return {
                "questions": [],
                "error": str(e)
            }
    
    def _parse_questions(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse the model's response into structured questions"""
        questions = []
        current_question = {}
        
        try:
            # Split response into lines and process
            lines = response_text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.endswith("?"):
                    # New question
                    if current_question:
                        questions.append(current_question)
                    current_question = {
                        "question": line,
                        "claim": "",
                        "context": "",
                        "suggested_sources": []
                    }
                elif "claim:" in line.lower():
                    current_question["claim"] = line.split(":", 1)[1].strip()
                elif "context:" in line.lower():
                    current_question["context"] = line.split(":", 1)[1].strip()
                elif "source" in line.lower():
                    current_question["suggested_sources"].append(line.split(":", 1)[1].strip())
            
            # Add the last question if exists
            if current_question:
                questions.append(current_question)
                
            # If no questions were found, create a default one
            if not questions:
                questions.append({
                    "question": "Is this claim verifiable?",
                    "claim": "The claim needs verification",
                    "context": "General verification needed",
                    "suggested_sources": ["reliable news sources", "academic research"]
                })
                
        except Exception as e:
            print(f"Error parsing questions: {e}")
            # Return a default question if parsing fails
            questions = [{
                "question": "Is this claim verifiable?",
                "claim": "The claim needs verification",
                "context": "General verification needed",
                "suggested_sources": ["reliable news sources", "academic research"]
            }]
            
        return questions
    
    async def refine_questions(self, questions: List[Dict[str, Any]], feedback: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Refine questions based on feedback from other agents"""
        try:
            feedback_prompt = f"""Review and refine the following questions based on feedback:

Original Questions:
{self._format_questions(questions)}

Feedback:
{feedback}

Please improve these questions by:
1. Making them more specific
2. Addressing any gaps identified in the feedback
3. Focusing on areas that need more verification
4. Ensuring they are answerable with available sources"""

            response = self.model.generate_content(
                self._create_agent_prompt(feedback_prompt)
            )
            
            if response.text:
                return self._parse_questions(response.text)
            return questions
            
        except Exception as e:
            print(f"Error refining questions: {e}")
            return questions
    
    def _format_questions(self, questions: List[Dict[str, Any]]) -> str:
        """Format questions for display in prompts"""
        formatted = []
        for i, q in enumerate(questions, 1):
            formatted.append(f"{i}. Question: {q['question']}")
            formatted.append(f"   Claim: {q['claim']}")
            formatted.append(f"   Context: {q['context']}")
            formatted.append(f"   Suggested Sources: {', '.join(q['suggested_sources'])}")
            formatted.append("")
        return "\n".join(formatted)

    def analyze_evidence(self, claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the collected evidence and provide a fact-checking assessment."""
        print(f"\n--- {self.personality['name']} ({self.personality['role']}) analyzing evidence for: '{claim}' ---")
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            # Format evidence for analysis
            evidence_text = "\n".join([
                f"Source: {e.get('source', 'Unknown')}\n"
                f"Content: {e.get('content', 'No content')}\n"
                f"Relevance: {e.get('relevance', 'Unknown')}\n"
                for e in evidence
            ])
            
            # Combine personality prompt with the analysis prompt
            personality_prompt = self._get_personality_prompt()
            analysis_prompt = (
                f"Given the following claim: '{claim}'\n\n"
                f"And the following evidence:\n{evidence_text}\n\n"
                f"Please analyze the evidence and provide:\n"
                f"1. A confidence score (0-100) on the claim's veracity\n"
                f"2. Key findings that support or contradict the claim\n"
                f"3. Any gaps in the evidence\n"
                f"4. Recommendations for further verification\n"
                f"Format the response as a structured analysis."
            )
            
            full_prompt = personality_prompt + analysis_prompt
            response = model.generate_content(full_prompt)
            
            if response.text:
                return {
                    "claim": claim,
                    "analysis": response.text,
                    "evidence_count": len(evidence),
                    "agent_name": self.personality['name'],
                    "agent_role": self.personality['role']
                }
            else:
                return {
                    "claim": claim,
                    "analysis": "Failed to analyze evidence",
                    "evidence_count": len(evidence),
                    "agent_name": self.personality['name'],
                    "agent_role": self.personality['role']
                }

        except Exception as e:
            print(f"Error analyzing evidence with Gemini: {e}")
            traceback.print_exc()
            return {
                "claim": claim,
                "analysis": f"Error during analysis: {str(e)}",
                "evidence_count": len(evidence),
                "agent_name": self.personality['name'],
                "agent_role": self.personality['role']
            } 