"""Simple Flask UI for LangGraph travel agent."""

import asyncio
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import secrets
from sqlalchemy import create_engine, Column, String, DateTime, func, JSON
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv
import bcrypt
import json
import uuid
import io
import contextlib

# Add langraph and project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "langraph"))
sys.path.insert(0, str(project_root))

from graph import run

# Import STM module (use alias to avoid conflict with route function)
# STM is in project root, which is already in sys.path
from stm.short_term_memory import add_message as stm_add_message, clear_stm as stm_clear_stm

# Load .env file from project root (works both locally and in Docker)
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Fallback to current directory
    load_dotenv()

# Database setup
class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model."""
    __tablename__ = "users"

    email = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)


class Chat(Base):
    """Chat/Conversation model."""
    __tablename__ = "chats"

    email = Column(String, primary_key=True, index=True)
    session_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    messages = Column(JSONB, nullable=False, default=list)  # Store as JSON array
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TravelPlanItem(Base):
    """Travel plan item model."""
    __tablename__ = "travel_plan_items"

    email = Column(String, primary_key=True, index=True)
    session_id = Column(String, primary_key=True, index=True)
    title = Column(String, primary_key=True, index=True)
    details = Column(JSONB, nullable=False, default=dict)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default='not_booked')
    normalized_key = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Database connection - use 127.0.0.1 instead of localhost to avoid IPv6 issues
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@127.0.0.1:5437/myproject"
)

# Use connect_args to handle connection issues gracefully
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize database tables (only if database is available)
def init_database():
    """Initialize database tables if database is available."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables initialized successfully")
    except Exception as e:
        print(f"⚠ Warning: Could not connect to database: {e}")
        print("  Database features will be unavailable until database is started.")
        print("  To start database: docker-compose up -d")

# Try to initialize database on startup (non-blocking)
init_database()

# Pre-load embedding model to avoid Flask reloader issues
def preload_embedding_model():
    """Pre-load the sentence-transformers model at startup to avoid reloader issues."""
    try:
        print("[STARTUP] Pre-loading embedding model...")
        from memory.embeddings import get_model
        model = get_model()
        # Test encode to ensure model is fully loaded
        _ = model.encode("test", convert_to_numpy=True)
        print("[STARTUP] ✓ Embedding model loaded successfully")
    except Exception as e:
        print(f"[STARTUP] ⚠ Warning: Could not pre-load embedding model: {e}")
        print("  Memory features may be slower on first use")

# Pre-load model at startup
preload_embedding_model()

def serialize_plan_item(item: TravelPlanItem) -> dict:
    """Serialize TravelPlanItem ORM object into dict."""
    return {
        "title": item.title,
        "type": item.type,
        "status": item.status,
        "details": item.details or {},
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None
    }


app = Flask(__name__, static_folder='dist', static_url_path='')
app.secret_key = secrets.token_hex(16)  # Generate a secret key for sessions
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")


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


def require_login(f):
    """Decorator to require login for routes."""
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route("/")
def index():
    """Serve the React app."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/booking")
def serve_booking():
    """Serve the React app for booking page (client-side routing)."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/<path:path>")
def serve_static(path):
    """Serve static files or React app for client-side routing."""
    # Skip API routes - they're handled separately
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # For client-side routes (like /booking), serve index.html
        return send_from_directory(app.static_folder, 'index.html')


