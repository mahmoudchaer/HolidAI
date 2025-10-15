"""
Flask web application for HotelPlanner with LangGraph ReAct agent.
Uses Anthropic Claude with proper tool calling.
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from agent import create_hotel_agent, chat_with_agent

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
	try:
		sys.stdout.reconfigure(encoding='utf-8')
	except:
		pass

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize LangGraph agent
app.agent, app.system_message = create_hotel_agent()

# Store conversation history per session
conversations = {}

@app.route('/')
def chat_index():
	"""Chat interface page."""
	return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def api_chat():
	"""Chat endpoint with LangGraph agent."""
	try:
		payload = request.get_json(force=True)
		session_id = payload.get('session_id', 'default')
		user_message = payload.get('message', '').strip()

		if not user_message:
			return jsonify({"success": False, "error": "Empty message"})

		# Get conversation history for this session
		conversation_history = conversations.get(session_id, [])

		# Get agent response with tool usage
		response, updated_history = chat_with_agent(app.agent, app.system_message, user_message, conversation_history)

		# Update conversation history
		conversations[session_id] = updated_history

		return jsonify({
			"success": True,
			"response": response,
			"session_id": session_id
		})

	except Exception as e:
		import traceback
		traceback.print_exc()
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

if __name__ == '__main__':
	# Check for API keys
	if not os.getenv("ANTHROPIC_API_KEY"):
		print("⚠️ Error: ANTHROPIC_API_KEY not found in .env file")
		print("Add to .env: ANTHROPIC_API_KEY=your_key_here")
		exit(1)
	
	if not os.getenv("SERPAPI_KEY"):
		print("⚠️ Error: SERPAPI_KEY not found in .env file")
		print("Add to .env: SERPAPI_KEY=your_key_here")
		exit(1)
	
	print("🤖 HotelPlanner LangGraph Agent starting...")
	print("Open http://localhost:5000")
	app.run(debug=True, host='0.0.0.0', port=5000)
