"""Main entry point for LangGraph orchestration."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from graph import run

# Load environment variables from .env file in main directory
# Get the project root directory (1 level up from langraph/)
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)


async def main():
    """Main entry point for interactive LangGraph."""
    print("=" * 60)
    print("LangGraph Travel Agent System")
    print("=" * 60)
    print("\nType 'exit' to quit\n")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\nGoodbye!")
                break
            
            if not user_input:
                continue
            
            print("\nProcessing...")
            result = await run(user_input)
            
            print(f"\nAssistant: {result.get('last_response', 'No response')}")
            
            # Show route if different from main_agent
            route = result.get('route', 'main_agent')
            if route != 'main_agent':
                print(f"[Route: {route}]")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