@app.route("/api/user", methods=["GET"])
def get_current_user():
    """Get current user info."""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "Not authenticated"}), 401
    
    return jsonify({
        "success": True,
        "user": {
            "email": user_email
        }
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    """Logout endpoint."""
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


@app.route("/api/signup", methods=["POST"])
def signup():
    """User signup endpoint."""
    try:
        # Check database connection first
        try:
            test_conn = engine.connect()
            test_conn.close()
        except Exception as e:
            return jsonify({
                "success": False,
                "detail": "Database is not available. Please start the database with: docker-compose up -d"
            }), 503

        data = request.json
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "detail": "Email and password are required"
            }), 400

        # Validate password length
        if len(password) < 8:
            return jsonify({
                "success": False,
                "detail": "Password must be at least 8 characters long"
            }), 400

        # Validate email format (basic check)
        if "@" not in email or "." not in email:
            return jsonify({
                "success": False,
                "detail": "Invalid email format"
            }), 400

        db = SessionLocal()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                return jsonify({
                    "success": False,
                    "detail": "Email already registered"
                }), 400

            # Hash password using bcrypt
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

            # Create new user
            new_user = User(
                email=email,
                password_hash=password_hash
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            # Set session
            session['user_email'] = email

            return jsonify({
                "success": True,
                "message": "User registered successfully",
                "redirect": "/"
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "detail": f"Error creating user: {str(e)}"
            }), 500
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "detail": f"Server error: {str(e)}"
        }), 500


