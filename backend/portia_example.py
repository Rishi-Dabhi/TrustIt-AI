import os
from dotenv import load_dotenv
from portia import (
    Config,
    LLMModel,
    LLMProvider,
    Portia,
    example_tool_registry,
)
import yaml

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Load the portia_agent personality
personality_path = "backend/config/personalities/portia_agent.yaml"
with open(personality_path, "r") as f:
    personality = yaml.safe_load(f)

google_config = Config.from_default(
    llm_provider=LLMProvider.GOOGLE_GENERATIVE_AI,
    llm_model_name=LLMModel.GEMINI_2_0_FLASH,
    google_api_key=GOOGLE_API_KEY
)

portia = Portia(config=google_config, tools=example_tool_registry)
num_questions = 3
initial_query = "Donald trump and Bin ladin was school mates and Donald trump did 911."

# Use the personality system prompt for the agent
prompt = personality["system_prompt"] + "\n\n" + (
    f"First, critically evaluate the user query: '{initial_query}'.\n"
    f"Determine if this query represents a statement or question that can be meaningfully investigated or fact-checked using publicly available information, such as recent news headlines or established knowledge. \n"
    f"Consider if the query is: inherently subjective (opinion), purely personal ('Is my cat happy?'), unverifiable (metaphysical claims like 'Is God real?'), nonsensical, or simply too vague/lacking specifics to allow for factual analysis against external sources.\n"
    f"If the query falls into any of these categories (subjective, personal, unverifiable, nonsensical, too vague for factual lookup), then you MUST return *only* the exact text: 'not enough context'.\n\n"
    f"Otherwise (if the query *is* suitable for factual investigation via web search):\n"
    f"Generate {num_questions} specific, concise questions based on '{initial_query}'. These questions should be designed to help gather comprehensive information and context about the topic through web searches, focusing on distinct aspects or facets.\n"
    f"Return *only* the generated questions, each on a new line, without any numbering or bullet points."
)

plan = portia.plan(query=prompt)
print(f"--- PLAN ---\n{plan.steps}")
plan_run = portia.run_plan(plan)
print(plan_run.outputs.final_output)