"""Planner-related tools for the MCP server."""

import sys
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

from sqlalchemy import create_engine, Column, String, DateTime, func, JSON, UniqueConstraint
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.dialects.postgresql import JSONB

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@127.0.0.1:5437/myproject"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class TravelPlanItem(Base):
    """Travel plan item model."""
    __tablename__ = "travel_plan_items"
    __table_args__ = (
        UniqueConstraint("email", "session_id", "normalized_key", name="uq_travel_plan_normalized"),
    )

    email = Column(String, primary_key=True)
    session_id = Column(String, primary_key=True)
    title = Column(String, primary_key=True)
    details = Column(JSONB, nullable=False, default=dict)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default='not_booked')
    normalized_key = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def _canonicalize_value(value):
    """Recursively normalize values for key generation."""
    if isinstance(value, dict):
        return {k: _canonicalize_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalize_value(v) for v in value]
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _fingerprint_title(title: str) -> str:
    """Create a lightweight fingerprint of the provided title."""
    if not title:
        return ""
    import re

    cleaned = re.sub(r"[^a-z0-9]", "", title.strip().lower())
    return cleaned


def generate_normalized_key(details: Optional[Dict], item_type: str, title: str = "") -> str:
    """Generate deterministic key for plan items."""
    canonical_details = _canonicalize_value(details or {})
    payload = {
        "type": (item_type or "").strip().lower(),
        "details": canonical_details,
    }
    if not canonical_details:
        payload["title_fingerprint"] = _fingerprint_title(title)

    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def backfill_normalized_keys():
    """Populate normalized keys for legacy rows."""
    try:
        db = SessionLocal()
        items = db.query(TravelPlanItem).filter(
            (TravelPlanItem.normalized_key == None) | (TravelPlanItem.normalized_key == "")
        ).all()
        updated = 0
        for item in items:
            item.normalized_key = generate_normalized_key(item.details, item.type, item.title)
            updated += 1
        if updated:
            db.commit()
            print(f"[PLANNER] Backfilled normalized keys for {updated} travel plan item(s)")
    except Exception as exc:
        print(f"[PLANNER] Warning: could not backfill normalized keys: {exc}")
    finally:
        try:
            db.close()
        except Exception:
            pass


# Initialize database tables (only if database is available)
def init_planner_tables():
    """Initialize planner database tables if database is available."""
    try:
        Base.metadata.create_all(bind=engine)
        print("[PLANNER] ✓ Database tables initialized successfully")
    except Exception as e:
        print(f"[PLANNER] ⚠ Warning: Could not connect to database: {e}")
        print("  Planner features will be unavailable until database is started.")
        print("  To start database: docker-compose up -d")

# Try to initialize tables on import (non-blocking)
try:
    init_planner_tables()
    backfill_normalized_keys()
except Exception as e:
    print(f"[PLANNER] Could not initialize tables on import: {e}")


