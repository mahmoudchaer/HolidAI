"""
Flight booking tools for HolidAI.
Handles flight booking workflow and database integration.
"""

from typing import Dict, Any, List
from langchain_core.tools import tool
from database.models import get_database_session, Booking, User
import json
from datetime import datetime


@tool
def quick_book_flight(
    flight_data: Dict[str, Any],
    passenger_info: Dict[str, Any],
    user_email: str
) -> Dict[str, Any]:
    """
    Complete flight booking process with passenger information.
    
    Args:
        flight_data: Flight details (airline, flight_number, departure_time, arrival_time, price, etc.)
        passenger_info: Passenger details (first_name, last_name, email, phone, passport_number)
        user_email: User's email address
    
    Returns:
        Dictionary containing booking confirmation
    """
    try:
        # Validate required fields
        required_flight_fields = ['airline', 'departure_time', 'arrival_time', 'price']
        required_passenger_fields = ['first_name', 'last_name', 'email', 'phone']
        
        for field in required_flight_fields:
            if field not in flight_data:
                return {"success": False, "error": f"Missing required flight field: {field}"}
        
        for field in required_passenger_fields:
            if field not in passenger_info:
                return {"success": False, "error": f"Missing required passenger field: {field}"}
        
        # Generate booking reference
        booking_reference = f"FL{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create booking confirmation
        confirmation = {
            "booking_reference": booking_reference,
            "status": "confirmed",
            "booking_type": "flight",
            "flight_details": {
                "airline": flight_data.get("airline"),
                "flight_number": flight_data.get("flight_number", "N/A"),
                "departure_time": flight_data.get("departure_time"),
                "arrival_time": flight_data.get("arrival_time"),
                "duration": flight_data.get("duration", "N/A"),
                "stops": flight_data.get("stops", "N/A"),
                "aircraft": flight_data.get("aircraft", "N/A"),
                "price": flight_data.get("price"),
                "booking_url": flight_data.get("booking_url", "")
            },
            "passenger_details": passenger_info,
            "booking_date": datetime.now().isoformat(),
            "total_amount": flight_data.get("price"),
            "currency": "USD"
        }
        
        return {
            "success": True,
            "message": "Flight booking completed successfully!",
            "booking_reference": booking_reference,
            "confirmation": confirmation
        }
        
    except Exception as e:
        return {"success": False, "error": f"Booking failed: {str(e)}"}


@tool
def format_flight_booking_confirmation(booking_data: Dict[str, Any]) -> str:
    """
    Format flight booking confirmation in a user-friendly way.
    
    Args:
        booking_data: Dictionary containing booking confirmation details
    
    Returns:
        Clean formatted string with booking confirmation
    """
    if not booking_data.get("success"):
        return f"❌ **Booking Failed:** {booking_data.get('error', 'Unknown error')}"
    
    confirmation = booking_data.get("confirmation", {})
    flight_details = confirmation.get("flight_details", {})
    passenger_details = confirmation.get("passenger_details", {})
    
    result = "🎉 **Flight Booking Confirmed!**\n\n"
    
    # Booking reference
    result += f"📋 **Booking Reference:** {confirmation.get('booking_reference', 'N/A')}\n"
    result += f"📅 **Booking Date:** {confirmation.get('booking_date', 'N/A')}\n"
    result += f"✅ **Status:** {confirmation.get('status', 'N/A').title()}\n\n"
    
    # Flight details
    result += "✈️ **Flight Details:**\n"
    result += f"• **Airline:** {flight_details.get('airline', 'N/A')}\n"
    result += f"• **Flight Number:** {flight_details.get('flight_number', 'N/A')}\n"
    result += f"• **Departure:** {flight_details.get('departure_time', 'N/A')}\n"
    result += f"• **Arrival:** {flight_details.get('arrival_time', 'N/A')}\n"
    result += f"• **Duration:** {flight_details.get('duration', 'N/A')}\n"
    result += f"• **Stops:** {flight_details.get('stops', 'N/A')}\n"
    result += f"• **Aircraft:** {flight_details.get('aircraft', 'N/A')}\n\n"
    
    # Passenger details
    result += "👤 **Passenger Details:**\n"
    result += f"• **Name:** {passenger_details.get('first_name', 'N/A')} {passenger_details.get('last_name', 'N/A')}\n"
    result += f"• **Email:** {passenger_details.get('email', 'N/A')}\n"
    result += f"• **Phone:** {passenger_details.get('phone', 'N/A')}\n"
    if passenger_details.get('passport_number'):
        result += f"• **Passport:** {passenger_details.get('passport_number', 'N/A')}\n"
    result += "\n"
    
    # Payment details
    result += "💰 **Payment Details:**\n"
    result += f"• **Total Amount:** {confirmation.get('total_amount', 'N/A')}\n"
    result += f"• **Currency:** {confirmation.get('currency', 'USD')}\n\n"
    
    # Next steps
    result += "📝 **Next Steps:**\n"
    result += "• Check your email for detailed confirmation\n"
    result += "• Arrive at the airport 2-3 hours before departure\n"
    result += "• Have your passport and booking reference ready\n"
    result += "• Check-in online 24 hours before departure\n\n"
    
    result += "🎉 **Have a great trip!** Safe travels! ✈️"
    
    return result


