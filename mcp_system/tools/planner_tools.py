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


def _sanitize_unicode_data(data):
    """Recursively sanitize Unicode characters in data structures to prevent PostgreSQL errors.
    
    This function:
    - Removes null bytes (\u0000) which PostgreSQL cannot handle
    - Ensures all strings are properly encoded
    - Fixes any invalid Unicode escape sequences
    - Handles corrupted Unicode sequences like \u0000f6 -> \u00f6
    """
    if isinstance(data, dict):
        return {k: _sanitize_unicode_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_unicode_data(item) for item in data]
    elif isinstance(data, str):
        # Remove null bytes which PostgreSQL cannot handle
        # Also fix corrupted Unicode sequences like \u0000f6 -> \u00f6
        cleaned = data
        
        # Remove null bytes (most critical - PostgreSQL cannot handle these)
        if '\x00' in cleaned:
            cleaned = cleaned.replace('\x00', '')
        
        # Fix corrupted Unicode escape sequences in JSON strings
        # Pattern: \u0000 followed by hex digits should be \u00XX
        import re
        # This pattern matches \u0000 followed by exactly 2 hex digits
        pattern = r'\\u0000([0-9a-fA-F]{2})'
        def fix_unicode_escape(match):
            hex_part = match.group(1)
            return f'\\u00{hex_part}'
        cleaned = re.sub(pattern, fix_unicode_escape, cleaned)
        
        # Ensure it's valid UTF-8
        try:
            # Try encoding to ensure it's valid
            cleaned.encode('utf-8')
            return cleaned
        except (UnicodeEncodeError, UnicodeDecodeError):
            # If encoding fails, try to fix it by removing problematic characters
            try:
                cleaned = cleaned.encode('utf-8', errors='replace').decode('utf-8')
                return cleaned
            except Exception:
                # Last resort: return a safe string
                return cleaned if isinstance(cleaned, str) else str(cleaned)
    else:
        return data


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
            # Sanitize Unicode characters to prevent PostgreSQL errors
            details = _sanitize_unicode_data(details)
            # Also sanitize title to prevent any issues
            if isinstance(title, str):
                title = title.replace('\x00', '')
            
            # Round-trip through JSON to ensure proper encoding before storing in PostgreSQL
            # This catches any remaining encoding issues
            try:
                details_json = json.dumps(details, ensure_ascii=False)
                details = json.loads(details_json)
            except (TypeError, ValueError, UnicodeEncodeError) as e:
                print(f"[WARNING] JSON round-trip failed, using sanitized data directly: {e}")
                # If JSON round-trip fails, use the sanitized data as-is
            
            normalized_key = generate_normalized_key(details, type, title)

            db = SessionLocal()
            try:
                # Check if item already exists by normalized_key
                existing = db.query(TravelPlanItem).filter(
                    TravelPlanItem.email == user_email,
                    TravelPlanItem.session_id == session_id,
                    TravelPlanItem.normalized_key == normalized_key
                ).first()
                
                # For hotels: Also check if same hotel exists (by name and location) even if normalized_key differs
                # This handles cases where hotel is added first without room details, then with room details
                if type == "hotel" and not existing:
                    hotel_name = details.get("name") or details.get("hotel_name", "").lower().strip()
                    hotel_location = (details.get("location") or details.get("address", "")).lower().strip()
                    if hotel_name:
                        # Find existing hotels with same name and location
                        all_hotels = db.query(TravelPlanItem).filter(
                            TravelPlanItem.email == user_email,
                            TravelPlanItem.session_id == session_id,
                            TravelPlanItem.type == "hotel"
                        ).all()
                        for hotel_item in all_hotels:
                            existing_name = (hotel_item.details.get("name") or hotel_item.details.get("hotel_name", "")).lower().strip()
                            existing_location = (hotel_item.details.get("location") or hotel_item.details.get("address", "")).lower().strip()
                            if hotel_name == existing_name and (not hotel_location or not existing_location or hotel_location == existing_location):
                                existing = hotel_item
                                print(f"[PLANNER TOOL] Found existing hotel '{hotel_name}' - will merge room details")
                                break
                
                if existing:
                    # Merge/update existing item
                    # For hotels: If new details have room info (check_in, check_out, price) and existing doesn't, merge them
                    if type == "hotel" and existing.type == "hotel":
                        existing_details = existing.details or {}
                        # Merge room details if new details have them
                        if details.get("check_in") and not existing_details.get("check_in"):
                            existing_details["check_in"] = details.get("check_in")
                        if details.get("check_out") and not existing_details.get("check_out"):
                            existing_details["check_out"] = details.get("check_out")
                        if (details.get("price_total") or details.get("price")) and not (existing_details.get("price_total") or existing_details.get("price")):
                            if details.get("price_total"):
                                existing_details["price_total"] = details.get("price_total")
                            if details.get("price"):
                                existing_details["price"] = details.get("price")
                        if details.get("room_type") or details.get("roomType"):
                            existing_details["room_type"] = details.get("room_type") or details.get("roomType")
                        if details.get("board"):
                            existing_details["board"] = details.get("board")
                        if details.get("currency"):
                            existing_details["currency"] = details.get("currency")
                        # Merge other fields
                        for key, value in details.items():
                            if key not in existing_details or not existing_details[key]:
                                existing_details[key] = value
                        details = existing_details
                        print(f"[PLANNER TOOL] Merged room details into existing hotel")
                    
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
                    db.refresh(new_item)  # Ensure the item is fully committed
                    print(f"[PLANNER TOOL] ✓ Successfully added plan item to database: {title} (session_id: {session_id[:8]}..., email: {user_email})")
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
                    # Sanitize Unicode characters to prevent PostgreSQL errors
                    item.details = _sanitize_unicode_data(details)
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
                
                print(f"[PLANNER TOOL] Retrieved {len(items)} plan items from database (session_id: {session_id[:8]}..., email: {user_email})")
                
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

