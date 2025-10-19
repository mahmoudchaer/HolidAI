"""
Authentication tools for user management.
Handles user registration, login, and session management.
"""

from typing import Optional, Dict, Any
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from database.models import User, get_database_session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import os
import secrets

# Password hashing
import hashlib
import base64

def hash_password(password: str) -> str:
    """Simple password hashing using SHA-256."""
    # Truncate password to 50 characters to avoid issues
    password = password[:50]
    # Add salt
    salt = "holidai_salt_2024"
    # Hash password with salt
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    password = password[:50]  # Truncate to match
    salt = "holidai_salt_2024"
    test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return test_hash == hashed

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def register_user_function(email: str, username: str, password: str, first_name: str, last_name: str, phone: str = "") -> Dict[str, Any]:
    """
    Register a new user account (Flask route function).
    
    Args:
        email: User email address
        username: Username
        password: Plain text password
        first_name: User's first name
        last_name: User's last name
        phone: User's phone number (optional)
    
    Returns:
        Registration result with user info or error
    """
    try:
        db = get_database_session()
        
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            db.close()
            return {"error": "User with this email or username already exists"}
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Create new user
        new_user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Generate access token
        access_token = create_access_token(data={"sub": new_user.email})
        
        db.close()
        
        return {
            "success": True,
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "phone": new_user.phone,
                "created_at": new_user.created_at.isoformat()
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        return {"error": f"Registration failed: {str(e)}"}


def authenticate_user_function(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate user login (Flask route function).
    
    Args:
        email: User email address
        password: Plain text password
    
    Returns:
        Authentication result with user info and token or error
    """
    try:
        db = get_database_session()
        
        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            db.close()
            return {"error": "Invalid email or password"}
        
        # Check password
        if not verify_password(password, user.hashed_password):
            db.close()
            return {"error": "Invalid email or password"}
        
        # Check if user is active
        if not user.is_active:
            db.close()
            return {"error": "Account is deactivated"}
        
        # Generate access token
        access_token = create_access_token(data={"sub": user.email})
        
        db.close()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "created_at": user.created_at.isoformat()
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        return {"error": f"Authentication failed: {str(e)}"}


def get_user_by_email_function(email: str) -> Dict[str, Any]:
    """
    Get user information by email (Flask route function).
    
    Args:
        email: User email address
    
    Returns:
        User information or error
    """
    try:
        db = get_database_session()
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            db.close()
            return {"error": "User not found"}
        
        db.close()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat()
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to get user: {str(e)}"}


def update_user_profile_function(email: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user profile information (Flask route function).
    
    Args:
        email: User email address
        updates: Dictionary with fields to update
    
    Returns:
        Update result with updated user info or error
    """
    try:
        db = get_database_session()
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            db.close()
            return {"error": "User not found"}
        
        # Update allowed fields
        allowed_fields = ["first_name", "last_name", "phone"]
        
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(user)
        db.close()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "updated_at": user.updated_at.isoformat()
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to update profile: {str(e)}"}


# LangChain tools for agent use
@tool
def register_user(email: str, username: str, password: str, first_name: str, last_name: str, phone: str = "") -> Dict[str, Any]:
    """
    Register a new user account.
    
    Args:
        email: User email address
        username: Username
        password: Plain text password
        first_name: User's first name
        last_name: User's last name
        phone: User's phone number (optional)
    
    Returns:
        Registration result with user info or error
    """
    return register_user_function(email, username, password, first_name, last_name, phone)


@tool
def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate user login.
    
    Args:
        email: User email address
        password: Plain text password
    
    Returns:
        Authentication result with user info and token or error
    """
    return authenticate_user_function(email, password)


@tool
def get_user_by_email(email: str) -> Dict[str, Any]:
    """
    Get user information by email.
    
    Args:
        email: User email address
    
    Returns:
        User information or error
    """
    return get_user_by_email_function(email)


@tool
def update_user_profile(email: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user profile information.
    
    Args:
        email: User email address
        updates: Dictionary with fields to update
    
    Returns:
        Update result with updated user info or error
    """
    return update_user_profile_function(email, updates)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return {"email": email}
    except jwt.PyJWTError:
        return None


def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    """Get current user from token."""
    credentials_exception = {"error": "Could not validate credentials"}
    
    try:
        payload = verify_token(token)
        if payload is None:
            return credentials_exception
        
        email = payload["email"]
        user_result = get_user_by_email_function(email)
        
        if "error" in user_result:
            return credentials_exception
        
        return user_result["user"]
        
    except Exception:
        return credentials_exception