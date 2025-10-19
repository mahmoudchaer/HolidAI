"""
Enhanced hotel booking tools with database integration.
"""

from typing import Dict, Any
from langchain_core.tools import tool
from datetime import datetime
import uuid
import json
from database.models import Booking, Hotel, User, get_database_session


@tool
def quick_book_hotel(hotel: Dict[str, Any], check_in_date: str, check_out_date: str, guests: int = 2, room_type: str = "Standard", guest_name: str = "", guest_email: str = "") -> Dict[str, Any]:
    """
    Quick booking process that handles everything in one step to prevent recursion.
    
    Args:
        hotel: Hotel property dictionary
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        guests: Number of guests
        room_type: Room type (Standard, Deluxe, Suite, etc.)
        guest_name: Guest name
        guest_email: Guest email
    
    Returns:
        Complete booking confirmation
    """
    # Validate dates
    try:
        check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
        check_out = datetime.strptime(check_out_date, "%Y-%m-%d")
        nights = (check_out - check_in).days
        
        if nights <= 0:
            return {"error": "Check-out date must be after check-in date"}
            
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}
    
    # Calculate pricing
    rate_per_night = hotel.get("rate_per_night", {}).get("extracted_lowest", 0)
    if not rate_per_night:
        rate_per_night = hotel.get("rate_per_night", {}).get("lowest", "0")
        try:
            rate_per_night = float(str(rate_per_night).replace("$", "").replace(",", ""))
        except:
            rate_per_night = 0
    
    # Room type pricing multipliers
    room_pricing = {
        "Standard": 1.0,
        "Deluxe": 1.3,
        "Suite": 1.8,
        "Executive": 2.2,
        "Presidential": 3.0
    }
    
    multiplier = room_pricing.get(room_type, 1.0)
    final_rate = rate_per_night * multiplier
    subtotal = final_rate * nights
    taxes = subtotal * 0.10
    total_cost = subtotal + taxes
    
    # Generate confirmation
    booking_id = str(uuid.uuid4())[:8].upper()
    confirmation_number = f"HTL-{booking_id}-{datetime.now().strftime('%Y%m%d')}"
    
    # Create complete booking
    booking = {
        "booking_id": booking_id,
        "confirmation_number": confirmation_number,
        "hotel": {
            "name": hotel.get("name", "Unknown Hotel"),
            "rating": hotel.get("overall_rating", 0),
            "class": hotel.get("hotel_class", 0),
            "amenities": hotel.get("amenities", [])[:5],
            "address": hotel.get("address", ""),
            "phone": hotel.get("phone", "")
        },
        "dates": {
            "check_in": check_in_date,
            "check_out": check_out_date,
            "nights": nights
        },
        "guests": guests,
        "room_type": room_type,
        "guest_info": {
            "name": guest_name or "Guest",
            "email": guest_email or "guest@email.com"
        },
        "pricing": {
            "rate_per_night": round(final_rate, 2),
            "subtotal": round(subtotal, 2),
            "taxes": round(taxes, 2),
            "total": round(total_cost, 2)
        },
        "status": "confirmed",
        "confirmed_at": datetime.now().isoformat(),
        "check_in_instructions": "Please arrive after 3:00 PM. Present this confirmation at check-in.",
        "cancellation_policy": "Free cancellation up to 24 hours before check-in."
    }
    
    return booking


@tool
def format_booking_confirmation(booking: Dict[str, Any]) -> str:
    """
    Format a booking confirmation in a clean, readable way.
    
    Args:
        booking: Booking dictionary
    
    Returns:
        Formatted booking confirmation string
    """
    if "error" in booking:
        return f"❌ **Booking Error:** {booking['error']}"
    
    hotel = booking["hotel"]
    dates = booking["dates"]
    pricing = booking["pricing"]
    guest_info = booking["guest_info"]
    
    confirmation = f"🎉 **Booking Confirmed!**\n\n"
    confirmation += f"**Confirmation #:** {booking['confirmation_number']}\n"
    confirmation += f"**Booking ID:** {booking['booking_id']}\n\n"
    
    confirmation += f"🏨 **Hotel Details:**\n"
    confirmation += f"• **Name:** {hotel['name']}\n"
    confirmation += f"• **Rating:** {hotel['rating']}/5 • {hotel['class']}-star\n"
    confirmation += f"• **Address:** {hotel['address']}\n"
    confirmation += f"• **Phone:** {hotel['phone']}\n\n"
    
    confirmation += f"📅 **Stay Details:**\n"
    confirmation += f"• **Check-in:** {dates['check_in']}\n"
    confirmation += f"• **Check-out:** {dates['check_out']}\n"
    confirmation += f"• **Nights:** {dates['nights']}\n"
    confirmation += f"• **Guests:** {booking['guests']}\n"
    confirmation += f"• **Room Type:** {booking['room_type']}\n\n"
    
    confirmation += f"👤 **Guest Information:**\n"
    confirmation += f"• **Name:** {guest_info['name']}\n"
    confirmation += f"• **Email:** {guest_info['email']}\n\n"
    
    confirmation += f"💰 **Pricing:**\n"
    confirmation += f"• **Rate per night:** ${pricing['rate_per_night']}\n"
    confirmation += f"• **Subtotal:** ${pricing['subtotal']}\n"
    confirmation += f"• **Taxes:** ${pricing['taxes']}\n"
    confirmation += f"• **Total:** ${pricing['total']}\n\n"
    
    confirmation += f"📋 **Important Information:**\n"
    confirmation += f"• {booking['check_in_instructions']}\n"
    confirmation += f"• {booking['cancellation_policy']}\n"
    
    return confirmation


