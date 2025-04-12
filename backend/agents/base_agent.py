import google.generativeai as genai
from typing import Dict, Any, List
from ..utils.personality_loader import PersonalityLoader

class BaseAgent:
    """Base class for all MARO framework agents"""
    
    def __init__(self, config: Dict[str, Any], agent_type: str):
        self.config = config
        self.agent_type = agent_type
        self.personality_loader = PersonalityLoader()
        self._load_personality()
        self._configure_gemini()
    
    def _configure_gemini(self):
        """Configure the Gemini model"""
        try:
            genai.configure(api_key=self.config["google_api_key"])
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            print(f"Gemini configured successfully for {self.agent_type}")
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
            raise
    
    def _load_personality(self):
        """Load agent personality"""
        try:
            self.personality = self.personality_loader.load_personality(self.agent_type)
            print(f"Loaded personality for {self.personality['name']}")
        except Exception as e:
            print(f"Error loading personality: {e}")
            raise
    
    def _create_agent_prompt(self, task_prompt: str) -> str:
        """Create a prompt that incorporates the agent's personality"""
        return f"""You are {self.personality['name']}, the {self.personality['role']}.

Your core traits are: {', '.join(self.personality['traits'])}
Your communication style is: {', '.join(self.personality['communication_style'])}
Your expertise includes: {', '.join(self.personality['expertise'])}
Your tone should be: {self.personality['tone']}

Follow this response structure:
{' → '.join(self.personality['dialogue_structure'])}

Task:
{task_prompt}"""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data - to be implemented by specific agents"""
        raise NotImplementedError("Each agent must implement its own process method") 