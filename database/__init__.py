"""
Database initialization and connection management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, DATABASE_URL
import os


def init_database():
    """Initialize the database with all tables."""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL, echo=False)
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("✅ HolidAI database initialized successfully!")
        print(f"📁 Database file: holidai.db")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        return False


def get_database_session():
    """Get a database session for operations."""
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def check_database_exists():
    """Check if database file exists."""
    return os.path.exists("holidai.db")


def get_database_info():
    """Get database information."""
    if check_database_exists():
        file_size = os.path.getsize("holidai.db")
        return {
            "exists": True,
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }
    else:
        return {"exists": False}


if __name__ == "__main__":
    init_database()