@tool
def save_booking_to_database(booking_data: Dict[str, Any], user_email: str = None) -> Dict[str, Any]:
    """
    Save booking to database for persistence.
    
    Args:
        booking_data: Complete booking dictionary
        user_email: User email for user association (optional)
    
    Returns:
        Database save result
    """
    try:
        db = get_database_session()
        
        # Find user if email provided
        user = None
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
        
        # Check if booking already exists
        existing_booking = db.query(Booking).filter(
            Booking.booking_id == booking_data["booking_id"]
        ).first()
        
        if existing_booking:
            db.close()
            return {"error": "Booking already exists in database"}
        
        # Create hotel record if not exists
        hotel = None
        if "hotel" in booking_data:
            hotel_name = booking_data["hotel"]["name"]
            hotel = db.query(Hotel).filter(Hotel.name == hotel_name).first()
            
            if not hotel:
                # Create new hotel record
                hotel = Hotel(
                    name=hotel_name,
                    city="Unknown",  # We'll need to extract this from hotel data
                    country="Unknown",
                    address=booking_data["hotel"].get("address", ""),
                    phone=booking_data["hotel"].get("phone", ""),
                    overall_rating=booking_data["hotel"].get("rating", 0),
                    hotel_class=booking_data["hotel"].get("class", 0),
                    amenities=json.dumps(booking_data["hotel"].get("amenities", [])),
                    description=booking_data["hotel"].get("description", "")
                )
                db.add(hotel)
                db.commit()
                db.refresh(hotel)
        
        # Create booking record
        booking = Booking(
            booking_id=booking_data["booking_id"],
            confirmation_number=booking_data["confirmation_number"],
            user_id=user.id if user else None,
            hotel_id=hotel.id if hotel else None,
            hotel_name=booking_data["hotel"]["name"],
            hotel_address=booking_data["hotel"].get("address", ""),
            hotel_phone=booking_data["hotel"].get("phone", ""),
            hotel_rating=booking_data["hotel"].get("rating", 0),
            hotel_class=booking_data["hotel"].get("class", 0),
            check_in_date=datetime.strptime(booking_data["dates"]["check_in"], "%Y-%m-%d"),
            check_out_date=datetime.strptime(booking_data["dates"]["check_out"], "%Y-%m-%d"),
            nights=booking_data["dates"]["nights"],
            guests=booking_data["guests"],
            room_type=booking_data["room_type"],
            guest_name=booking_data["guest_info"]["name"],
            guest_email=booking_data["guest_info"]["email"],
            rate_per_night=booking_data["pricing"]["rate_per_night"],
            subtotal=booking_data["pricing"]["subtotal"],
            taxes=booking_data["pricing"]["taxes"],
            total_cost=booking_data["pricing"]["total"],
            status=booking_data["status"],
            cancellation_policy=booking_data.get("cancellation_policy", ""),
            check_in_instructions=booking_data.get("check_in_instructions", ""),
            confirmed_at=datetime.strptime(booking_data["confirmed_at"], "%Y-%m-%dT%H:%M:%S.%f") if booking_data.get("confirmed_at") else None
        )
        
        db.add(booking)
        db.commit()
        db.refresh(booking)
        db.close()
        
        return {
            "success": True,
            "message": "Booking saved to database successfully",
            "booking_id": booking.id,
            "confirmation_number": booking.confirmation_number
        }
        
    except Exception as e:
        return {"error": f"Failed to save booking: {str(e)}"}


@tool
def get_user_bookings(user_email: str) -> Dict[str, Any]:
    """
    Get all bookings for a user.
    
    Args:
        user_email: User email address
    
    Returns:
        User's booking history
    """
    try:
        db = get_database_session()
        
        # Find user
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            db.close()
            return {"error": "User not found"}
        
        # Get bookings
        bookings = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).all()
        
        booking_list = []
        for booking in bookings:
            booking_list.append({
                "id": booking.id,
                "booking_id": booking.booking_id,
                "confirmation_number": booking.confirmation_number,
                "hotel_name": booking.hotel_name,
                "check_in_date": booking.check_in_date.strftime("%Y-%m-%d"),
                "check_out_date": booking.check_out_date.strftime("%Y-%m-%d"),
                "nights": booking.nights,
                "guests": booking.guests,
                "room_type": booking.room_type,
                "total_cost": booking.total_cost,
                "status": booking.status,
                "created_at": booking.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        db.close()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}"
            },
            "bookings": booking_list,
            "total_bookings": len(booking_list)
        }
        
    except Exception as e:
        return {"error": f"Failed to get bookings: {str(e)}"}


@tool
def cancel_booking_in_database(confirmation_number: str, reason: str = "") -> Dict[str, Any]:
    """
    Cancel a booking in the database.
    
    Args:
        confirmation_number: Booking confirmation number
        reason: Reason for cancellation
    
    Returns:
        Cancellation result
    """
    try:
        db = get_database_session()
        
        # Find booking
        booking = db.query(Booking).filter(Booking.confirmation_number == confirmation_number).first()
        
        if not booking:
            db.close()
            return {"error": "Booking not found"}
        
        if booking.status == "cancelled":
            db.close()
            return {"error": "Booking is already cancelled"}
        
        # Update booking status
        booking.status = "cancelled"
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = reason
        
        db.commit()
        db.close()
        
        return {
            "success": True,
            "message": "Booking cancelled successfully",
            "confirmation_number": confirmation_number,
            "cancelled_at": datetime.utcnow().isoformat(),
            "refund_amount": booking.total_cost
        }
        
    except Exception as e:
        return {"error": f"Failed to cancel booking: {str(e)}"}