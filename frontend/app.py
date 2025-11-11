"""Simple Flask UI for LangGraph travel agent."""

import asyncio
import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# Add langraph and project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "langraph"))
sys.path.insert(0, str(project_root))

from graph import run

app = Flask(__name__)
CORS(app)


def run_async(coro):
    """Run an async coroutine in a fresh event loop.
    
    This ensures each request gets a clean event loop, avoiding
    "Event loop is closed" errors.
    """
    # Always create a fresh event loop for Flask requests
    # This is the safest approach to avoid event loop conflicts
    try:
        # Try to use asyncio.run() which handles everything automatically
        return asyncio.run(coro)
    except RuntimeError as e:
        # If asyncio.run() fails (e.g., loop already running), 
        # create a new loop manually
        if "asyncio.run() cannot be called" in str(e) or "cannot be called from a running event loop" in str(e):
            # Create a new event loop in a new thread
            import concurrent.futures
            import threading
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            raise


@app.route("/")
def index():
    """Serve the main UI page."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat requests."""
    try:
        data = request.json
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Run the LangGraph in a properly managed event loop
        result = run_async(run(user_message))
        
        response = result.get("last_response", "No response generated")
        agents_called = result.get("agents_called", [])
        
        return jsonify({
            "response": response,
            "agents_called": agents_called
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

