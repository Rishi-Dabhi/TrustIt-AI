import os
import yaml
from typing import Dict, Any

class PersonalityLoader:
    """Utility class to load agent personalities from YAML files"""
    
    def __init__(self):
        self.personality_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "personalities"
        )
    
    def load_personality(self, agent_type: str) -> Dict[str, Any]:
        """Load personality configuration for a specific agent type"""
        yaml_file = os.path.join(self.personality_dir, f"{agent_type}.yaml")
        
        if not os.path.exists(yaml_file):
            raise ValueError(f"No personality configuration found for agent type: {agent_type}")
        
        try:
            with open(yaml_file, 'r') as f:
                personality = yaml.safe_load(f)
                print(f"Loaded personality for {personality['name']} ({personality['role']})")
                return personality
        except Exception as e:
            raise ValueError(f"Error loading personality configuration: {e}")
    
    def get_available_personalities(self) -> list[str]:
        """Get a list of available personality configurations"""
        try:
            yaml_files = [f[:-5] for f in os.listdir(self.personality_dir) 
                         if f.endswith('.yaml')]
            return yaml_files
        except Exception as e:
            print(f"Error listing personality configurations: {e}")
            return [] 