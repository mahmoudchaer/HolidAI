"""Simple Flask UI for LangGraph travel agent."""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import secrets
from sqlalchemy import create_engine, Column, String, DateTime, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import bcrypt

# Add langraph and project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "langraph"))
sys.path.insert(0, str(project_root))

from graph import run

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


# Database connection - use 127.0.0.1 instead of localhost to avoid IPv6 issues
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@127.0.0.1:5433/myproject"
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

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a secret key for sessions
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


def require_login(f):
    """Decorator to require login for routes."""
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route("/")
@require_login
def index():
    """Serve the main UI page (requires login)."""
    return render_template("index.html", user_email=session.get('user_email'))


@app.route("/signup")
def signup_page():
    """Serve the signup page."""
    # If already logged in, redirect to main page
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template("signup.html")


@app.route("/login")
def login_page():
    """Serve the login page."""
    # If already logged in, redirect to main page
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template("login.html")


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


@app.route("/api/chat", methods=["POST"])
@require_login
def chat():
    """Handle chat requests - memory is now handled by the memory node in LangGraph."""
    try:
        data = request.json
        user_message = data.get("message", "")
        user_email = session.get("user_email")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
        
        # Memory operations are now handled by the memory_node in LangGraph
        # Just pass user_email - the memory node will handle retrieval and storage
        print(f"[FLASK] Running LangGraph with user_email: {user_email}")
        result = run_async(run(
            user_message=user_message,
            user_email=user_email
        ))
        
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
        # Make sure we always return JSON, not HTML
        return jsonify({"error": error_msg, "details": "An error occurred processing your request"}), 500


if __name__ == "__main__":
    # Disable reloader to prevent issues with ML model loading
    # The model is pre-loaded at startup, so reloader isn't needed
    app.run(debug=True, port=5000, use_reloader=False)

