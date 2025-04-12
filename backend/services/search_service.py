import traceback
import google.generativeai as genai

# Use relative imports since we'll run from the project root
from ..tools import TavilySearchTool
from ..agents import QuestionGeneratorAgent

class SearchService:
    """Service to handle search functionality using Google's Generative AI and Tavily"""
    
    def __init__(self, config):
        self.config = config
        self.question_agent = QuestionGeneratorAgent(config)
        self._initialize_genai()
        self.search_tool = None
    
    def _initialize_genai(self):
        """Initialize Google's Generative AI and Tavily tool"""
        try:
            if "google_api_key" in self.config:
                genai.configure(api_key=self.config["google_api_key"])
                print("Google Generative AI configured successfully!")
            else:
                raise ValueError("Google API Key is required for setup.")

            # Create the Tavily search tool directly
            if "tavily_api_key" in self.config:
                self.search_tool = TavilySearchTool(api_key=self.config["tavily_api_key"])
                print(f"Created Tavily search tool successfully!")
            else:
                 raise ValueError("Tavily API Key is required for setup.")

        except Exception as e:
            print(f"Error during initialization: {e}")
            traceback.print_exc()
            self.search_tool = None
    
    def search(self, query: str) -> str:
        """
        Generate sub-questions, search the web for each using Tavily,
        and aggregate the results using Google's Generative AI.
        """
        if not self.search_tool:
            return "Error: Search service is not properly initialized."

        try:
            # 1. Generate sub-questions
            sub_questions = self.question_agent.generate_questions(query)

            all_results = []
            print(f"\n--- Searching for {len(sub_questions)} Sub-Questions ---")

            # 2. Loop through sub-questions and search using Tavily
            for i, sub_q in enumerate(sub_questions):
                print(f"\n[{i+1}/{len(sub_questions)}] Searching for: '{sub_q}'")
                print("-" * 20)

                try:
                    # Use Tavily tool directly
                    search_result = self.search_tool.search(sub_q)
                    all_results.append({
                        'question': sub_q,
                        'result': search_result
                    })
                    print(f"Found results for '{sub_q}'")

                except Exception as e:
                    error_message = f"Error during search for '{sub_q}': {e}"
                    print(error_message)
                    traceback.print_exc()
                    all_results.append({
                        'question': sub_q,
                        'result': f"Search failed: {str(e)}"
                    })

            print("--- All Sub-Searches Completed ---")

            # 3. Use Gemini to synthesize the results
            return self._synthesize_results(query, all_results)

        except Exception as e:
            error_message = f"Error during main search process: {e}"
            print(error_message)
            traceback.print_exc()
            return f"An error occurred: {error_message}"

    def _synthesize_results(self, original_query: str, results: list[dict]) -> str:
        """Use Gemini to synthesize the collected results into a final answer."""
        print("\n--- Synthesizing Final Answer ---")
        try:
            # Ensure GenAI is configured (might be redundant if __init__ succeeded, but safe)
            if not genai.API_KEY:
                 return "Error: Google Generative AI is not configured for synthesis."

            model = genai.GenerativeModel('gemini-1.5-pro') # Consider making model configurable

            # Format the results for the prompt
            formatted_results = "\n\n".join([
                f"Sub-question: {r['question']}\nResults: {r['result']}"
                for r in results
            ])

            prompt = (
                f"Based on the original query: '{original_query}' and the following search results:\n\n"
                f"{formatted_results}\n\n"
                f"Please synthesize this information into a comprehensive and well-structured answer to the original query. "
                f"Integrate the information smoothly and ensure it directly addresses the original query. If search for some sub-questions failed, mention that the information might be incomplete."
            )

            response = model.generate_content(prompt)
            # Add basic check for response content
            if response and response.text:
                return response.text
            else:
                # Handle cases where the response might be empty or blocked
                print(f"Synthesis generation failed or returned empty response. Response: {response}")
                return "Synthesis failed to generate content. Raw results:\n\n" + formatted_results


        except Exception as e:
            print(f"Error during synthesis: {e}")
            traceback.print_exc()
            # Fallback to returning raw results if synthesis fails
            formatted_results = "\n\n".join([
                f"Question: {r['question']}\nResults: {r['result']}"
                for r in results
            ])
            return "Synthesis failed due to an error. Raw results:\n\n" + formatted_results 