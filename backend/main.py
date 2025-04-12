"""
Main entry point for the TrustIt-AI application.
Initializes the environment, loads configuration, and runs the fact-checking system.
"""

import asyncio
import traceback
from typing import Dict, Any, List

# Use relative imports
from .agents import (
    FactCheckingAgent,
    QuestionGeneratorAgent,
    JudgeAgent,  # Import the JudgeAgent
)
from .services.search_service import SearchService
from .portia_integration import PortiaFactChecker  # Import the new Portia integration
from .config import load_config # Assuming config.py is in the same directory
from .utils import setup_environment # Assuming utils is a subdirectory

# Keep the original process_content for backward compatibility
async def process_content(content: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Process content through the agent pipeline"""
    try:
        print("\nInitializing agents...")
        # Initialize services
        search_service = SearchService(config)
        
        # Initialize agents
        fact_checker = FactCheckingAgent(config)
        question_generator = QuestionGeneratorAgent(config)
        judge_agent = JudgeAgent(config)  # Initialize the JudgeAgent
        
        print("\nGenerating initial questions...")
        # Generate initial questions
        # The generate_questions method is synchronous and returns a list of strings.
        initial_questions_list = question_generator.generate_questions(initial_query=content)

        if "not enough context" in initial_questions_list:
            return {
                "initial_questions": ["Not enough context to generate questions."], 
                "fact_checks": [],
                "follow_up_questions": [],
                "recommendations": [],
                "judgment": "Not enough context",
                "judgment_reason": "Not enough context to generate questions.",
                "metadata": {
                    "confidence_scores": {
                        "question_generator": 0.5,
                        "fact_checking": 0.5,
                        "follow_up_generator": 0.5,
                        "judge": 0.5
                    }
                }
            }

        questions_result = {
            "questions": initial_questions_list,
            # Placeholder for metadata and confidence score if needed later
            "metadata": {"timestamp": "2024-03-20T12:00:00Z"}, 
            "confidence_score": 0.0 # Placeholder
        }

        # questions_list is currently a list of strings.
        # The FactCheckingAgent likely expects a list of dicts, e.g., [{'question': '...'}]
        questions_for_fact_checker = [{"question": q} for q in initial_questions_list]

        if "error" in questions_result:
            print(f"Error in fact questioning: {questions_result['error']}")
            return {"error": f"Fact questioning failed: {questions_result['error']}"}

        print("\nVerifying facts...")
        # Verify facts
        fact_checks = await fact_checker.process({
            "questions": questions_for_fact_checker, # Pass the formatted list
            "content": content,
            "metadata": questions_result["metadata"]
        })

        if "error" in fact_checks:
            print(f"Error in fact checking: {fact_checks['error']}")
            return {"error": f"Fact checking failed: {fact_checks['error']}"}

        # Temporarily comment out follow-up question generation as QuestionGeneratorAgent
        # doesn't support generating questions based on fact checks.
        # print("\\nGenerating follow-up questions...")
        # # Review and generate follow-up questions
        # review_result = await question_generator.process({ # Use question_generator
        #     "fact_checks": fact_checks["fact_checks"],
        #     "content": content,
        #     "metadata": fact_checks["metadata"]
        # })
        #
        # if "error" in review_result:
        #     print(f"Error in questioning: {review_result['error']}")
        #     return {"error": f"Questioning failed: {review_result['error']}"}

        # TODO: Implement follow-up question generation using an appropriate agent.
        follow_up_questions_placeholder = [] # Placeholder
        recommendations_placeholder = [] # Placeholder
        follow_up_confidence_placeholder = 0.0 # Placeholder

        # Make final judgment using JudgeAgent
        print("\nMaking final judgment...")
        judgment_result = judge_agent.judge(fact_checks["fact_checks"])

        return {
            "initial_questions": questions_result["questions"],
            "fact_checks": fact_checks["fact_checks"],
            "follow_up_questions": follow_up_questions_placeholder, # Use placeholder
            "recommendations": recommendations_placeholder, # Use placeholder
            "judgment": judgment_result["judgment"],  # Include judgment in the result
            "judgment_reason": judgment_result.get("reason", ""),  # Include the reasoning behind the judgment
            "metadata": {
                "confidence_scores": {
                    "question_generator": questions_result.get("confidence_score", 0.0),
                    "fact_checking": fact_checks.get("confidence_score", 0.0),
                    # "question_generator": review_result.get("confidence_score", 0.0) # Commented out
                    "follow_up_generator": follow_up_confidence_placeholder, # Placeholder
                    "judge": judgment_result["confidence_score"]  # Add judge confidence score
                }
            }
        }
        
    except Exception as e:
        print(f"\nError in processing pipeline: {str(e)}")
        traceback.print_exc()
        return {"error": str(e)}

# New function that uses Portia integration
async def process_content_with_portia(content: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Process content through the Portia-based agent pipeline"""
    try:
        print("\nInitializing Portia fact checker...")
        portia_checker = PortiaFactChecker(config)
        
        print("\nProcessing content with Portia...")
        result = await portia_checker.process_content(content)
        
        return result
        
    except Exception as e:
        print(f"\nError in Portia processing pipeline: {str(e)}")
        traceback.print_exc()
        return {"error": str(e)}

async def main():
    """Main function to run the application"""
    # Setup environment and configuration
    setup_environment()
    
    try:
        # Load configuration
        config = load_config()
        
        # Test content
        test_content = """
        Recent studies suggest that artificial intelligence could replace up to 40% of jobs 
        by 2030. This has led to widespread concern about unemployment and economic disruption. 
        However, historical evidence shows that technological advances typically create more 
        jobs than they eliminate.
        """
        
        # Choose which processing method to use (original or Portia)
        use_portia = True  # Set to False to use the original pipeline
        
        if use_portia:
            # Process with Portia
            result = await process_content_with_portia(test_content, config)
            print("\nUsing Portia for fact-checking")
        else:
            # Process with original pipeline
            result = await process_content(test_content, config)
            print("\nUsing original pipeline for fact-checking")
        
        # Display results
        if "error" not in result:
            print("\n" + "="*50)
            print("      FACT-CHECKING ANALYSIS RESULTS      ")
            print("="*50)
            
            # Display Final Judgment first for quick reference
            print(f"\nFINAL JUDGMENT: {result['judgment'].upper()}")
            print(f"Confidence Score: {result['metadata']['confidence_scores'].get('judge', 0.0):.2f}")
            if "judgment_reason" in result and result["judgment_reason"]:
                print(f"Reasoning: {result['judgment_reason']}")
            
            print("\nInitial Questions:")
            for q in result["initial_questions"]:
                print(f"- {q}")
            
            print("\nFact Checks:")
            for check in result["fact_checks"]:
                print(f"\nQuestion: {check.get('question', {}).get('question', 'Unknown')}")
                if "analysis" in check:
                    print(f"Status: {check['analysis'].get('verification_status', 'Unknown')}")
                    print(f"Confidence: {check['analysis'].get('confidence_score', 0.0)}")
            
            if result.get("follow_up_questions"):
                print("\nFollow-up Questions:")
                for agent, questions in result["follow_up_questions"].items():
                    print(f"\n{agent.title()} Agent Questions:")
                    for q in questions:
                        print(f"- {q}")
            
            if result.get("recommendations"):
                print("\nRecommendations:")
                for rec in result["recommendations"]:
                    print(f"- {rec}")
                
            print("\nConfidence Scores:")
            for agent, score in result["metadata"]["confidence_scores"].items():
                print(f"{agent}: {score}")
            print("="*50)
        else:
            print(f"\nError: {result['error']}")
            
    except Exception as e:
        print(f"\nApplication error: {e}")
        print("\n--- TrustIt-AI initialization failed ---")
        print("Please ensure you have:")
        print("1. Set up all required API keys in the .env file")
        print("2. Installed all required dependencies")
        print("3. Configured the environment correctly")

if __name__ == "__main__":
    asyncio.run(main()) 