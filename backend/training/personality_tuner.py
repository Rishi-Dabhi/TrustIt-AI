import google.generativeai as genai
from typing import Dict, Any, List
import yaml
import os
from ..utils.personality_loader import PersonalityLoader

class PersonalityTuner:
    """Class to fine-tune model responses based on agent personalities"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.personality_loader = PersonalityLoader()
        self._configure_gemini()
        
    def _configure_gemini(self):
        """Configure the Gemini model"""
        genai.configure(api_key=self.config["google_api_key"])
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def generate_training_examples(self, personality: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate training examples based on personality traits"""
        examples = []
        
        # Generate examples for different response types
        for response_type in personality["response_format"]:
            prompt = self._create_training_prompt(personality, response_type)
            examples.append({
                "input": prompt,
                "expected_style": self._create_style_guide(personality)
            })
            
        return examples
    
    def _create_training_prompt(self, personality: Dict[str, Any], response_type: str) -> str:
        """Create a training prompt for a specific response type"""
        return f"""As {personality['name']}, the {personality['role']}, respond to this task:
        
Task: Analyze the following claim in the style of {response_type}
Claim: "Social media usage directly causes depression in teenagers"

Your response should reflect these traits:
{', '.join(personality['traits'])}

Communication style should be:
{', '.join(personality['communication_style'])}

Use your expertise in:
{', '.join(personality['expertise'])}

Maintain a {personality['tone']} tone.

You may use these catchphrases:
{', '.join(personality['catchphrases'])}"""

    def _create_style_guide(self, personality: Dict[str, Any]) -> str:
        """Create a style guide based on personality traits"""
        return f"""Response Style Guide:
1. Tone: {personality['tone']}
2. Communication: {', '.join(personality['communication_style'])}
3. Engagement: {', '.join(personality['engagement_techniques'])}
4. Structure: {' → '.join(personality['dialogue_structure'])}
5. Confidence Level: {personality['confidence_level']}
6. Thoroughness Level: {personality['thoroughness_level']}"""

    def tune_response(self, agent_type: str, input_text: str) -> str:
        """Fine-tune a response based on personality"""
        # Load personality configuration
        personality = self.personality_loader.load_personality(agent_type)
        
        # Create personality-specific prompt
        system_prompt = f"""You are {personality['name']}, the {personality['role']}.
        
Your core traits are: {', '.join(personality['traits'])}
Your communication style is: {', '.join(personality['communication_style'])}
Your expertise includes: {', '.join(personality['expertise'])}
Your tone should be: {personality['tone']}

Follow this response structure:
{' → '.join(personality['dialogue_structure'])}

Use these engagement techniques:
{', '.join(personality['engagement_techniques'])}

You may occasionally use these catchphrases:
{', '.join(personality['catchphrases'])}

Be aware of your biases:
{', '.join(personality['biases'])}

Maintain these levels:
- Confidence: {personality['confidence_level']}
- Skepticism: {personality['skepticism_level']}
- Thoroughness: {personality['thoroughness_level']}

Now, respond to the following input while maintaining this personality:

{input_text}"""

        # Generate tuned response
        response = self.model.generate_content(system_prompt)
        return response.text if response.text else "Failed to generate response"

    def evaluate_response(self, response: str, personality: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate how well a response matches the personality traits"""
        evaluation_prompt = f"""Evaluate how well this response matches the following personality traits:

Response:
{response}

Personality Traits:
{', '.join(personality['traits'])}

Communication Style:
{', '.join(personality['communication_style'])}

Tone: {personality['tone']}

Rate each aspect from 0.0 to 1.0:
1. Trait alignment
2. Communication style match
3. Tone consistency
4. Expertise demonstration
5. Overall personality match"""

        try:
            eval_response = self.model.generate_content(evaluation_prompt)
            # In a real implementation, you would parse the response to get numerical scores
            # For now, we'll return placeholder scores
            return {
                "trait_alignment": 0.8,
                "communication_style": 0.7,
                "tone_consistency": 0.9,
                "expertise_demonstration": 0.8,
                "overall_match": 0.8
            }
        except Exception as e:
            print(f"Error during evaluation: {e}")
            return {}

def main():
    """Main function to demonstrate personality tuning"""
    import json
    from pathlib import Path
    
    # Load configuration (you'll need to implement this)
    config = {"google_api_key": os.getenv("GOOGLE_API_KEY")}
    
    # Initialize tuner
    tuner = PersonalityTuner(config)
    
    # Test with each agent type
    agent_types = ["fact_checker", "linguistic_analyst", "sentiment_analyst", "judge"]
    test_input = "Analyze this claim: 'Social media usage directly causes depression in teenagers'"
    
    results = {}
    for agent_type in agent_types:
        print(f"\nTesting {agent_type}...")
        try:
            # Generate tuned response
            response = tuner.tune_response(agent_type, test_input)
            
            # Load personality for evaluation
            personality = tuner.personality_loader.load_personality(agent_type)
            
            # Evaluate response
            evaluation = tuner.evaluate_response(response, personality)
            
            results[agent_type] = {
                "response": response,
                "evaluation": evaluation
            }
            
            # Print results
            print(f"\nResponse from {personality['name']}:")
            print("-" * 50)
            print(response)
            print("\nEvaluation:")
            print(json.dumps(evaluation, indent=2))
            
        except Exception as e:
            print(f"Error processing {agent_type}: {e}")
    
    # Save results
    output_dir = Path("backend/training/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "tuning_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main() 