@app.route("/api/login", methods=["POST"])
def login():
    """User login endpoint."""
    try:
        # Check database connection first
        try:
            test_conn = engine.connect()
            test_conn.close()
        except Exception as e:
            return jsonify({
                "success": False,
                "detail": "Database is not available. Please start the database with: docker-compose up -d"
            }), 503

        data = request.json
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "detail": "Email and password are required"
            }), 400

        db = SessionLocal()
        try:
            # Find user by email
            user = db.query(User).filter(User.email == email).first()

            if not user:
                return jsonify({
                    "success": False,
                    "detail": "Invalid email or password"
                }), 401

            # Verify password
            password_bytes = password.encode('utf-8')
            stored_hash_bytes = user.password_hash.encode('utf-8')

            if not bcrypt.checkpw(password_bytes, stored_hash_bytes):
                return jsonify({
                    "success": False,
                    "detail": "Invalid email or password"
                }), 401

            # Update last_login timestamp
            user.last_login = datetime.utcnow()
            db.commit()

            # Set session
            session['user_email'] = email

            return jsonify({
                "success": True,
                "message": "Login successful",
                "redirect": "/"
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "detail": f"Error during login: {str(e)}"
            }), 500
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "detail": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations", methods=["GET"])
@require_login
def get_conversations():
    """Get all conversations for the current user."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        db = SessionLocal()
        try:
            conversations = db.query(Chat).filter(
                Chat.email == user_email
            ).order_by(Chat.updated_at.desc()).all()
            
            result = []
            for conv in conversations:
                result.append({
                    "session_id": conv.session_id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                    "message_count": len(conv.messages) if conv.messages else 0
                })
            
            return jsonify({
                "success": True,
                "conversations": result
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "error": f"Error fetching conversations: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations", methods=["POST"])
@require_login
def create_conversation():
    """Create a new conversation."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        data = request.json or {}
        title = data.get("title", "New Chat")
        session_id = str(uuid.uuid4())
        
        db = SessionLocal()
        try:
            new_chat = Chat(
                email=user_email,
                session_id=session_id,
                title=title,
                messages=[]
            )
            
            db.add(new_chat)
            db.commit()
            db.refresh(new_chat)
            
            return jsonify({
                "success": True,
                "session_id": session_id,
                "title": title,
                "created_at": new_chat.created_at.isoformat() if new_chat.created_at else None
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "error": f"Error creating conversation: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations/<session_id>", methods=["GET"])
@require_login
def get_conversation(session_id):
    """Get a specific conversation with all messages."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if not chat:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found"
                }), 404
            
            # Ensure messages are properly formatted as a list
            messages = chat.messages if chat.messages else []
            # Convert to list if it's not already (JSONB might return dict-like structure)
            if not isinstance(messages, list):
                try:
                    import json
                    if isinstance(messages, str):
                        messages = json.loads(messages)
                    elif isinstance(messages, dict):
                        messages = list(messages.values()) if messages else []
                    else:
                        messages = list(messages) if messages else []
                except:
                    messages = []
            
            print(f"[DEBUG] Loading conversation {session_id}: {len(messages)} messages")
            for i, msg in enumerate(messages):
                print(f"  Message {i}: role={msg.get('role')}, content_length={len(str(msg.get('content', '')))}")
            
            return jsonify({
                "success": True,
                "session_id": chat.session_id,
                "title": chat.title,
                "messages": messages,
                "created_at": chat.created_at.isoformat() if chat.created_at else None,
                "updated_at": chat.updated_at.isoformat() if chat.updated_at else None
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Error fetching conversation: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations/<session_id>", methods=["PUT", "PATCH"])
@require_login
def update_conversation(session_id):
    """Update a conversation (e.g., rename title)."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        data = request.json or {}
        new_title = data.get("title", "").strip()
        
        if not new_title:
            return jsonify({
                "success": False,
                "error": "Title is required"
            }), 400
        
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if not chat:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found"
                }), 404
            
            chat.title = new_title
            chat.updated_at = datetime.utcnow()
            db.commit()
            
            return jsonify({
                "success": True,
                "message": "Conversation updated successfully",
                "title": new_title
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "error": f"Error updating conversation: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations/<session_id>", methods=["DELETE"])
@require_login
def delete_conversation(session_id):
    """Delete a conversation."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if not chat:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found"
                }), 404
            
            db.delete(chat)
            db.commit()
            
            # Clear STM for this session
            try:
                stm_clear_stm(session_id)
            except Exception as e:
                print(f"[WARNING] Could not clear STM for deleted conversation: {e}")
            
            return jsonify({
                "success": True,
                "message": "Conversation deleted successfully"
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "error": f"Error deleting conversation: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/conversations/<session_id>/messages", methods=["POST"])
@require_login
def add_message(session_id):
    """Add a message to a conversation."""
    try:
        user_email = session.get("user_email")
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        data = request.json
        role = data.get("role")  # "user" or "assistant"
        content = data.get("content", "")
        
        if not role or role not in ["user", "assistant"]:
            return jsonify({
                "success": False,
                "error": "Invalid role. Must be 'user' or 'assistant'"
            }), 400
        
        if not content:
            return jsonify({
                "success": False,
                "error": "Content is required"
            }), 400
        
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if not chat:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found"
                }), 404
            
            # Get current messages
            messages = list(chat.messages) if chat.messages else []
            
            # Add new message
            new_message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            messages.append(new_message)
            
            # Update chat
            # Use flag_modified to ensure SQLAlchemy detects the change
            from sqlalchemy.orm.attributes import flag_modified
            chat.messages = messages
            flag_modified(chat, "messages")
            chat.updated_at = datetime.utcnow()
            
            # Update title if this is the first user message
            if role == "user" and len(messages) == 1:
                # Use first 50 characters of user message as title
                chat.title = content[:50] + ("..." if len(content) > 50 else "")
            
            db.commit()
            
            return jsonify({
                "success": True,
                "message": "Message added successfully"
            })
        except Exception as e:
            db.rollback()
            return jsonify({
                "success": False,
                "error": f"Error adding message: {str(e)}"
            }), 500
        finally:
            db.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/travel-plan", methods=["GET"])
@require_login
def get_travel_plan():
    """Return all saved travel plan items for the given session."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({
            "success": False,
            "error": "session_id is required"
        }), 400

    user_email = session.get("user_email")
    db = SessionLocal()
    try:
        items = db.query(TravelPlanItem).filter(
            TravelPlanItem.email == user_email,
            TravelPlanItem.session_id == session_id
        ).order_by(TravelPlanItem.created_at.asc()).all()

        serialized_items = [serialize_plan_item(item) for item in items]
        print(f"[API] Travel plan request - session_id: {session_id[:8]}..., user: {user_email}, found {len(serialized_items)} items")
        return jsonify({
            "success": True,
            "session_id": session_id,
            "count": len(serialized_items),
            "items": serialized_items
        })
    except Exception as e:
        print(f"[ERROR] Could not fetch travel plan items: {e}")
        return jsonify({
            "success": False,
            "error": "Unable to retrieve travel plan items"
        }), 500
    finally:
        db.close()