@tool
def save_flight_booking_to_database(
    booking_data: Dict[str, Any],
    user_email: str
) -> Dict[str, Any]:
    """
    Save flight booking to database for persistence.
    
    Args:
        booking_data: Dictionary containing booking confirmation details
        user_email: User's email address
    
    Returns:
        Dictionary containing save result
    """
    try:
        if not booking_data.get("success"):
            return {"success": False, "error": "Invalid booking data"}
        
        confirmation = booking_data.get("confirmation", {})
        flight_details = confirmation.get("flight_details", {})
        
        # Get database session
        session = get_database_session()
        
        try:
            # Get user
            user = session.query(User).filter(User.email == user_email).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Create booking record
            booking = Booking(
                user_id=user.id,
                booking_type="flight",
                booking_reference=confirmation.get("booking_reference"),
                status=confirmation.get("status", "confirmed"),
                booking_data=json.dumps(confirmation),
                total_amount=float(confirmation.get("total_amount", 0).replace("$", "").replace(",", "")),
                currency=confirmation.get("currency", "USD"),
                booking_date=datetime.now(),
                check_in_date=None,
                check_out_date=None,
                guest_count=1,
                special_requests=""
            )
            
            session.add(booking)
            session.commit()
            
            return {
                "success": True,
                "message": "Flight booking saved to database",
                "booking_id": booking.id
            }
            
        finally:
            session.close()
            
    except Exception as e:
        return {"success": False, "error": f"Database save failed: {str(e)}"}


@tool
def get_user_flight_bookings(user_email: str) -> Dict[str, Any]:
    """
    Get user's flight booking history.
    
    Args:
        user_email: User's email address
    
    Returns:
        Dictionary containing user's flight bookings
    """
    try:
        # Get database session
        session = get_database_session()
        
        try:
            # Get user
            user = session.query(User).filter(User.email == user_email).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Get flight bookings
            bookings = session.query(Booking).filter(
                Booking.user_id == user.id,
                Booking.booking_type == "flight"
            ).order_by(Booking.booking_date.desc()).all()
            
            flight_bookings = []
            for booking in bookings:
                try:
                    booking_data = json.loads(booking.booking_data)
                    flight_details = booking_data.get("flight_details", {})
                    
                    flight_booking = {
                        "booking_id": booking.id,
                        "booking_reference": booking.booking_reference,
                        "status": booking.status,
                        "booking_date": booking.booking_date.isoformat(),
                        "airline": flight_details.get("airline", "N/A"),
                        "flight_number": flight_details.get("flight_number", "N/A"),
                        "departure_time": flight_details.get("departure_time", "N/A"),
                        "arrival_time": flight_details.get("arrival_time", "N/A"),
                        "duration": flight_details.get("duration", "N/A"),
                        "price": flight_details.get("price", "N/A"),
                        "total_amount": booking.total_amount
                    }
                    flight_bookings.append(flight_booking)
                except (json.JSONDecodeError, KeyError):
                    continue
            
            return {
                "success": True,
                "user_email": user_email,
                "total_bookings": len(flight_bookings),
                "bookings": flight_bookings
            }
            
        finally:
            session.close()
            
    except Exception as e:
        return {"success": False, "error": f"Database query failed: {str(e)}"}


