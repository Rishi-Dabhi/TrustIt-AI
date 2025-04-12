import google.generativeai as genai
import traceback
from .personalities import AgentPersonalities

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
            model = genai.GenerativeModel('gemini-2.0-flash') 
            prompt = (
                f"First, critically evaluate the user query: '{initial_query}'.\n"
                f"Determine if this query represents a statement or question that can be meaningfully investigated or fact-checked using publicly available information, such as recent news headlines or established knowledge. \n"
                f"Consider if the query is: inherently subjective (opinion), purely personal ('Is my cat happy?'), unverifiable (metaphysical claims like 'Is God real?'), nonsensical, or simply too vague/lacking specifics to allow for factual analysis against external sources.\n"
                f"Otherwise (if the query *is* suitable for factual investigation via web search):\n"
                f"Generate {num_questions} specific, concise questions based on '{initial_query}'. These questions should be designed to help gather comprehensive information and context about the topic through web searches, focusing on distinct aspects or facets.\n"
                f"Return *only* the generated questions, each on a new line, without any numbering or bullet points."
            )
            
            response = model.generate_content(prompt)
            
            if response.text:

                print("\n\n--- Gemini Response ---")
                print(response.text)
                print("-" * 30 + "\n\n")

                if response.text.lower() == "not enough context":
                    print("Gemini summarised that the user query is not enough context to generate questions.")
                    return ["not enough context"]
                else:
                    questions = [q.strip() for q in response.text.split('\n') if q.strip()]
                    print(f"Generated {len(questions)} questions:")
                    for i, q in enumerate(questions):
                        print(f"  {i+1}. {q}")
                    print("-" * 30)
                    return questions
            else:
                print("Gemini did not return any questions.")
                return [initial_query] # Fallback to the original query

        except Exception as e:
            print(f"Error generating questions with Gemini: {e}")
            traceback.print_exc()
            # Fallback to the original query if generation fails
            return [initial_query] 