def register_planner_tools(mcp):
    """Register all planner-related tools with the MCP server."""
    
    @mcp.tool(description="Add a new item to the travel plan. Use this when the user wants to save/select a flight, hotel, or other travel option.")
    def agent_add_plan_item_tool(user_email: str, session_id: str, title: str, details: Dict, type: str, status: str = "not_booked") -> Dict:
        """Add a new item to the travel plan.
        
        Args:
            user_email: User's email address
            session_id: Session identifier
            title: Title/name of the plan item (e.g., "Flight to Paris", "Hotel in Dubai")
            details: JSON object containing all details about the item (flight details, hotel info, etc.)
            type: Type of item (e.g., "flight", "hotel", "visa", "restaurant", "activity")
            status: Status of the item (default: "not_booked", "booked", "cancelled")
        
        Returns:
            Dictionary with success status and message
        """
        try:
            # Try to create table if it doesn't exist (retry mechanism)
            try:
                Base.metadata.create_all(bind=engine)
            except:
                pass  # Table might already exist
            
            details = details or {}
            normalized_key = generate_normalized_key(details, type, title)

            db = SessionLocal()
            try:
                # Check if item already exists
                existing = db.query(TravelPlanItem).filter(
                    TravelPlanItem.email == user_email,
                    TravelPlanItem.session_id == session_id,
                    TravelPlanItem.normalized_key == normalized_key
                ).first()
                
                if existing:
                    # Update existing item
                    existing.details = details
                    existing.type = type
                    existing.status = status
                    existing.title = title
                    existing.normalized_key = normalized_key
                    existing.updated_at = datetime.utcnow()
                    db.commit()
                    return {
                        "success": True,
                        "message": f"Updated existing plan item: {title}",
                        "action": "updated"
                    }
                else:
                    # Create new item
                    new_item = TravelPlanItem(
                        email=user_email,
                        session_id=session_id,
                        title=title,
                        details=details,
                        type=type,
                        status=status,
                        normalized_key=normalized_key
                    )
                    db.add(new_item)
                    db.commit()
                    return {
                        "success": True,
                        "message": f"Successfully added plan item: {title}",
                        "action": "added"
                    }
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
        except Exception as e:
            print(f"[ERROR] Error adding plan item: {e}")
            return {
                "success": False,
                "message": f"Error adding plan item: {str(e)}"
            }
    
    @mcp.tool(description="Update an existing travel plan item. Use this when the user wants to modify details or status of a saved item.")
    def agent_update_plan_item_tool(user_email: str, session_id: str, title: str, details: Optional[Dict] = None, status: Optional[str] = None) -> Dict:
        """Update an existing travel plan item.
        
        Args:
            user_email: User's email address
            session_id: Session identifier
            title: Title of the plan item to update
            details: Optional new details to update (if None, keeps existing)
            status: Optional new status to update (if None, keeps existing)
        
        Returns:
            Dictionary with success status and message
        """
        try:
            # Try to create table if it doesn't exist (retry mechanism)
            try:
                Base.metadata.create_all(bind=engine)
            except:
                pass  # Table might already exist
            
            db = SessionLocal()
            try:
                item = db.query(TravelPlanItem).filter(
                    TravelPlanItem.email == user_email,
                    TravelPlanItem.session_id == session_id,
                    TravelPlanItem.title == title
                ).first()
                
                if not item:
                    return {
                        "success": False,
                        "message": f"Plan item '{title}' not found"
                    }
                
                if details is not None:
                    item.details = details
                if status is not None:
                    item.status = status

                # Recompute normalized key if details changed
                if details is not None:
                    item.normalized_key = generate_normalized_key(item.details, item.type, item.title)
                
                item.updated_at = datetime.utcnow()
                db.commit()
                
                return {
                    "success": True,
                    "message": f"Successfully updated plan item: {title}"
                }
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
        except Exception as e:
            print(f"[ERROR] Error updating plan item: {e}")
            return {
                "success": False,
                "message": f"Error updating plan item: {str(e)}"
            }
    
    @mcp.tool(description="Delete a travel plan item. Use this when the user wants to remove an item from their plan.")
    def agent_delete_plan_item_tool(user_email: str, session_id: str, title: str) -> Dict:
        """Delete a travel plan item.
        
        Args:
            user_email: User's email address
            session_id: Session identifier
            title: Title of the plan item to delete
        
        Returns:
            Dictionary with success status and message
        """
        try:
            # Try to create table if it doesn't exist (retry mechanism)
            try:
                Base.metadata.create_all(bind=engine)
            except:
                pass  # Table might already exist
            
            db = SessionLocal()
            try:
                item = db.query(TravelPlanItem).filter(
                    TravelPlanItem.email == user_email,
                    TravelPlanItem.session_id == session_id,
                    TravelPlanItem.title == title
                ).first()
                
                if not item:
                    return {
                        "success": False,
                        "message": f"Plan item '{title}' not found"
                    }
                
                db.delete(item)
                db.commit()
                
                return {
                    "success": True,
                    "message": f"Successfully deleted plan item: {title}"
                }
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
        except Exception as e:
            print(f"[ERROR] Error deleting plan item: {e}")
            return {
                "success": False,
                "message": f"Error deleting plan item: {str(e)}"
            }
    
    @mcp.tool(description="Retrieve all travel plan items for a session. Use this to get the current travel plan.")
    def agent_get_plan_items_tool(user_email: str, session_id: str, type: Optional[str] = None, status: Optional[str] = None) -> Dict:
        """Retrieve travel plan items for a session.
        
        Args:
            user_email: User's email address
            session_id: Session identifier
            type: Optional filter by type (e.g., "flight", "hotel")
            status: Optional filter by status (e.g., "not_booked", "booked")
        
        Returns:
            Dictionary with list of plan items
        """
        try:
            # Try to create table if it doesn't exist (retry mechanism)
            try:
                Base.metadata.create_all(bind=engine)
            except:
                pass  # Table might already exist
            
            db = SessionLocal()
            try:
                query = db.query(TravelPlanItem).filter(
                    TravelPlanItem.email == user_email,
                    TravelPlanItem.session_id == session_id
                )
                
                if type:
                    query = query.filter(TravelPlanItem.type == type)
                if status:
                    query = query.filter(TravelPlanItem.status == status)
                
                items = query.order_by(TravelPlanItem.created_at.desc()).all()
                
                result = []
                for item in items:
                    result.append({
                        "title": item.title,
                        "type": item.type,
                        "details": item.details,
                        "status": item.status,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                        "updated_at": item.updated_at.isoformat() if item.updated_at else None
                    })
                
                return {
                    "success": True,
                    "items": result,
                    "count": len(result)
                }
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
        except Exception as e:
            print(f"[ERROR] Error retrieving plan items: {e}")
            return {
                "success": False,
                "items": [],
                "count": 0,
                "message": f"Error retrieving plan items: {str(e)}"
            }