@app.route("/api/travel-plan", methods=["DELETE"])
@require_login
def delete_travel_plan_item():
    """Delete a travel plan item."""
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "error": "Request body is required"
        }), 400
    
    session_id = data.get("session_id")
    title = data.get("title")
    
    if not session_id or not title:
        return jsonify({
            "success": False,
            "error": "session_id and title are required"
        }), 400

    user_email = session.get("user_email")
    db = SessionLocal()
    try:
        item = db.query(TravelPlanItem).filter(
            TravelPlanItem.email == user_email,
            TravelPlanItem.session_id == session_id,
            TravelPlanItem.title == title
        ).first()
        
        if not item:
            return jsonify({
                "success": False,
                "error": f"Plan item '{title}' not found"
            }), 404
        
        db.delete(item)
        db.commit()
        
        print(f"[API] Deleted plan item - session_id: {session_id[:8]}..., title: {title}, user: {user_email}")
        return jsonify({
            "success": True,
            "message": f"Successfully deleted plan item: {title}"
        })
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Could not delete travel plan item: {e}")
        return jsonify({
            "success": False,
            "error": f"Unable to delete travel plan item: {str(e)}"
        }), 500
    finally:
        db.close()


@app.route("/api/book-hotel", methods=["POST"])
@require_login
def book_hotel():
    """Secure booking endpoint - processes hotel booking with payment info."""
    try:
        data = request.json
        user_email = session.get("user_email")
        
        if not user_email:
            return jsonify({"error": True, "error_message": "Not authenticated"}), 401
        
        # Import MCP client to call booking tool
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root / "mcp_system" / "clients"))
        
        from hotel_agent_client import HotelAgentClient
        import asyncio
        
        # Call booking tool via MCP
        async def make_booking():
            return await HotelAgentClient.invoke("book_hotel_room", **data)
        
        booking_result = asyncio.run(make_booking())
        
        return jsonify(booking_result)
        
    except Exception as e:
        return jsonify({
            "error": True,
            "error_message": f"Booking failed: {str(e)}"
        }), 500


