"""Async database utilities for trip_plans table.

This module provides async functions to interact with the trip_plans table.
Uses SQLAlchemy (same as the rest of the project) with async wrappers.
"""

import os
import json
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Database connection - use same pattern as frontend/app.py
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@127.0.0.1:5433/myproject"
)

# Create engine (same as frontend/app.py)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _get_trip_plan_sync(email: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Synchronous function to get trip plan.
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        Trip plan dictionary with 'plan' (list of steps) and 'updated_at', or None if not found
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT plan, updated_at
                FROM trip_plans
                WHERE email = :email AND session_id = :session_id
            """),
            {"email": email, "session_id": session_id}
        )
        row = result.fetchone()
        
        if row:
            # Convert JSONB to Python dict/list
            plan = row[0]
            if isinstance(plan, str):
                plan = json.loads(plan)
            elif hasattr(plan, '__dict__'):
                # SQLAlchemy might return a custom type, convert to dict
                plan = dict(plan) if hasattr(plan, 'keys') else plan
            
            return {
                "plan": plan if isinstance(plan, list) else json.loads(plan) if isinstance(plan, str) else [],
                "updated_at": row[1].isoformat() if row[1] else None
            }
        return None
    except Exception as e:
        print(f"[ERROR] Error getting trip plan: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


def _upsert_trip_plan_sync(email: str, session_id: str, plan: List[Dict[str, Any]]) -> bool:
    """Synchronous function to insert or update trip plan.
    
    Args:
        email: User's email address
        session_id: Session identifier
        plan: List of trip plan steps (each step is a dict)
        
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        # Convert plan to JSON string for storage
        plan_json = json.dumps(plan)
        
        db.execute(
            text("""
                INSERT INTO trip_plans (email, session_id, plan, updated_at)
                VALUES (:email, :session_id, :plan::jsonb, NOW())
                ON CONFLICT (email, session_id)
                DO UPDATE SET
                    plan = :plan::jsonb,
                    updated_at = NOW()
            """),
            {"email": email, "session_id": session_id, "plan": plan_json}
        )
        db.commit()
        
        print(f"[TRIP_PLAN_DB] Upserted trip plan for {email}/{session_id} with {len(plan)} steps")
        return True
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error upserting trip plan: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def _clear_trip_plan_sync(email: str, session_id: str) -> bool:
    """Synchronous function to clear trip plan (set to empty array).
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO trip_plans (email, session_id, plan, updated_at)
                VALUES (:email, :session_id, '[]'::jsonb, NOW())
                ON CONFLICT (email, session_id)
                DO UPDATE SET
                    plan = '[]'::jsonb,
                    updated_at = NOW()
            """),
            {"email": email, "session_id": session_id}
        )
        db.commit()
        
        print(f"[TRIP_PLAN_DB] Cleared trip plan for {email}/{session_id}")
        return True
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error clearing trip plan: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


# Async wrappers using asyncio.to_thread
async def get_trip_plan(email: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get trip plan for a user and session (async wrapper).
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        Trip plan dictionary with 'plan' (list of steps) and 'updated_at', or None if not found
    """
    return await asyncio.to_thread(_get_trip_plan_sync, email, session_id)


async def upsert_trip_plan(email: str, session_id: str, plan: List[Dict[str, Any]]) -> bool:
    """Insert or update trip plan (async wrapper).
    
    Args:
        email: User's email address
        session_id: Session identifier
        plan: List of trip plan steps (each step is a dict)
        
    Returns:
        True if successful, False otherwise
    """
    return await asyncio.to_thread(_upsert_trip_plan_sync, email, session_id, plan)


async def clear_trip_plan(email: str, session_id: str) -> bool:
    """Clear trip plan (set to empty array) (async wrapper).
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        True if successful, False otherwise
    """
    return await asyncio.to_thread(_clear_trip_plan_sync, email, session_id)
