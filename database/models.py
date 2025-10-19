"""
Database models for HolidAI hotel booking system.
Uses SQLAlchemy ORM for easy database management.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database configuration
DATABASE_URL = "sqlite:///holidai.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User model for authentication and profile management."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="user")
    preferences = relationship("UserPreference", back_populates="user")


class Hotel(Base):
    """Hotel model for caching hotel data."""
    __tablename__ = "hotels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    overall_rating = Column(Float, nullable=True)
    hotel_class = Column(Integer, nullable=True)
    reviews_count = Column(Integer, default=0)
    amenities = Column(Text, nullable=True)  # JSON string
    images = Column(Text, nullable=True)  # JSON string
    description = Column(Text, nullable=True)
    check_in_time = Column(String(20), nullable=True)
    check_out_time = Column(String(20), nullable=True)
    cancellation_policy = Column(Text, nullable=True)
    pet_friendly = Column(Boolean, default=False)
    free_wifi = Column(Boolean, default=False)
    parking = Column(Boolean, default=False)
    pool = Column(Boolean, default=False)
    gym = Column(Boolean, default=False)
    restaurant = Column(Boolean, default=False)
    spa = Column(Boolean, default=False)
    business_center = Column(Boolean, default=False)
    airport_shuttle = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="hotel")


class Booking(Base):
    """Booking model for storing hotel reservations."""
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(String(50), unique=True, index=True, nullable=False)
    confirmation_number = Column(String(100), unique=True, index=True, nullable=False)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=True)  # Nullable for external hotels
    
    # Booking details
    hotel_name = Column(String(255), nullable=False)
    hotel_address = Column(Text, nullable=True)
    hotel_phone = Column(String(50), nullable=True)
    hotel_rating = Column(Float, nullable=True)
    hotel_class = Column(Integer, nullable=True)
    
    # Dates and guests
    check_in_date = Column(DateTime, nullable=False)
    check_out_date = Column(DateTime, nullable=False)
    nights = Column(Integer, nullable=False)
    guests = Column(Integer, nullable=False)
    room_type = Column(String(50), nullable=False)
    
    # Guest information
    guest_name = Column(String(200), nullable=False)
    guest_email = Column(String(255), nullable=False)
    guest_phone = Column(String(20), nullable=True)
    special_requests = Column(Text, nullable=True)
    dietary_requirements = Column(Text, nullable=True)
    accessibility_needs = Column(Text, nullable=True)
    
    # Pricing
    rate_per_night = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    taxes = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    
    # Status and policies
    status = Column(String(50), default="confirmed")  # confirmed, cancelled, modified
    cancellation_policy = Column(Text, nullable=True)
    check_in_instructions = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    hotel = relationship("Hotel", back_populates="bookings")


class UserPreference(Base):
    """User preferences for personalized recommendations."""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Preferences
    preferred_hotel_chains = Column(Text, nullable=True)  # JSON string
    preferred_amenities = Column(Text, nullable=True)  # JSON string
    budget_range_min = Column(Float, nullable=True)
    budget_range_max = Column(Float, nullable=True)
    preferred_room_types = Column(Text, nullable=True)  # JSON string
    preferred_locations = Column(Text, nullable=True)  # JSON string
    loyalty_programs = Column(Text, nullable=True)  # JSON string
    
    # Travel preferences
    travel_style = Column(String(50), nullable=True)  # business, leisure, family, luxury
    accessibility_needs = Column(Text, nullable=True)
    dietary_preferences = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="preferences")


class SearchHistory(Base):
    """Search history for analytics and recommendations."""
    __tablename__ = "search_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for anonymous users
    
    # Search parameters
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=True)
    check_in_date = Column(DateTime, nullable=True)
    check_out_date = Column(DateTime, nullable=True)
    guests = Column(Integer, nullable=True)
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    rating_min = Column(Float, nullable=True)
    amenities = Column(Text, nullable=True)  # JSON string
    
    # Results
    results_count = Column(Integer, nullable=True)
    search_duration = Column(Float, nullable=True)  # Time in seconds
    
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_session():
    """Get a database session for operations."""
    return SessionLocal()


def init_database():
    """Initialize the database with tables."""
    create_tables()
    print("HolidAI database initialized!")


if __name__ == "__main__":
    init_database()
