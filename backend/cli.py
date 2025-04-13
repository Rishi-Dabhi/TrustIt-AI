"""
Command-line interface for the TrustIt-AI fact-checking system.
"""
import argparse
import asyncio
from backend.utils import setup_environment
from backend.config import load_config
from backend.main import process_content

async def cli():
    """Run the command-line interface for the fact-checking system"""
    parser = argparse.ArgumentParser(
        description="Analyze and fact-check content using TrustIt-AI"
    )
    parser.add_argument(
        "--content",
        type=str,
        help="The content to analyze (if not provided, will use sample content)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a file containing the content to analyze"
    )
    
    args = parser.parse_args()
    
    # Setup environment and configuration
    setup_environment()
    
    try:
        # Load configuration
        config = load_config()
        
        # Get content from arguments or file
        if args.file:
            try:
                with open(args.file, 'r') as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading file: {e}")
                return
        elif args.content:
            content = args.content
        else:
            # Use sample content
            content = """
            Recent studies suggest that artificial intelligence could replace up to 40% of jobs 
            by 2030. This has led to widespread concern about unemployment and economic disruption. 
            However, historical evidence shows that technological advances typically create more 
            jobs than they eliminate.
            """
            print("\nUsing sample content since no input was provided:")
            print("-" * 50)
            print(content)
            print("-" * 50)
        
        # Process the content
        result = await process_content(content, config)
        
        # Display results
        if "error" not in result:
            print("\n" + "="*50)
            print("      FACT-CHECKING ANALYSIS RESULTS      ")
            print("="*50)
            print("\nInitial Questions:")
            for q in result["initial_questions"]:
                print(f"- {q['question']}")
            
            print("\nFact Checks:")
            for check in result["fact_checks"]:
                print(f"\nQuestion: {check['question']['question']}")
                print(f"Status: {check['analysis']['verification_status']}")
                print(f"Confidence: {check['analysis']['confidence_score']}")
            
            print("\nFollow-up Questions:")
            for agent, questions in result["follow_up_questions"].items():
                print(f"\n{agent.title()} Agent Questions:")
                for q in questions:
                    print(f"- {q}")
            
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
    asyncio.run(cli()) 