@app.route("/api/chat", methods=["POST"])
@require_login
def chat():
    """Handle chat requests - memory is now handled by the memory node in LangGraph."""
    try:
        data = request.json
        user_message = data.get("message", "")
        session_id = data.get("session_id")  # Get session_id from request
        user_email = session.get("user_email")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        # Emit start of processing
        emit_agent_activity("search", "Processing your request...", "Analyzing your query")
        
        # If no session_id provided, create a new conversation
        db = SessionLocal()
        try:
            if not session_id:
                # Create new conversation
                session_id = str(uuid.uuid4())
                new_chat = Chat(
                    email=user_email,
                    session_id=session_id,
                    title=user_message[:50] + ("..." if len(user_message) > 50 else ""),
                    messages=[]
                )
                db.add(new_chat)
                db.commit()
            else:
                # Verify conversation exists and belongs to user
                chat = db.query(Chat).filter(
                    Chat.email == user_email,
                    Chat.session_id == session_id
                ).first()
                if not chat:
                    return jsonify({"error": "Conversation not found"}), 404
        finally:
            db.close()
        
        # Save user message to conversation
        db = SessionLocal()
        try:
            add_message_response = add_message(session_id)
            # Note: add_message is a route function, we need to call it differently
            # Let's do it directly here
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if chat:
                messages = list(chat.messages) if chat.messages else []
                messages.append({
                    "role": "user",
                    "content": user_message,
                    "timestamp": datetime.utcnow().isoformat()
                })
                # Use flag_modified to ensure SQLAlchemy detects the change
                from sqlalchemy.orm.attributes import flag_modified
                chat.messages = messages
                flag_modified(chat, "messages")
                chat.updated_at = datetime.utcnow()
                
                # Update title if this is the first message
                if len(messages) == 1:
                    chat.title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                
                db.commit()
                print(f"[DEBUG] Saved user message to conversation {session_id}, total messages: {len(messages)}")
                
                # Add to STM
                try:
                    stm_add_message(session_id, user_email, "user", user_message)
                except Exception as e:
                    print(f"[WARNING] Could not add user message to STM: {e}")
        except Exception as e:
            print(f"[WARNING] Could not save user message: {e}")
        finally:
            db.close()
        
        # Memory operations are now handled by the memory_agent in LangGraph
        # Just pass user_email - the memory node will handle retrieval and storage
        print(f"[FLASK] Running LangGraph with user_email: {user_email}, session_id: {session_id}")
        
        # Capture stdout to emit agent activities
        log_capture = LogCapture()
        old_stdout = sys.stdout
        sys.stdout = log_capture
        
        # Track interaction start time
        interaction_start_time = time.time()
        
        try:
            result = run_async(run(
                user_message=user_message,
                user_email=user_email,
                session_id=session_id
            ))
        finally:
            sys.stdout = old_stdout
        
        response = result.get("last_response", "No response generated")
        agents_called = result.get("agents_called", [])
        
        # Calculate interaction latency
        interaction_latency_ms = (time.time() - interaction_start_time) * 1000
        
        # Log user interaction
        try:
            # Import agent_logger from langraph
            from pathlib import Path
            langraph_path = Path(__file__).parent.parent / "langraph"
            sys.path.insert(0, str(langraph_path))
            from agent_logger import log_interaction
            
            # Extract token usage if available (would need to be passed from graph)
            token_usage = None  # Could be extracted from result if available
            
            log_interaction(
                session_id=session_id,
                user_email=user_email,
                user_message=user_message,
                agent_response=response,
                latency_ms=interaction_latency_ms,
                token_usage=token_usage
            )
        except Exception as e:
            print(f"[WARNING] Could not log interaction: {e}")
        
        # Emit completion
        emit_agent_activity("success", "Response ready!", "All agents completed")
        
        # Save agent response to conversation
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(
                Chat.email == user_email,
                Chat.session_id == session_id
            ).first()
            
            if chat:
                messages = list(chat.messages) if chat.messages else []
                messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.utcnow().isoformat()
                })
                # Use flag_modified to ensure SQLAlchemy detects the change
                from sqlalchemy.orm.attributes import flag_modified
                chat.messages = messages
                flag_modified(chat, "messages")
                chat.updated_at = datetime.utcnow()
                db.commit()
                print(f"[DEBUG] Saved assistant message to conversation {session_id}, total messages: {len(messages)}")
                
                # Add to STM
                try:
                    stm_add_message(session_id, user_email, "agent", response)
                except Exception as e:
                    print(f"[WARNING] Could not add agent message to STM: {e}")
        except Exception as e:
            print(f"[WARNING] Could not save agent response: {e}")
        finally:
            db.close()
        
        emit_agent_activity("success", "Response ready!", "Processing complete")
        
        return jsonify({
            "response": response,
            "agents_called": agents_called,
            "session_id": session_id
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        emit_agent_activity("error", "An error occurred", str(e)[:100])
        # Make sure we always return JSON, not HTML
        return jsonify({"error": error_msg, "details": "An error occurred processing your request"}), 500


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    print(f"[WEBSOCKET] Client connected")
    

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    print(f"[WEBSOCKET] Client disconnected")


def emit_agent_activity(activity_type, message, details=None):
    """Emit agent activity to connected clients."""
    try:
        # Only emit if we're in a request context and during chat endpoint
        from flask import has_request_context, request
        if has_request_context() and request and hasattr(request, 'endpoint'):
            # Only emit during /api/chat requests to avoid WSGI conflicts
            if request.endpoint == 'chat':
                socketio.emit('agent_activity', {
                    'type': activity_type,
                    'message': message,
                    'details': details
                }, namespace='/')
    except Exception:
        # Silently fail to avoid WSGI errors
        pass


class LogCapture:
    """Capture print statements and convert them to WebSocket emissions."""
    
    def __init__(self):
        self.logs = []
        
    def write(self, text):
        if text.strip():
            self.logs.append(text)
            # Parse and emit agent activities (only if in request context and not during error handling)
            try:
                from flask import has_request_context, request
                if has_request_context() and request and hasattr(request, 'endpoint'):
                    # Only emit during /api/chat requests, not during other endpoints
                    if request.endpoint == 'chat':
                        self._parse_and_emit(text)
            except:
                pass  # Silently fail to avoid WSGI errors
        sys.__stdout__.write(text)
    
    def flush(self):
        sys.__stdout__.flush()
    
    def _parse_and_emit(self, text):
        """Parse log text and emit relevant activities."""
        text = text.strip()
        
        # Memory agent
        if "MEMORY AGENT STARTED" in text:
            emit_agent_activity("analyzing", "Checking your memory...", "Retrieving relevant context")
        elif "memories retrieved" in text.lower():
            count = self._extract_number(text, "memories retrieved")
            if count:
                emit_agent_activity("analyzing", f"Found {count} relevant memories", "Using your past preferences")
        
        # Flight agent
        elif "FLIGHT AGENT STARTED" in text:
            emit_agent_activity("flight", "Searching for flights...", "Checking available airlines")
        elif "FLIGHT AGENT COMPLETED" in text:
            duration = self._extract_duration(text)
            emit_agent_activity("flight", "Flight search completed", f"Found options in {duration}")
        
        # Hotel agent
        elif "HOTEL AGENT STARTED" in text:
            emit_agent_activity("hotel", "Searching for hotels...", "Finding accommodations")
        elif "HOTEL AGENT COMPLETED" in text:
            emit_agent_activity("hotel", "Hotel search completed", "Found accommodation options")
        
        # Visa agent
        elif "VISA AGENT STARTED" in text:
            emit_agent_activity("visa", "Checking visa requirements...", "Getting documentation info")
        elif "VISA AGENT COMPLETED" in text:
            emit_agent_activity("visa", "Visa information retrieved", "Requirements ready")
        
        # TripAdvisor agent
        elif "TRIPADVISOR AGENT STARTED" in text:
            emit_agent_activity("attractions", "Finding attractions...", "Searching local recommendations")
        elif "TRIPADVISOR AGENT COMPLETED" in text:
            emit_agent_activity("attractions", "Attractions found", "Got recommendations")
        
        # Main agent
        elif "Main Agent: Created Execution Plan" in text:
            emit_agent_activity("analyzing", "Creating execution plan...", "Planning which agents to use")
        
        # Plan executor
        elif "Plan Executor: Executing step" in text and "/1" in text:
            emit_agent_activity("search", "Starting agent execution...", "Processing your request")
    
    def _extract_number(self, text, keyword):
        """Extract number before keyword."""
        try:
            idx = text.lower().find(keyword.lower())
            if idx > 0:
                # Look backwards for number
                for i in range(idx-1, max(0, idx-20), -1):
                    if text[i:idx].strip().split()[-1].isdigit():
                        return text[i:idx].strip().split()[-1]
        except:
            pass
        return None
    
    def _extract_duration(self, text):
        """Extract duration from text like '(3.95s)' or '(Duration: 3.872s)'."""
        import re
        match = re.search(r'\((?:Duration: )?(\d+\.\d+)s\)', text)
        if match:
            return f"{match.group(1)}s"
        return "a moment"


if __name__ == "__main__":
    # Disable reloader to prevent issues with ML model loading
    # The model is pre-loaded at startup, so reloader isn't needed
    # Bind to 0.0.0.0 to allow access from outside the container
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

