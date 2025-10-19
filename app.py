"""
Flask web application for HotelPlanner with LangGraph ReAct agent.
Uses Anthropic Claude with proper tool calling.
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from agent import create_hotel_agent, chat_with_agent
from auth.auth_tools import register_user_function, authenticate_user_function, get_user_by_email_function, update_user_profile_function
from tools.booking_tools import save_booking_to_database, get_user_bookings, cancel_booking_in_database

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

# Store booking sessions per user
booking_sessions = {}

@app.route('/')
def index():
	"""Main dashboard page (default)."""
	return render_template('dashboard.html')

@app.route('/chat')
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

@app.route('/api/booking', methods=['POST'])
def api_booking():
	"""Booking workflow endpoint."""
	try:
		payload = request.get_json(force=True)
		session_id = payload.get('session_id', 'default')
		action = payload.get('action', '')
		data = payload.get('data', {})
		
		# Get or create booking session
		if session_id not in booking_sessions:
			booking_sessions[session_id] = {}
		
		booking_session = booking_sessions[session_id]
		
		# Handle different booking actions
		if action == 'initiate':
			# Start booking process
			from tools.booking_tools import initiate_booking
			result = initiate_booking(data['hotel'], data['check_in_date'], data['check_out_date'], data.get('guests', 2))
			booking_sessions[session_id] = result
			
		elif action == 'select_room':
			from tools.booking_tools import select_room_type
			result = select_room_type(booking_session, data.get('room_type', 'Standard'))
			booking_sessions[session_id] = result
			
		elif action == 'add_guest_info':
			from tools.booking_tools import add_guest_information
			result = add_guest_information(booking_session, data)
			booking_sessions[session_id] = result
			
		elif action == 'process_payment':
			from tools.booking_tools import process_payment
			result = process_payment(booking_session, data)
			booking_sessions[session_id] = result
			
		elif action == 'confirm':
			from tools.booking_tools import confirm_booking
			result = confirm_booking(booking_session)
			booking_sessions[session_id] = result
			
		elif action == 'summary':
			from tools.booking_tools import get_booking_summary
			result = get_booking_summary(booking_session)
			return jsonify({"success": True, "summary": result})
			
		elif action == 'cancel':
			from tools.booking_tools import cancel_booking
			result = cancel_booking(booking_session, data.get('reason', ''))
			booking_sessions[session_id] = result
			
		else:
			return jsonify({"success": False, "error": "Invalid action"})
		
		return jsonify({
			"success": True,
			"booking_session": booking_sessions[session_id],
			"session_id": session_id
		})
		
	except Exception as e:
		import traceback
		traceback.print_exc()
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

@app.route('/api/auth/register', methods=['POST'])
def api_register():
	"""User registration endpoint."""
	try:
		payload = request.get_json(force=True)
		
		# Validate required fields
		required_fields = ['email', 'username', 'password', 'first_name', 'last_name']
		missing_fields = [field for field in required_fields if not payload.get(field)]
		
		if missing_fields:
			return jsonify({
				"success": False,
				"error": f"Missing required fields: {', '.join(missing_fields)}"
			}), 400
		
		# Register user
		result = register_user_function(
			email=payload['email'],
			username=payload['username'],
			password=payload['password'],
			first_name=payload['first_name'],
			last_name=payload['last_name'],
			phone=payload.get('phone', '')
		)
		
		if 'error' in result:
			return jsonify({
				"success": False,
				"error": result['error']
			}), 400
		
		return jsonify({
			"success": True,
			"message": "User registered successfully",
			"user": result['user'],
			"access_token": result['access_token']
		})
		
	except Exception as e:
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
	"""User login endpoint."""
	try:
		payload = request.get_json(force=True)
		
		# Validate required fields
		if not payload.get('email') or not payload.get('password'):
			return jsonify({
				"success": False,
				"error": "Email and password are required"
			}), 400
		
		# Authenticate user
		result = authenticate_user_function(
			email=payload['email'],
			password=payload['password']
		)
		
		if 'error' in result:
			return jsonify({
				"success": False,
				"error": result['error']
			}), 401
		
		return jsonify({
			"success": True,
			"message": "Login successful",
			"user": result['user'],
			"access_token": result['access_token']
		})
		
	except Exception as e:
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

@app.route('/api/user/bookings', methods=['GET'])
def api_user_bookings():
	"""Get user's booking history."""
	try:
		user_email = request.args.get('email')
		
		if not user_email:
			return jsonify({
				"success": False,
				"error": "User email is required"
			}), 400
		
		result = get_user_bookings(user_email)
		
		if 'error' in result:
			return jsonify({
				"success": False,
				"error": result['error']
			}), 400
		
		return jsonify({
			"success": True,
			"user": result['user'],
			"bookings": result['bookings'],
			"total_bookings": result['total_bookings']
		})
		
	except Exception as e:
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

@app.route('/api/booking/save', methods=['POST'])
def api_save_booking():
	"""Save booking to database."""
	try:
		payload = request.get_json(force=True)
		
		booking_data = payload.get('booking_data')
		user_email = payload.get('user_email')
		
		if not booking_data:
			return jsonify({
				"success": False,
				"error": "Booking data is required"
			}), 400
		
		result = save_booking_to_database(booking_data, user_email)
		
		if 'error' in result:
			return jsonify({
				"success": False,
				"error": result['error']
			}), 400
		
		return jsonify({
			"success": True,
			"message": result['message'],
			"booking_id": result['booking_id'],
			"confirmation_number": result['confirmation_number']
		})
		
	except Exception as e:
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

if __name__ == '__main__':
	# Check for API keys
	if not os.getenv("OPENAI_API_KEY"):
		print("⚠️ Error: OPENAI_API_KEY not found in .env file")
		print("Add to .env: OPENAI_API_KEY=your_key_here")
		exit(1)
	
	if not os.getenv("SERPAPI_KEY"):
		print("⚠️ Error: SERPAPI_KEY not found in .env file")
		print("Add to .env: SERPAPI_KEY=your_key_here")
		exit(1)
	
	print("🤖 HotelPlanner LangGraph Agent starting...")
	print("Open http://localhost:5000")
	app.run(debug=True, host='0.0.0.0', port=5000)