@tool
def cancel_flight_booking_in_database(
    booking_reference: str,
    user_email: str
) -> Dict[str, Any]:
    """
    Cancel flight booking in database.
    
    Args:
        booking_reference: Booking reference number
        user_email: User's email address
    
    Returns:
        Dictionary containing cancellation result
    """
    try:
        # Get database session
        session = get_database_session()
        
        try:
            # Get user
            user = session.query(User).filter(User.email == user_email).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Find booking
            booking = session.query(Booking).filter(
                Booking.user_id == user.id,
                Booking.booking_reference == booking_reference,
                Booking.booking_type == "flight"
            ).first()
            
            if not booking:
                return {"success": False, "error": "Booking not found"}
            
            # Update booking status
            booking.status = "cancelled"
            session.commit()
            
            return {
                "success": True,
                "message": f"Flight booking {booking_reference} has been cancelled",
                "booking_reference": booking_reference
            }
            
        finally:
            session.close()
            
    except Exception as e:
        return {"success": False, "error": f"Cancellation failed: {str(e)}"}


@tool
def format_flight_bookings_list(bookings_data: Dict[str, Any]) -> str:
    """
    Format user's flight bookings in a user-friendly list.
    
    Args:
        bookings_data: Dictionary containing user's flight bookings
    
    Returns:
        Clean formatted string with flight bookings list
    """
    if not bookings_data.get("success"):
        return f"❌ **Error:** {bookings_data.get('error', 'Unknown error')}"
    
    bookings = bookings_data.get("bookings", [])
    user_email = bookings_data.get("user_email", "Unknown")
    total_bookings = bookings_data.get("total_bookings", 0)
    
    if total_bookings == 0:
        return f"✈️ **No flight bookings found for {user_email}.**\n\nStart planning your next trip! 🌍"
    
    result = f"✈️ **Your Flight Bookings ({total_bookings} total):**\n\n"
    
    for i, booking in enumerate(bookings, 1):
        status_emoji = "✅" if booking.get("status") == "confirmed" else "❌" if booking.get("status") == "cancelled" else "⏳"
        
        result += f"{status_emoji} **{i}. {booking.get('airline', 'Unknown Airline')}**\n"
        result += f"   📋 **Reference:** {booking.get('booking_reference', 'N/A')}\n"
        result += f"   🎫 **Flight:** {booking.get('flight_number', 'N/A')}\n"
        result += f"   🕐 **Departure:** {booking.get('departure_time', 'N/A')}\n"
        result += f"   🕕 **Arrival:** {booking.get('arrival_time', 'N/A')}\n"
        result += f"   ⏱️ **Duration:** {booking.get('duration', 'N/A')}\n"
        result += f"   💰 **Price:** {booking.get('price', 'N/A')}\n"
        result += f"   📅 **Booked:** {booking.get('booking_date', 'N/A')[:10]}\n"
        result += f"   📊 **Status:** {booking.get('status', 'N/A').title()}\n\n"
    
    result += "💡 **Need help?** I can:\n"
    result += "• Show detailed booking information\n"
    result += "• Help you cancel a booking\n"
    result += "• Find new flights for your next trip\n"
    result += "• Book hotels at your destination\n\n"
    result += "Just let me know what you'd like to do! ✈️"
    
    return result
