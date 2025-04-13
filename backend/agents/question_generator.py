import google.generativeai as genai
import traceback
from .personalities import AgentPersonalities
import re

class QuestionGeneratorAgent:
    """Agent that uses Gemini to generate sub-questions from an initial query."""
    
    def __init__(self, config):
        self.config = config
        self._configure_gemini()
        
    def _configure_gemini(self):
        """Configure the Google Generative AI client."""
        try:
            genai.configure(api_key=self.config["google_api_key"])
            print("Gemini configured successfully for Question Generator.")
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
            # Depending on the use case, you might want to raise an exception or handle this differently

    def generate_questions(self, initial_query: str, num_questions: int = 3) -> list[str]:
        """Generate a list of specific questions based on the initial query."""
        print(f"\n--- Generating Sub-Questions for: '{initial_query}' ---")
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') 
            prompt = (
                f"First, critically evaluate the following content: '{initial_query}'.\n"
                f"STEP 1: Determine if this content contains ANY factual claims or assertions that could potentially be misinformation or disinformation. A factual claim is any statement presented as fact rather than opinion, even if subtle or implied.\n\n"
                f"If the content contains NO factual claims whatsoever (e.g., it's purely opinion, a personal question, hypothetical scenario, or just requesting information), respond ONLY with: 'not enough context'.\n\n"
                f"STEP 2: If the content DOES contain factual claims, identify the most important claims that would need verification to determine if the content contains misinformation.\n\n"
                f"STEP 3: Generate exactly {num_questions} specific, direct questions that would help determine if the content contains misinformation. These questions should:\n"
                f"- Target the key factual claims present in the content\n"
                f"- Be phrased neutrally to avoid search bias\n"
                f"- Focus on verifiable aspects (dates, statistics, events, relationships between entities)\n"
                f"- Help establish the overall truthfulness of the content\n\n"
                f"Return ONLY the generated questions without any numbering, commentary, or explanation. Each question should be on a new line."
            )
            
            response = model.generate_content(prompt)
            
            if response.text:

                print("\n\n--- Gemini Response ---")
                print(response.text)
                print("-" * 30 + "\n\n")

                # Check for the special "NOT_FACT_CHECKABLE" response
                if "not enough context" in response.text:
                    print("Content does not contain factual claims that can be verified.")
                    return ["not enough context"]
                elif response.text.lower().strip() in ("not_fact_checkable"):
                    print("Gemini indicated that the user query is not enough context to generate questions.")
                    return ["not enough context"]
                else:
                    # Clean up the questions by removing any potential numbering or bullet points
                    raw_questions = [q.strip() for q in response.text.split('\n') if q.strip()]
                    cleaned_questions = []
                    
                    for q in raw_questions:
                        # Remove numbering (e.g., "1.", "1)", "[1]", etc.)
                        q = re.sub(r'^\s*[\[\(]?\d+[\.\)\]]?\s*', '', q)
                        # Remove bullet points
                        q = re.sub(r'^\s*[-•*]\s*', '', q)
                        if q and any(q.endswith(c) for c in ['?', '.', '!']):  # Ensure it's a question or statement
                            cleaned_questions.append(q)
                    
                    # If we have more questions than requested, trim to the requested amount
                    if len(cleaned_questions) > num_questions:
                        cleaned_questions = cleaned_questions[:num_questions]
                    
                    # If we somehow have no valid questions after cleaning, use the original query
                    if not cleaned_questions:
                        print("No valid questions were generated after cleaning.")
                        return [initial_query]
                        
                    print(f"Generated {len(cleaned_questions)} questions:")
                    for i, q in enumerate(cleaned_questions):
                        print(f"  {i+1}. {q}")
                    print("-" * 30)
                    return cleaned_questions
            else:
                print("Gemini did not return any questions.")
                return [initial_query] # Fallback to the original query

        except Exception as e:
            print(f"Error generating questions with Gemini: {e}")
            traceback.print_exc()
            # Fallback to the original query if generation fails
            return [initial_query] 