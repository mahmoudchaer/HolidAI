"""Utilities-related tools for the MCP server (weather, currency, date/time, eSIM)."""

import os
import re
import httpx
import json
import requests
import time
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv
from tools.doc_loader import get_doc
from tools.api_logger import log_api_call
from bs4 import BeautifulSoup

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# API configuration
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")  # Optional - can use free tier
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
CURRENCY_API_URL = "https://api.exchangerate-api.com/v4/latest"  # Free, no key needed
WORLDTIME_API_URL = "http://worldtimeapi.org/api"  # Free, no key needed
CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY", "")  # Required for Calendarific API
CALENDARIFIC_API_URL = "https://calendarific.com/api/v2/holidays"


def register_utilities_tools(mcp):
    """Register utilities tools with the MCP server."""
    
    @mcp.tool(description=get_doc("get_real_time_weather", "utilities"))
    async def get_real_time_weather(location: str) -> Dict:
        """Get real-time weather information for a specific location.
        
        Args:
            location: City name or country name (e.g., "New York", "London", "Lebanon")
            
        Returns:
            Dictionary with weather information including temperature, conditions, humidity, etc.
        """
        try:
            # Try OpenWeatherMap first if API key is available
            if WEATHER_API_KEY:
                start_time = time.time()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    params = {
                        "q": location,
                        "appid": WEATHER_API_KEY,
                        "units": "metric"  # Use metric for Celsius
                    }
                    response = await client.get(WEATHER_API_URL, params=params)
                    response_time_ms = (time.time() - start_time) * 1000
                    response.raise_for_status()
                    data = response.json()
                    
                    # Log API call
                    log_api_call(
                        service="weather",
                        endpoint="/weather",
                        method="GET",
                        request_payload=params,
                        response_status=response.status_code,
                        response_time_ms=response_time_ms,
                        success=True
                    )
                    
                    return {
                        "error": False,
                        "location": f"{data.get('name', location)}, {data.get('sys', {}).get('country', '')}",
                        "temperature": round(data.get("main", {}).get("temp", 0), 1),
                        "feels_like": round(data.get("main", {}).get("feels_like", 0), 1),
                        "description": data.get("weather", [{}])[0].get("description", "").title(),
                        "humidity": data.get("main", {}).get("humidity", 0),
                        "wind_speed": round(data.get("wind", {}).get("speed", 0) * 3.6, 1),  # Convert m/s to km/h
                        "pressure": data.get("main", {}).get("pressure", 0),
                        "visibility": round(data.get("visibility", 0) / 1000, 1) if data.get("visibility") else None,  # Convert to km
                        "clouds": data.get("clouds", {}).get("all", 0),
                        "units": {
                            "temperature": "Celsius",
                            "wind_speed": "km/h",
                            "pressure": "hPa",
                            "visibility": "km"
                        }
                    }
            else:
                # Fallback to wttr.in (free, no key needed)
                start_time = time.time()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    url = f"https://wttr.in/{location}?format=j1"
                    response = await client.get(url)
                    response_time_ms = (time.time() - start_time) * 1000
                    response.raise_for_status()
                    data = response.json()
                    
                    # Log API call (wttr.in is free but still an external API)
                    log_api_call(
                        service="weather",
                        endpoint="/weather",
                        method="GET",
                        request_payload={"location": location, "source": "wttr.in"},
                        response_status=response.status_code,
                        response_time_ms=response_time_ms,
                        success=True
                    )
                    
                    current = data.get("current_condition", [{}])[0]
                    return {
                        "error": False,
                        "location": location,
                        "temperature": int(current.get("temp_C", 0)),
                        "feels_like": int(current.get("FeelsLikeC", 0)),
                        "description": current.get("weatherDesc", [{}])[0].get("value", ""),
                        "humidity": int(current.get("humidity", 0)),
                        "wind_speed": float(current.get("windspeedKmph", 0)),
                        "pressure": int(current.get("pressure", 0)),
                        "visibility": float(current.get("visibility", 0)),
                        "clouds": int(current.get("cloudcover", 0)),
                        "units": {
                            "temperature": "Celsius",
                            "wind_speed": "km/h",
                            "pressure": "mbar",
                            "visibility": "km"
                        }
                    }
        except httpx.HTTPStatusError as e:
            error_msg = f"Could not fetch weather data for '{location}'. Please check the location name and try again."
            log_api_call(
                service="weather",
                endpoint="/weather",
                method="GET",
                request_payload={"location": location},
                response_status=e.response.status_code if hasattr(e, 'response') else None,
                response_time_ms=None,
                success=False,
                error_message=error_msg
            )
            return {
                "error": True,
                "error_message": error_msg,
                "error_code": "API_ERROR"
            }
        except Exception as e:
            error_msg = f"Error fetching weather: {str(e)}"
            log_api_call(
                service="weather",
                endpoint="/weather",
                method="GET",
                request_payload={"location": location},
                response_status=None,
                response_time_ms=None,
                success=False,
                error_message=error_msg
            )
            return {
                "error": True,
                "error_message": error_msg,
                "error_code": "UNEXPECTED_ERROR"
            }
    
    @mcp.tool(description=get_doc("convert_currencies", "utilities"))
    async def convert_currencies(from_currency: str, to_currency: str, amount: float = 1.0) -> Dict:
        """Convert currency from one code to another.
        
        Args:
            from_currency: Source currency code (e.g., "USD", "EUR", "GBP", "JPY")
            to_currency: Target currency code (e.g., "USD", "EUR", "GBP", "JPY")
            amount: Amount to convert (default: 1.0)
            
        Returns:
            Dictionary with conversion result including converted amount and exchange rate
        """
        try:
            from_currency = from_currency.upper().strip()
            to_currency = to_currency.upper().strip()
            
            if from_currency == to_currency:
                return {
                    "error": False,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "amount": amount,
                    "converted_amount": amount,
                    "exchange_rate": 1.0,
                    "message": "Same currency - no conversion needed"
                }
            
            # Use exchangerate-api.com (free, no key needed)
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get rates for the base currency
                response = await client.get(f"{CURRENCY_API_URL}/{from_currency}")
                response.raise_for_status()
                data = response.json()
                
                rates = data.get("rates", {})
                if to_currency not in rates:
                    return {
                        "error": True,
                        "error_message": f"Currency code '{to_currency}' not found or not supported.",
                        "error_code": "INVALID_CURRENCY"
                    }
                
                exchange_rate = rates[to_currency]
                converted_amount = round(amount * exchange_rate, 2)
                
                return {
                    "error": False,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "amount": amount,
                    "converted_amount": converted_amount,
                    "exchange_rate": round(exchange_rate, 6),
                    "rate_date": data.get("date", ""),
                    "base_currency": data.get("base", from_currency)
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "error": True,
                    "error_message": f"Currency code '{from_currency}' not found or not supported.",
                    "error_code": "INVALID_CURRENCY"
                }
            return {
                "error": True,
                "error_message": f"Error fetching exchange rates: {e.response.status_code}",
                "error_code": "API_ERROR"
            }
        except Exception as e:
            return {
                "error": True,
                "error_message": f"Error converting currency: {str(e)}",
                "error_code": "UNEXPECTED_ERROR"
            }
    
    @mcp.tool(description=get_doc("get_real_time_date_time", "utilities"))
    async def get_real_time_date_time(location: str) -> Dict:
        """Get real-time date and time for a specific country or city.
        
        Args:
            location: Country name or city name (e.g., "New York", "London", "Japan", "Lebanon")
            
        Returns:
            Dictionary with current date, time, timezone, and related information
        """
        # Method 1: Try using Python's zoneinfo (Python 3.9+) or pytz as fallback
        try:
            location_lower = location.lower().strip()
            
            # Comprehensive timezone mapping
            timezone_map = {
                # Major Cities - US
                "new york": "America/New_York", "nyc": "America/New_York", "new york city": "America/New_York",
                "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
                "chicago": "America/Chicago", "houston": "America/Chicago", "dallas": "America/Chicago",
                "miami": "America/New_York", "boston": "America/New_York", "atlanta": "America/New_York",
                "washington": "America/New_York", "washington dc": "America/New_York", "dc": "America/New_York",
                "seattle": "America/Los_Angeles", "denver": "America/Denver", "phoenix": "America/Phoenix",
                # Major Cities - Europe
                "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
                "rome": "Europe/Rome", "madrid": "Europe/Madrid", "amsterdam": "Europe/Amsterdam",
                "brussels": "Europe/Brussels", "vienna": "Europe/Vienna", "zurich": "Europe/Zurich",
                "stockholm": "Europe/Stockholm", "copenhagen": "Europe/Copenhagen", "oslo": "Europe/Oslo",
                "helsinki": "Europe/Helsinki", "dublin": "Europe/Dublin", "lisbon": "Europe/Lisbon",
                "athens": "Europe/Athens", "warsaw": "Europe/Warsaw", "prague": "Europe/Prague",
                "budapest": "Europe/Budapest", "istanbul": "Europe/Istanbul", "moscow": "Europe/Moscow",
                # Major Cities - Asia
                "tokyo": "Asia/Tokyo", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
                "hong kong": "Asia/Hong_Kong", "singapore": "Asia/Singapore", "seoul": "Asia/Seoul",
                "bangkok": "Asia/Bangkok", "kuala lumpur": "Asia/Kuala_Lumpur", "jakarta": "Asia/Jakarta",
                "manila": "Asia/Manila", "ho chi minh": "Asia/Ho_Chi_Minh", "hanoi": "Asia/Ho_Chi_Minh",
                "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
                "dubai": "Asia/Dubai", "abu dhabi": "Asia/Dubai", "riyadh": "Asia/Riyadh",
                "jeddah": "Asia/Riyadh", "doha": "Asia/Qatar", "kuwait": "Asia/Kuwait",
                "beirut": "Asia/Beirut",
                # Major Cities - Other
                "cairo": "Africa/Cairo", "johannesburg": "Africa/Johannesburg", "cape town": "Africa/Johannesburg",
                "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne", "brisbane": "Australia/Brisbane",
                "perth": "Australia/Perth", "auckland": "Pacific/Auckland",
                "toronto": "America/Toronto", "vancouver": "America/Vancouver", "montreal": "America/Toronto",
                "calgary": "America/Edmonton", "mexico city": "America/Mexico_City",
                "sao paulo": "America/Sao_Paulo", "rio de janeiro": "America/Sao_Paulo",
                "buenos aires": "America/Argentina/Buenos_Aires", "lima": "America/Lima",
                "bogota": "America/Bogota", "santiago": "America/Santiago",
                # Countries
                "usa": "America/New_York", "united states": "America/New_York", "us": "America/New_York",
                "uk": "Europe/London", "united kingdom": "Europe/London", "britain": "Europe/London",
                "france": "Europe/Paris", "germany": "Europe/Berlin", "italy": "Europe/Rome",
                "spain": "Europe/Madrid", "netherlands": "Europe/Amsterdam", "belgium": "Europe/Brussels",
                "switzerland": "Europe/Zurich", "austria": "Europe/Vienna", "sweden": "Europe/Stockholm",
                "norway": "Europe/Oslo", "denmark": "Europe/Copenhagen", "finland": "Europe/Helsinki",
                "ireland": "Europe/Dublin", "portugal": "Europe/Lisbon", "greece": "Europe/Athens",
                "poland": "Europe/Warsaw", "czech republic": "Europe/Prague", "hungary": "Europe/Budapest",
                "turkey": "Europe/Istanbul", "russia": "Europe/Moscow",
                "japan": "Asia/Tokyo", "china": "Asia/Shanghai", "south korea": "Asia/Seoul", "korea": "Asia/Seoul",
                "thailand": "Asia/Bangkok", "malaysia": "Asia/Kuala_Lumpur", "indonesia": "Asia/Jakarta",
                "philippines": "Asia/Manila", "vietnam": "Asia/Ho_Chi_Minh", "india": "Asia/Kolkata",
                "uae": "Asia/Dubai", "united arab emirates": "Asia/Dubai", "saudi arabia": "Asia/Riyadh",
                "qatar": "Asia/Qatar", "kuwait": "Asia/Kuwait", "lebanon": "Asia/Beirut",
                "egypt": "Africa/Cairo", "south africa": "Africa/Johannesburg",
                "australia": "Australia/Sydney", "new zealand": "Pacific/Auckland",
                "canada": "America/Toronto", "brazil": "America/Sao_Paulo", "mexico": "America/Mexico_City",
                "argentina": "America/Argentina/Buenos_Aires", "chile": "America/Santiago",
                "peru": "America/Lima", "colombia": "America/Bogota"
            }
            
            # Try to find timezone in map
            timezone = timezone_map.get(location_lower)
            
            # Try variations
            if not timezone:
                variations = [
                    location_lower.replace(" city", ""),
                    location_lower.replace("town", ""),
                    location_lower.replace(" capital", ""),
                    location_lower.replace("the ", "")
                ]
                for var in variations:
                    if var in timezone_map:
                        timezone = timezone_map[var]
                        break
            
            if not timezone:
                # Try WorldTimeAPI as fallback
                return await _get_time_from_worldtimeapi(location, location_lower, timezone_map)
            
            # Use Python's datetime with timezone (Python 3.9+)
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(timezone)
            except (ImportError, Exception):
                # Fallback to pytz if zoneinfo not available
                try:
                    import pytz
                    tz = pytz.timezone(timezone)
                except ImportError:
                    # If neither available, use WorldTimeAPI
                    return await _get_time_from_worldtimeapi(location, location_lower, timezone_map)
            
            # Get current time in the timezone
            now = datetime.now(tz)
            
            # Format UTC offset
            utc_offset = now.strftime("%z")
            if utc_offset:
                utc_offset = f"{utc_offset[:3]}:{utc_offset[3:]}"
            else:
                utc_offset = "+00:00"
            
            return {
                "error": False,
                "location": location,
                "timezone": timezone,
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "day_of_week": now.strftime("%A"),
                "utc_offset": utc_offset,
                "abbreviation": now.strftime("%Z") or timezone.split("/")[-1][:3].upper(),
                "timezone_name": timezone
            }
            
        except Exception as e:
            # Final fallback to WorldTimeAPI
            try:
                return await _get_time_from_worldtimeapi(location, location.lower().strip(), {})
            except:
                return {
                    "error": True,
                    "error_message": f"Error fetching date/time for '{location}': {str(e)}",
                    "error_code": "UNEXPECTED_ERROR"
                }
    
    async def _get_time_from_worldtimeapi(location: str, location_lower: str, timezone_map: dict) -> Dict:
        """Fallback method using WorldTimeAPI."""
        try:
            # Use provided timezone_map if available, otherwise use default
            if not timezone_map:
                timezone_map = {
                # Major Cities
                "new york": "America/New_York",
                "nyc": "America/New_York",
                "new york city": "America/New_York",
                "los angeles": "America/Los_Angeles",
                "la": "America/Los_Angeles",
                "san francisco": "America/Los_Angeles",
                "chicago": "America/Chicago",
                "houston": "America/Chicago",
                "miami": "America/New_York",
                "boston": "America/New_York",
                "washington": "America/New_York",
                "washington dc": "America/New_York",
                "seattle": "America/Los_Angeles",
                "denver": "America/Denver",
                "phoenix": "America/Phoenix",
                "atlanta": "America/New_York",
                "dallas": "America/Chicago",
                "london": "Europe/London",
                "paris": "Europe/Paris",
                "berlin": "Europe/Berlin",
                "rome": "Europe/Rome",
                "madrid": "Europe/Madrid",
                "amsterdam": "Europe/Amsterdam",
                "brussels": "Europe/Brussels",
                "vienna": "Europe/Vienna",
                "zurich": "Europe/Zurich",
                "stockholm": "Europe/Stockholm",
                "copenhagen": "Europe/Copenhagen",
                "oslo": "Europe/Oslo",
                "helsinki": "Europe/Helsinki",
                "dublin": "Europe/Dublin",
                "lisbon": "Europe/Lisbon",
                "athens": "Europe/Athens",
                "warsaw": "Europe/Warsaw",
                "prague": "Europe/Prague",
                "budapest": "Europe/Budapest",
                "istanbul": "Europe/Istanbul",
                "moscow": "Europe/Moscow",
                "tokyo": "Asia/Tokyo",
                "beijing": "Asia/Shanghai",
                "shanghai": "Asia/Shanghai",
                "hong kong": "Asia/Hong_Kong",
                "singapore": "Asia/Singapore",
                "seoul": "Asia/Seoul",
                "bangkok": "Asia/Bangkok",
                "kuala lumpur": "Asia/Kuala_Lumpur",
                "jakarta": "Asia/Jakarta",
                "manila": "Asia/Manila",
                "ho chi minh": "Asia/Ho_Chi_Minh",
                "hanoi": "Asia/Ho_Chi_Minh",
                "mumbai": "Asia/Kolkata",
                "delhi": "Asia/Kolkata",
                "bangalore": "Asia/Kolkata",
                "dubai": "Asia/Dubai",
                "abu dhabi": "Asia/Dubai",
                "riyadh": "Asia/Riyadh",
                "jeddah": "Asia/Riyadh",
                "doha": "Asia/Qatar",
                "kuwait": "Asia/Kuwait",
                "beirut": "Asia/Beirut",
                "cairo": "Africa/Cairo",
                "johannesburg": "Africa/Johannesburg",
                "cape town": "Africa/Johannesburg",
                "sydney": "Australia/Sydney",
                "melbourne": "Australia/Melbourne",
                "brisbane": "Australia/Brisbane",
                "perth": "Australia/Perth",
                "auckland": "Pacific/Auckland",
                "toronto": "America/Toronto",
                "vancouver": "America/Vancouver",
                "montreal": "America/Toronto",
                "calgary": "America/Edmonton",
                "mexico city": "America/Mexico_City",
                "sao paulo": "America/Sao_Paulo",
                "rio de janeiro": "America/Sao_Paulo",
                "buenos aires": "America/Argentina/Buenos_Aires",
                "lima": "America/Lima",
                "bogota": "America/Bogota",
                "santiago": "America/Santiago",
                # Countries
                "usa": "America/New_York",
                "united states": "America/New_York",
                "us": "America/New_York",
                "uk": "Europe/London",
                "united kingdom": "Europe/London",
                "britain": "Europe/London",
                "france": "Europe/Paris",
                "germany": "Europe/Berlin",
                "italy": "Europe/Rome",
                "spain": "Europe/Madrid",
                "netherlands": "Europe/Amsterdam",
                "belgium": "Europe/Brussels",
                "switzerland": "Europe/Zurich",
                "austria": "Europe/Vienna",
                "sweden": "Europe/Stockholm",
                "norway": "Europe/Oslo",
                "denmark": "Europe/Copenhagen",
                "finland": "Europe/Helsinki",
                "ireland": "Europe/Dublin",
                "portugal": "Europe/Lisbon",
                "greece": "Europe/Athens",
                "poland": "Europe/Warsaw",
                "czech republic": "Europe/Prague",
                "hungary": "Europe/Budapest",
                "turkey": "Europe/Istanbul",
                "russia": "Europe/Moscow",
                "japan": "Asia/Tokyo",
                "china": "Asia/Shanghai",
                "south korea": "Asia/Seoul",
                "korea": "Asia/Seoul",
                "thailand": "Asia/Bangkok",
                "malaysia": "Asia/Kuala_Lumpur",
                "indonesia": "Asia/Jakarta",
                "philippines": "Asia/Manila",
                "vietnam": "Asia/Ho_Chi_Minh",
                "india": "Asia/Kolkata",
                "uae": "Asia/Dubai",
                "united arab emirates": "Asia/Dubai",
                "saudi arabia": "Asia/Riyadh",
                "qatar": "Asia/Qatar",
                "kuwait": "Asia/Kuwait",
                "lebanon": "Asia/Beirut",
                "egypt": "Africa/Cairo",
                "south africa": "Africa/Johannesburg",
                "australia": "Australia/Sydney",
                "new zealand": "Pacific/Auckland",
                "canada": "America/Toronto",
                "brazil": "America/Sao_Paulo",
                "mexico": "America/Mexico_City",
                "argentina": "America/Argentina/Buenos_Aires",
                "chile": "America/Santiago",
                "peru": "America/Lima",
                "colombia": "America/Bogota"
            }
            
            # Try to find timezone in map
            timezone = timezone_map.get(location_lower)
            
            # If not found, try with common variations
            if not timezone:
                # Remove common suffixes
                variations = [
                    location_lower,
                    location_lower.replace(" city", ""),
                    location_lower.replace("town", ""),
                    location_lower.replace(" capital", "")
                ]
                for var in variations:
                    if var in timezone_map:
                        timezone = timezone_map[var]
                        break
            
            # If still not found, try WorldTimeAPI's timezone list endpoint
            if not timezone:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        # Try to get timezone by location name using WorldTimeAPI's ip endpoint
                        # or try common timezone patterns
                        location_normalized = location_lower.replace(" ", "_").replace("-", "_")
                        
                        # Try common timezone patterns
                        possible_timezones = [
                            f"America/{location_normalized.title()}",
                            f"Europe/{location_normalized.title()}",
                            f"Asia/{location_normalized.title()}",
                            f"Africa/{location_normalized.title()}",
                            f"Australia/{location_normalized.title()}",
                            f"Pacific/{location_normalized.title()}",
                            f"America/New_{location_normalized.title()}",
                            f"America/Los_{location_normalized.title()}",
                        ]
                        
                        for tz in possible_timezones:
                            try:
                                response = await client.get(f"{WORLDTIME_API_URL}/timezone/{tz}", timeout=5.0)
                                if response.status_code == 200:
                                    timezone = tz
                                    break
                            except:
                                continue
                except:
                    pass
            
            if not timezone:
                return {
                    "error": True,
                    "error_message": f"Could not determine timezone for '{location}'. Please try using a major city name or country name.",
                    "error_code": "INVALID_LOCATION",
                    "suggestion": "Try using major city names like 'New York', 'London', 'Tokyo' or country names like 'USA', 'UK', 'Japan'"
                }
            
            # Fetch timezone data
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{WORLDTIME_API_URL}/timezone/{timezone}")
                response.raise_for_status()
                data = response.json()
                
                # Parse datetime - handle different formats
                datetime_str = data.get("datetime", "")
                if not datetime_str:
                    return {
                        "error": True,
                        "error_message": f"No datetime data returned for '{location}'.",
                        "error_code": "API_ERROR"
                    }
                
                # Handle different datetime formats
                try:
                    # WorldTimeAPI returns ISO format like "2024-01-15T14:30:00.123456+05:00" or "2024-01-15T14:30:00.123456Z"
                    # Clean up the datetime string
                    if datetime_str.endswith('Z'):
                        datetime_str = datetime_str[:-1] + '+00:00'
                    
                    # Parse using fromisoformat (Python 3.7+)
                    # Handle microseconds and timezone offset
                    if '.' in datetime_str:
                        # Has microseconds
                        parts = datetime_str.split('.')
                        if len(parts) == 2:
                            date_part = parts[0]
                            rest = parts[1]
                            # Extract timezone offset
                            if '+' in rest:
                                micro, offset = rest.split('+')
                                datetime_str = f"{date_part}.{micro}+{offset}"
                            elif '-' in rest and len(rest) > 6:  # Timezone offset, not just microseconds
                                # Check if it's a timezone offset (format: -05:00)
                                if rest[-6] == '-' or rest[-6] == '+':
                                    micro = rest[:-6]
                                    offset = rest[-6:]
                                    datetime_str = f"{date_part}.{micro}{offset}"
                                else:
                                    datetime_str = f"{date_part}.{rest}"
                            else:
                                datetime_str = f"{date_part}.{rest}"
                    
                    # Parse the datetime
                    dt = datetime.fromisoformat(datetime_str)
                except (ValueError, AttributeError) as e:
                    # Fallback: try to extract just the date and time parts
                    try:
                        # Extract date and time manually
                        # Format is typically: "2024-01-15T14:30:00.123456+05:00"
                        import re
                        match = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})', datetime_str)
                        if match:
                            date_part = match.group(1)
                            time_part = match.group(2)
                            dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
                        else:
                            raise ValueError("Could not parse datetime")
                    except:
                        return {
                            "error": True,
                            "error_message": f"Could not parse datetime format: {datetime_str}. Please try a different location.",
                            "error_code": "PARSE_ERROR"
                        }
                
                return {
                    "error": False,
                    "location": location,
                    "timezone": timezone,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M:%S"),
                    "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "day_of_week": dt.strftime("%A"),
                    "utc_offset": data.get("utc_offset", ""),
                    "abbreviation": data.get("abbreviation", ""),
                    "timezone_name": data.get("timezone", timezone)
                }
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", str(e))
            except:
                error_detail = str(e)
            
            return {
                "error": True,
                "error_message": f"Could not fetch time data for '{location}'. Error: {error_detail}",
                "error_code": "API_ERROR",
                "suggestion": "Please check the location name and try again. Use major city names or country names."
            }
        except Exception as e:
            import traceback
            return {
                "error": True,
                "error_message": f"Error fetching date/time: {str(e)}",
                "error_code": "UNEXPECTED_ERROR",
                "details": str(traceback.format_exc())[:200]  # First 200 chars of traceback
            }
    
    @mcp.tool(description=get_doc("get_esim_bundles", "utilities"))
    async def get_esim_bundles(country: str, limit: Optional[int] = 50) -> Dict:
        """Get available eSIM bundles for a specific country.
        
        Searches esimradar.com first, then Nomad (getnomad.app) as fallback for countries like UAE.
        
        Args:
            country: Country name (e.g., "Qatar", "USA", "Lebanon", "Japan", "France", "UAE")
            limit: Maximum number of bundles to return (default: 50, max: 200)
            
        Returns:
            Dictionary with list of eSIM bundles including provider, plan, validity, price, and link.
            If data unavailable from both sources, returns recommended eSIM provider websites.
        """
        # Validate and enforce limit
        if limit is None:
            limit = 50
        elif limit < 1:
            limit = 50
        elif limit > 200:
            limit = 200
        try:
            # Map country names to esimradar.com slugs and country codes
            country_mapping = {
                # Middle East
                "qatar": ("esim-qatar", "qa"),
                "uae": ("esim-uae", "ae"),
                "united arab emirates": ("esim-uae", "ae"),
                "emirates": ("esim-uae", "ae"),  # Alternative name
                "dubai": ("esim-uae", "ae"),  # Common city reference
                "saudi arabia": ("esim-saudi-arabia", "sa"),
                "kuwait": ("esim-kuwait", "kw"),
                "bahrain": ("esim-bahrain", "bh"),
                "oman": ("esim-oman", "om"),
                "lebanon": ("esim-lebanon", "lb"),
                "jordan": ("esim-jordan", "jo"),
                "egypt": ("esim-egypt", "eg"),
                "turkey": ("esim-turkey", "tr"),
                # Asia
                "japan": ("esim-japan", "jp"),
                "china": ("esim-china", "cn"),
                "south korea": ("esim-south-korea", "kr"),
                "korea": ("esim-south-korea", "kr"),
                "singapore": ("esim-singapore", "sg"),
                "thailand": ("esim-thailand", "th"),
                "malaysia": ("esim-malaysia", "my"),
                "indonesia": ("esim-indonesia", "id"),
                "philippines": ("esim-philippines", "ph"),
                "vietnam": ("esim-vietnam", "vn"),
                "india": ("esim-india", "in"),
                "hong kong": ("esim-hong-kong", "hk"),
                "taiwan": ("esim-taiwan", "tw"),
                # Europe
                "uk": ("esim-uk", "gb"),
                "united kingdom": ("esim-uk", "gb"),
                "britain": ("esim-uk", "gb"),
                "france": ("esim-france", "fr"),
                "germany": ("esim-germany", "de"),
                "italy": ("esim-italy", "it"),
                "spain": ("esim-spain", "es"),
                "netherlands": ("esim-netherlands", "nl"),
                "belgium": ("esim-belgium", "be"),
                "switzerland": ("esim-switzerland", "ch"),
                "austria": ("esim-austria", "at"),
                "sweden": ("esim-sweden", "se"),
                "norway": ("esim-norway", "no"),
                "denmark": ("esim-denmark", "dk"),
                "finland": ("esim-finland", "fi"),
                "ireland": ("esim-ireland", "ie"),
                "portugal": ("esim-portugal", "pt"),
                "greece": ("esim-greece", "gr"),
                "poland": ("esim-poland", "pl"),
                "czech republic": ("esim-czech-republic", "cz"),
                "hungary": ("esim-hungary", "hu"),
                "russia": ("esim-russia", "ru"),
                # Americas
                "usa": ("esim-usa", "us"),
                "united states": ("esim-usa", "us"),
                "us": ("esim-usa", "us"),
                "canada": ("esim-canada", "ca"),
                "mexico": ("esim-mexico", "mx"),
                "brazil": ("esim-brazil", "br"),
                "argentina": ("esim-argentina", "ar"),
                "chile": ("esim-chile", "cl"),
                "colombia": ("esim-colombia", "co"),
                # Oceania
                "australia": ("esim-australia", "au"),
                "new zealand": ("esim-new-zealand", "nz"),
                # Africa
                "south africa": ("esim-south-africa", "za"),
            }
            
            country_lower = country.lower().strip()
            
            # Try to find country in mapping
            country_slug, country_code = None, None
            if country_lower in country_mapping:
                country_slug, country_code = country_mapping[country_lower]
            else:
                # Try variations
                variations = [
                    country_lower.replace("the ", ""),
                    country_lower.replace(" country", ""),
                ]
                for var in variations:
                    if var in country_mapping:
                        country_slug, country_code = country_mapping[var]
                        break
                
                if not country_slug:
                    return {
                        "error": True,
                        "error_message": f"Country '{country}' not found in eSIM database. Please try using a supported country name.",
                        "error_code": "INVALID_COUNTRY",
                        "suggestion": "Try using country names like 'Qatar', 'USA', 'UAE', 'Japan', 'Lebanon', etc."
                    }
            
            # Generate URL slugs - improved pattern matching
            # Create country name slug (e.g., "lebanon" -> "lebanon", "uae" -> "uae")
            country_name_slug = country_lower.replace(" ", "-").replace("_", "-")
            # Create short slug (remove common words)
            country_short_slug = country_name_slug.replace("united-", "").replace("arab-", "").replace("emirates", "uae")
            
            # Scrape eSIM data - try multiple URL patterns
            urls_to_try = []
            
            # For Lebanon, try Middle East regional page first (Lebanon is included there)
            if country_lower == "lebanon" or country_code.lower() == "lb":
                urls_to_try.extend([
                    "https://esimradar.com/esim/middle-east/",
                    "https://esimradar.com/esim-middle-east/",
                    f"https://esimradar.com/esim/{country_name_slug}/",
                    f"https://esimradar.com/esim-{country_name_slug}/",
                    f"https://esimradar.com/{country_slug}/?s={country_code}",
                    f"https://esimradar.com/{country_slug}/",
                ])
            # For UAE, try Middle East regional page first (UAE is included there, same as Lebanon)
            elif country_code.lower() == "ae" or "uae" in country_lower or "united arab emirates" in country_lower:
                urls_to_try.extend([
                    # Try Middle East regional page first (UAE is included there)
                    "https://esimradar.com/esim/middle-east/",
                    "https://esimradar.com/esim-middle-east/",
                    # Then try UAE-specific URLs
                    "https://esimradar.com/esim/uae/",
                    "https://esimradar.com/esim-uae/",
                    "https://esimradar.com/esim/united-arab-emirates/",
                    "https://esimradar.com/esim-united-arab-emirates/",
                    "https://esimradar.com/esim/dubai/",
                    "https://esimradar.com/esim-dubai/",
                    "https://esimradar.com/esim-ae/",
                    f"https://esimradar.com/{country_slug}/?s={country_code}",
                    f"https://esimradar.com/{country_slug}/",
                ])
            else:
                # For other countries, use standard patterns
                urls_to_try.extend([
                    # Pattern 1: /esim/{country-name-slug}/ (works for UAE, Qatar, Japan, etc.)
                    f"https://esimradar.com/esim/{country_name_slug}/",
                    # Pattern 2: /esim-{country-short-slug}/ (works for Qatar, Japan, USA, etc.)
                    f"https://esimradar.com/esim-{country_short_slug}/",
                    # Pattern 3: /esim-{country-code}/ (works for some countries like QA, US)
                    f"https://esimradar.com/esim-{country_code.lower()}/",
                    # Pattern 4: Original patterns with query string
                    f"https://esimradar.com/{country_slug}/?s={country_code}",
                    f"https://esimradar.com/{country_slug}/",
                ])
            
            # Remove duplicates while preserving order
            seen = set()
            urls_to_try = [url for url in urls_to_try if url not in seen and not seen.add(url)]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Try multiple URL formats
            response = None
            url = None
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
                for attempt_url in urls_to_try:
                    try:
                        print(f"eSIM Tool: Trying URL: {attempt_url}")
                        response = await client.get(attempt_url)
                        if response.status_code == 200:
                            url = attempt_url
                            print(f"eSIM Tool: Successfully fetched from {url}")
                            break
                    except httpx.HTTPStatusError as e:
                        print(f"eSIM Tool: URL {attempt_url} returned status {e.response.status_code}")
                        continue
                    except Exception as e:
                        print(f"eSIM Tool: Error with URL {attempt_url}: {str(e)}")
                        continue
                
                if not response or response.status_code != 200:
                    # Try Nomad as fallback (simple structure, easy to parse)
                    print("eSIM Tool: esimradar.com failed, trying Nomad (getnomad.app)...")
                    nomad_country_slugs = {
                        "uae": "uae",
                        "united arab emirates": "uae",
                        "emirates": "uae",
                        "dubai": "uae",
                        "saudi arabia": "saudi-arabia",
                        "qatar": "qatar",
                        "kuwait": "kuwait",
                        "bahrain": "bahrain",
                        "oman": "oman",
                        "lebanon": "lebanon",
                        "jordan": "jordan",
                        "egypt": "egypt",
                        "turkey": "turkey",
                        "usa": "usa",
                        "united states": "usa",
                        "france": "france",
                        "germany": "germany",
                        "italy": "italy",
                        "spain": "spain",
                        "uk": "uk",
                        "united kingdom": "uk",
                        "japan": "japan",
                        "singapore": "singapore",
                        "thailand": "thailand",
                        "australia": "australia"
                    }
                    
                    nomad_slug = nomad_country_slugs.get(country_lower)
                    if nomad_slug:
                        nomad_url = f"https://www.getnomad.app/en/{nomad_slug}"
                        try:
                            print(f"eSIM Tool: Trying Nomad URL: {nomad_url}")
                            nomad_response = await client.get(nomad_url)
                            if nomad_response.status_code == 200:
                                response = nomad_response
                                url = nomad_url
                                print(f"eSIM Tool: Successfully fetched from Nomad {url}")
                        except Exception as e:
                            print(f"eSIM Tool: Nomad fetch failed: {str(e)}")
                    
                    # If still no response, provide helpful suggestions
                    if not response or response.status_code != 200:
                        return {
                            "error": True,
                            "error_message": f"eSIM data not available for '{country}' in our database.",
                            "error_code": "DATA_UNAVAILABLE",
                            "country": country,
                            "suggestion": "Try checking these eSIM providers directly:",
                            "recommended_providers": [
                                {"name": "Airalo", "url": "https://www.airalo.com"},
                                {"name": "Holafly", "url": "https://esim.holafly.com"},
                                {"name": "Nomad", "url": "https://www.getnomad.app"},
                                {"name": "Ubigi", "url": "https://www.ubigi.com"}
                            ]
                        }
                
                # Debug: Check response status and content length
                print(f"eSIM Tool: Response status: {response.status_code}, Content length: {len(response.text)}")
                
                # Parse HTML with BeautifulSoup
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                except Exception as e:
                    return {
                        "error": True,
                        "error_message": f"Error parsing HTML: {str(e)}",
                        "error_code": "PARSING_ERROR",
                        "country": country
                    }
                
                # Debug: Check what tables exist in the HTML
                all_tables = soup.find_all("table")
                print(f"eSIM Tool: Found {len(all_tables)} table(s) in HTML")
                if all_tables:
                    for idx, tbl in enumerate(all_tables[:3]):  # Show first 3 tables
                        tbl_id = tbl.get("id", "no-id")
                        tbl_class = tbl.get("class", [])
                        print(f"eSIM Tool: Table {idx}: id='{tbl_id}', class={tbl_class}")
                
                # Find the table with eSIM bundles - try multiple possible table IDs
                table = soup.find("table", id="table_1")
                
                # If table_1 not found, try other common table IDs or just find any table
                if not table:
                    # Try alternative table IDs
                    for table_id in ["table_1", "esim-table", "bundles-table", "data-table"]:
                        table = soup.find("table", id=table_id)
                        if table:
                            print(f"eSIM Tool: Found table with id='{table_id}'")
                            break
                    
                    # If still not found, try to find any table with class or data attributes
                    if not table:
                        table = soup.find("table", class_=lambda x: x and ("esim" in str(x).lower() or "bundle" in str(x).lower()))
                        if table:
                            print(f"eSIM Tool: Found table with esim/bundle class")
                    
                    # Last resort: find any table
                    if not table:
                        tables = soup.find_all("table")
                        if tables:
                            table = tables[0]  # Use first table found
                            print(f"eSIM Tool: Using first available table (id='{table.get('id', 'no-id')}')")
                
                if not table:
                    # No table - check if this is Nomad (different structure)
                    if "getnomad.app" in url:
                        print("eSIM Tool: Parsing Nomad page structure...")
                        bundles = []
                        
                        # Nomad structure (based on actual HTML):
                        # Each plan is in an <li> with class "cursor-pointer border-2"
                        # - Data: <span class="font-bold">1 GB</span>
                        # - Validity: <p>For 7 DAYS</p>
                        # - Price: <div class="text-lg font-extrabold whitespace-nowrap">USD4.50</div>
                        
                        # Find all li elements that look like plan cards - try multiple selectors
                        plan_lis = soup.find_all("li", class_=lambda x: x and "cursor-pointer" in str(x) and "border-2" in str(x))
                        
                        # If no results, try alternative selectors
                        if not plan_lis:
                            # Try finding by data attributes or other class patterns
                            plan_lis = soup.find_all("li", class_=lambda x: x and ("plan" in str(x).lower() or "bundle" in str(x).lower() or "card" in str(x).lower()))
                        
                        # If still no results, try finding divs with plan-like classes
                        if not plan_lis:
                            plan_divs = soup.find_all("div", class_=lambda x: x and ("plan" in str(x).lower() or "bundle" in str(x).lower() or "card" in str(x).lower()))
                            if plan_divs:
                                print(f"eSIM Tool: Found {len(plan_divs)} plan <div> elements on Nomad (using divs instead of lis)")
                                # Convert divs to a list-like structure for processing
                                plan_lis = plan_divs
                        
                        print(f"eSIM Tool: Found {len(plan_lis)} plan elements on Nomad")
                        
                        # Parse each plan element
                        for idx, plan_elem in enumerate(plan_lis[:limit]):
                            try:
                                # Extract data amount - try multiple patterns
                                data_match = None
                                # Try <span class="font-bold">
                                data_elem = plan_elem.find("span", class_=lambda x: x and "font-bold" in str(x))
                                if data_elem:
                                    data_match = data_elem.get_text().strip()
                                # Try finding text with GB/MB
                                if not data_match:
                                    text = plan_elem.get_text()
                                    gb_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB)', text, re.IGNORECASE)
                                    if gb_match:
                                        data_match = f"{gb_match.group(1)} {gb_match.group(2).upper()}"
                                
                                # Extract validity - try multiple patterns
                                validity_match = ""
                                # Try "For X DAYS" pattern
                                for p_tag in plan_elem.find_all("p"):
                                    p_text = p_tag.get_text()
                                    if "For" in p_text and "DAY" in p_text:
                                        validity_pattern = r'For\s+(\d+)\s+DAYS?'
                                        match = re.search(validity_pattern, p_text, re.IGNORECASE)
                                        if match:
                                            validity_match = f"{match.group(1)} days"
                                            break
                                
                                # Also try finding validity in any text
                                if not validity_match:
                                    text = plan_elem.get_text()
                                    validity_pattern = r'(\d+)\s*(?:day|days)'
                                    match = re.search(validity_pattern, text, re.IGNORECASE)
                                    if match:
                                        validity_match = f"{match.group(1)} days"
                                
                                # Extract price - try multiple patterns
                                price_match = None
                                # Try specific div class
                                price_div = plan_elem.find("div", class_=lambda x: x and "text-lg" in str(x) and "font-extrabold" in str(x) and "whitespace-nowrap" in str(x))
                                if not price_div:
                                    # Try any div with price-like classes
                                    price_div = plan_elem.find("div", class_=lambda x: x and ("price" in str(x).lower() or "cost" in str(x).lower() or "font-extrabold" in str(x) or "font-bold" in str(x)))
                                
                                if price_div:
                                    price_text = price_div.get_text().strip()
                                    # Clean up price (e.g., "USD4.50" or "USD 4.50" or "$4.50")
                                    if "USD" in price_text:
                                        price_match = "USD " + price_text.replace("USD", "").strip()
                                    elif "$" in price_text:
                                        price_match = "USD " + price_text.replace("$", "").strip()
                                    else:
                                        # Try to extract number
                                        price_num = re.search(r'(\d+\.?\d*)', price_text)
                                        if price_num:
                                            price_match = f"USD {price_num.group(1)}"
                                
                                # If still no price, try finding in all text
                                if not price_match:
                                    text = plan_elem.get_text()
                                    price_pattern = r'[\$]?\s*(\d+\.?\d*)'
                                    price_num = re.search(price_pattern, text)
                                    if price_num:
                                        price_match = f"USD {price_num.group(1)}"
                                
                                # Get purchase link (use main page URL or try to find link in element)
                                purchase_link = url
                                link_elem = plan_elem.find("a")
                                if link_elem:
                                    href = link_elem.get("href", "")
                                    if href:
                                        if href.startswith("http"):
                                            purchase_link = href
                                        elif href.startswith("/"):
                                            purchase_link = f"https://www.getnomad.app{href}"
                                        else:
                                            purchase_link = f"https://www.getnomad.app/{href}"
                                
                                # Debug first 3
                                if idx < 3:
                                    print(f"eSIM Tool: Plan {idx}: data={data_match}, validity={validity_match}, price={price_match}")
                                
                                # Only add if we have data and price
                                if data_match and price_match:
                                    plan_name = f"{data_match}"
                                    if validity_match:
                                        plan_name += f" - {validity_match}"
                                    
                                    bundle = {
                                        "provider": "Nomad",
                                        "plan": plan_name,
                                        "validity": validity_match or "",
                                        "price": price_match,
                                        "link": purchase_link
                                    }
                                    bundles.append(bundle)
                            except Exception as e:
                                print(f"eSIM Tool: Error parsing plan {idx}: {str(e)}")
                                continue
                        
                        # Remove duplicates based on plan+price
                        unique_bundles = []
                        seen = set()
                        for bundle in bundles:
                            key = (bundle["plan"], bundle["price"])
                            if key not in seen:
                                seen.add(key)
                                unique_bundles.append(bundle)
                        
                        if unique_bundles:
                            print(f"eSIM Tool: Successfully parsed {len(unique_bundles)} plans from Nomad")
                            return {
                                "error": False,
                                "country": country,
                                "bundles": unique_bundles[:limit],
                                "total": len(unique_bundles),
                                "source": url
                            }
                        else:
                            print("eSIM Tool: Nomad page loaded but couldn't extract plan data")
                    
                    # No table and not Nomad - try parsing div-based structures (common on esimradar.com)
                    if "esimradar.com" in url:
                        print("eSIM Tool: No table found, trying to parse div-based structure for esimradar.com...")
                        bundles = []
                        
                        # Try to find plan cards/divs - common patterns on esimradar.com
                        # Look for divs that might contain plan information
                        plan_divs = soup.find_all("div", class_=lambda x: x and (
                            "plan" in str(x).lower() or 
                            "bundle" in str(x).lower() or 
                            "card" in str(x).lower() or
                            "offer" in str(x).lower() or
                            "product" in str(x).lower()
                        ))
                        
                        # Also try data attributes
                        if not plan_divs:
                            plan_divs = soup.find_all("div", attrs={"data-plan": True}) or \
                                       soup.find_all("div", attrs={"data-bundle": True})
                        
                        # Try finding by text patterns (divs containing "GB" or "MB" with prices)
                        if not plan_divs:
                            all_divs = soup.find_all("div")
                            for div in all_divs:
                                text = div.get_text()
                                # Look for divs that contain both data size (GB/MB) and price indicators
                                if (re.search(r'\d+\s*(GB|MB)', text, re.IGNORECASE) and 
                                    (re.search(r'[\$€£]\s*\d+', text) or re.search(r'\d+\.\d+', text))):
                                    # Check if it's not too large (likely a container)
                                    if len(text) < 500:  # Reasonable size for a plan card
                                        plan_divs.append(div)
                                        if len(plan_divs) >= 20:  # Limit search
                                            break
                        
                        print(f"eSIM Tool: Found {len(plan_divs)} potential plan divs")
                        
                        # Try to extract data from divs
                        for idx, div in enumerate(plan_divs[:limit]):
                            try:
                                text = div.get_text()
                                
                                # Extract data amount
                                data_match = None
                                gb_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB)', text, re.IGNORECASE)
                                if gb_match:
                                    data_match = f"{gb_match.group(1)} {gb_match.group(2).upper()}"
                                
                                # Extract price
                                price_match = None
                                # Try USD/EUR/GBP symbols
                                price_patterns = [
                                    r'[\$€£]\s*(\d+(?:\.\d+)?)',
                                    r'(\d+(?:\.\d+)?\s*USD',
                                    r'(\d+(?:\.\d+)?)\s*EUR',
                                    r'(\d+(?:\.\d+)?)\s*GBP'
                                ]
                                for pattern in price_patterns:
                                    match = re.search(pattern, text, re.IGNORECASE)
                                    if match:
                                        price_match = f"USD {match.group(1)}"
                                        break
                                
                                # Extract validity
                                validity_match = ""
                                validity_patterns = [
                                    r'(\d+)\s*(?:day|days)',
                                    r'valid\s*(?:for|:)\s*(\d+)',
                                    r'duration[:\s]+(\d+)'
                                ]
                                for pattern in validity_patterns:
                                    match = re.search(pattern, text, re.IGNORECASE)
                                    if match:
                                        validity_match = f"{match.group(1)} days"
                                        break
                                
                                # Find provider name (look for common provider names)
                                provider_match = None
                                providers = ["airalo", "holafly", "nomad", "ubigi", "orange", "vodafone", "t-mobile", "three"]
                                for provider in providers:
                                    if provider in text.lower():
                                        provider_match = provider.capitalize()
                                        break
                                
                                # Find link
                                link_elem = div.find("a")
                                purchase_link = url
                                if link_elem:
                                    href = link_elem.get("href", "")
                                    if href:
                                        if href.startswith("http"):
                                            purchase_link = href
                                        elif href.startswith("/"):
                                            purchase_link = f"https://esimradar.com{href}"
                                        else:
                                            purchase_link = f"https://esimradar.com/{href}"
                                
                                # Only add if we have essential data
                                if data_match and price_match:
                                    plan_name = f"{data_match}"
                                    if validity_match:
                                        plan_name += f" - {validity_match}"
                                    
                                    bundle = {
                                        "provider": provider_match or "Unknown",
                                        "plan": plan_name,
                                        "validity": validity_match or "",
                                        "price": price_match,
                                        "link": purchase_link
                                    }
                                    bundles.append(bundle)
                                    
                                    if idx < 3:
                                        print(f"eSIM Tool: Extracted plan {idx}: {bundle}")
                            except Exception as e:
                                print(f"eSIM Tool: Error parsing div {idx}: {str(e)}")
                                continue
                        
                        if bundles:
                            print(f"eSIM Tool: Successfully parsed {len(bundles)} plans from div structure")
                            return {
                                "error": False,
                                "country": country,
                                "bundles": bundles[:limit],
                                "total": len(bundles),
                                "source": url
                            }
                        else:
                            print("eSIM Tool: Could not extract plan data from div structure")
                    
                    # If we got a 200 response, return success even if parsing failed
                    # User can check the URL directly
                    if response.status_code == 200:
                        print(f"eSIM Tool: Got 200 response but couldn't parse structure. Returning success with URL.")
                        return {
                            "error": False,
                            "country": country,
                            "bundles": [],  # Empty but successful fetch
                            "total": 0,
                            "source": url,
                            "note": "Page loaded successfully but data structure could not be parsed. Please check the source URL directly.",
                            "recommended_providers": [
                                {"name": "Airalo", "url": "https://www.airalo.com"},
                                {"name": "Holafly", "url": "https://esim.holafly.com"},
                                {"name": "Nomad", "url": "https://www.getnomad.app"},
                                {"name": "Ubigi", "url": "https://www.ubigi.com"}
                            ]
                        }
                    
                    # Only return error if we didn't get 200
                    print(f"eSIM Tool: Failed to fetch or parse data. URL: {url}, Status: {response.status_code if response else 'No response'}")
                    return {
                        "error": True,
                        "error_message": f"eSIM data not available for '{country}' in our database.",
                        "error_code": "DATA_UNAVAILABLE",
                        "country": country,
                        "suggestion": "Try checking these eSIM providers directly:",
                        "recommended_providers": [
                            {"name": "Airalo", "url": "https://www.airalo.com"},
                            {"name": "Holafly", "url": "https://esim.holafly.com"},
                            {"name": "Nomad", "url": "https://www.getnomad.app"},
                            {"name": "Ubigi", "url": "https://www.ubigi.com"}
                        ]
                    }
                
                rows = table.find_all("tr")
                bundles = []
                
                print(f"eSIM Tool: Found table with {len(rows)} rows")
                
                # Try to identify column positions by checking header row
                header_row = None
                if rows:
                    # Check if first row is header (has th tags or specific text)
                    first_row = rows[0]
                    if first_row.find("th"):
                        header_row = first_row
                    elif any(keyword in first_row.get_text().lower() for keyword in ["provider", "plan", "price", "validity", "data"]):
                        header_row = first_row
                
                # Determine column positions from header if available
                price_col_idx = None
                provider_col_idx = None
                plan_col_idx = None
                validity_col_idx = None
                
                if header_row:
                    header_cols = header_row.find_all(["th", "td"])
                    for idx, col in enumerate(header_cols):
                        text = col.get_text().lower()
                        if "price" in text or "$" in text or "cost" in text:
                            price_col_idx = idx
                        elif "provider" in text or "company" in text or "network" in text:
                            provider_col_idx = idx
                        elif "plan" in text or "package" in text or "offer" in text:
                            plan_col_idx = idx
                        elif "validity" in text or "days" in text or "duration" in text:
                            validity_col_idx = idx
                    print(f"eSIM Tool: Detected column positions - Price: {price_col_idx}, Provider: {provider_col_idx}, Plan: {plan_col_idx}, Validity: {validity_col_idx}")
                
                # Determine start index for data rows (skip header if found)
                start_idx = 1 if header_row else 0
                
                # If header detection failed, try to infer from actual data rows
                if price_col_idx is None or plan_col_idx is None:
                    # Sample a few data rows to infer structure
                    sample_rows = rows[start_idx:min(start_idx+5, len(rows))]
                    for row in sample_rows:
                        cols = row.find_all("td")
                        if len(cols) >= 6:
                            # Check column 1 - usually contains plan name with "GB" or "MB"
                            col1_text = cols[1].get_text().lower()
                            if "gb" in col1_text or "mb" in col1_text or "day" in col1_text or "global" in col1_text:
                                if plan_col_idx is None:
                                    plan_col_idx = 1
                            
                            # Check column 5 - usually contains the main price (larger number)
                            col5_text = cols[5].get_text().strip()
                            if col5_text and col5_text.replace(".", "").replace(",", "").isdigit():
                                if price_col_idx is None:
                                    price_col_idx = 5
                            
                            # Check column 3 - usually contains validity (small number, likely days)
                            col3_text = cols[3].get_text().strip()
                            if col3_text and col3_text.isdigit() and int(col3_text) <= 365:
                                if validity_col_idx is None:
                                    validity_col_idx = 3
                            
                            # Provider might be in column 0 (image/logo) or in the link
                            # Try to find provider name from link or image alt text
                            if provider_col_idx is None:
                                # Check if column 0 has an image with alt text or title
                                img = cols[0].find("img")
                                if img:
                                    alt_text = img.get("alt", "") or img.get("title", "")
                                    if alt_text:
                                        provider_col_idx = 0
                            
                            if price_col_idx is not None and plan_col_idx is not None:
                                break
                    
                    print(f"eSIM Tool: Inferred column positions - Price: {price_col_idx}, Provider: {provider_col_idx}, Plan: {plan_col_idx}, Validity: {validity_col_idx}")
                
                # Check if we're on a regional page (like Middle East) and need to filter by country
                is_regional_page = "middle-east" in url.lower() if url else False
                country_filter_keywords = []
                if is_regional_page:
                    # For Lebanon on Middle East page, filter by country keywords
                    if country_lower == "lebanon" or country_code.lower() == "lb":
                        country_filter_keywords = ["lebanon", "lb", "beirut"]
                    # Add more country filters as needed for other countries on regional pages
                    # For UAE on Middle East page
                    elif country_code.lower() == "ae" or "uae" in country_lower or "united arab emirates" in country_lower:
                        country_filter_keywords = ["uae", "united arab emirates", "emirates", "dubai", "abu dhabi"]
                
                for row_idx, row in enumerate(rows[start_idx:], start=start_idx):
                    cols = row.find_all("td")
                    # Need at least 4 columns (provider, plan, validity, price) - some tables might not have image column
                    if len(cols) < 4:
                        continue  # Skip invalid rows
                    
                    # If on regional page, filter rows by country
                    if is_regional_page and country_filter_keywords:
                        row_text = row.get_text().lower()
                        # Check if row contains country keywords
                        if not any(keyword in row_text for keyword in country_filter_keywords):
                            continue  # Skip rows that don't match the country
                    
                    # Use detected column positions if available, otherwise use smart defaults based on table structure
                    # Based on the debug output, the structure is: [empty, plan, data_gb, validity, price_per_gb, total_price, ...]
                    
                    if price_col_idx is not None and price_col_idx < len(cols):
                        price_col = cols[price_col_idx]
                    elif len(cols) >= 6:
                        # Try column 5 first (total price), fallback to column 4 (per GB price)
                        price_col = cols[5] if cols[5].get_text(strip=True) else cols[4]
                    elif len(cols) >= 5:
                        price_col = cols[4]
                    elif len(cols) >= 4:
                        price_col = cols[3]
                    else:
                        continue
                    
                    # Provider: Try to extract from image alt/title, or from link text
                    provider_text = ""
                    if provider_col_idx is not None and provider_col_idx < len(cols):
                        provider_col = cols[provider_col_idx]
                        provider_text = provider_col.get_text(strip=True)
                        # If empty, try to get from image
                        if not provider_text:
                            img = provider_col.find("img")
                            if img:
                                provider_text = img.get("alt", "") or img.get("title", "") or ""
                    
                    # If still no provider, try to extract from the plan name or link
                    if not provider_text:
                        # Check column 0 for image
                        img = cols[0].find("img") if len(cols) > 0 else None
                        if img:
                            provider_text = img.get("alt", "") or img.get("title", "") or ""
                    
                    # Plan: Column 1 typically contains the plan name
                    if plan_col_idx is not None and plan_col_idx < len(cols):
                        info_col = cols[plan_col_idx]
                    elif len(cols) >= 2:
                        info_col = cols[1]  # Column 1 usually has plan name like "Global 10GB – 1 Day"
                    else:
                        info_col = cols[0]
                    
                    # Validity: Column 3 typically contains days
                    if validity_col_idx is not None and validity_col_idx < len(cols):
                        validity_col = cols[validity_col_idx]
                    elif len(cols) >= 4:
                        validity_col = cols[3]  # Column 3 usually has validity days
                    else:
                        validity_col = cols[2] if len(cols) > 2 else cols[0]
                    
                    # Image column for link finding
                    img_col = cols[0] if len(cols) > 0 else None
                    provider_col = cols[0] if len(cols) > 0 else None
                    
                    # Find link - try multiple columns (skip None columns)
                    link = None
                    link_tag = None
                    
                    # Check column 9 which often has "View Details" link (based on terminal output)
                    if len(cols) > 9:
                        link_tag = cols[9].find("a")
                        # Also check if column 9 has a button or span with onclick/data attributes
                        if not link_tag:
                            btn = cols[9].find(["button", "span", "div"], onclick=True)
                            if btn:
                                onclick = btn.get("onclick", "")
                                # Try to extract URL from onclick handler
                                url_match = re.search(r'["\'](https?://[^"\']+)["\']', onclick)
                                if url_match:
                                    link = url_match.group(1)
                    
                    # Also check column 8 as fallback
                    if not link_tag and not link and len(cols) > 8:
                        link_tag = cols[8].find("a")
                    
                    # Check all columns for links if still not found
                    if not link_tag and not link:
                        for col_idx, col in enumerate(cols):
                            link_tag = col.find("a")
                            if link_tag:
                                break
                            # Also check for onclick handlers
                            btn = col.find(["button", "span", "div"], onclick=True)
                            if btn:
                                onclick = btn.get("onclick", "")
                                url_match = re.search(r'["\'](https?://[^"\']+)["\']', onclick)
                                if url_match:
                                    link = url_match.group(1)
                                    break
                    
                    # If still no link, try checking the row itself
                    if not link_tag and not link:
                        link_tag = row.find("a")
                    
                    # Extract href from link_tag if found
                    if link_tag and not link:
                        link = link_tag.get("href", "")
                        # Also check for data-href or other data attributes
                        if not link:
                            link = link_tag.get("data-href", "") or link_tag.get("data-url", "")
                    
                    # Make link absolute if relative
                    if link and not link.startswith("http"):
                        if link.startswith("/"):
                            link = f"https://esimradar.com{link}"
                        else:
                            link = f"https://esimradar.com/{link}"
                    
                    # Try to extract provider from link if still unknown
                    if link_tag and (not provider_text or provider_text == "Unknown Provider"):
                        # Link might contain provider name in URL or text
                        link_text = link_tag.get_text(strip=True)
                        if link_text and link_text != "View Details":
                            provider_text = link_text
                        # Or check URL for provider name
                        if provider_text == "Unknown Provider" and link and "/" in link:
                            url_parts = link.split("/")
                            for part in url_parts:
                                if part and part not in ["esim", "esimradar.com", "https:", "http:", ""]:
                                    # Might be provider name
                                    provider_text = part.replace("-", " ").title()
                                    break
                    
                    # Extract text from columns
                    # Provider text was already extracted above
                    plan_text = info_col.get_text(strip=True) if info_col else ""
                    validity_text = validity_col.get_text(strip=True) if validity_col else ""
                    price_text = price_col.get_text(strip=True) if price_col else ""
                    
                    # Clean up provider text
                    provider_text = provider_text.strip()
                    
                    # If provider is still empty, try to infer from plan name or other columns
                    if not provider_text:
                        # Sometimes provider is in the plan name or we can extract it from other context
                        # For now, we'll use "Unknown Provider" or try to get from link
                        provider_text = "Unknown Provider"
                    
                    # Debug: Log what we're extracting for first few rows
                    if row_idx < start_idx + 3:
                        print(f"eSIM Tool: Row {row_idx} - Provider: '{provider_text}', Plan: '{plan_text}', Validity: '{validity_text}', Price: '{price_text}'")
                        print(f"eSIM Tool: Row {row_idx} - Number of columns: {len(cols)}")
                        for i, col in enumerate(cols):
                            print(f"  Column {i}: '{col.get_text(strip=True)[:50]}'")
                    
                    bundle = {
                        "provider": provider_text,
                        "plan": plan_text,
                        "validity": validity_text,
                        "price": price_text,
                        "link": link
                    }
                    
                    # Only add if we have meaningful data (price is required, provider can be optional)
                    if bundle["price"] and bundle["plan"]:
                        bundles.append(bundle)
                
                if not bundles:
                    print(f"eSIM Tool: No bundles extracted from {len(rows)} rows")
                    # If we got 200, return success even if no bundles parsed
                    if response.status_code == 200:
                        return {
                            "error": False,
                            "country": country,
                            "bundles": [],
                            "total": 0,
                            "source": url,
                            "note": f"Page loaded successfully but no bundles could be extracted from {len(rows)} table rows. Please check the source URL directly.",
                            "recommended_providers": [
                                {"name": "Airalo", "url": "https://www.airalo.com"},
                                {"name": "Holafly", "url": "https://esim.holafly.com"},
                                {"name": "Nomad", "url": "https://www.getnomad.app"},
                                {"name": "Ubigi", "url": "https://www.ubigi.com"}
                            ]
                        }
                    # Only return error if we didn't get 200
                    return {
                        "error": True,
                        "error_message": f"No eSIM bundles found for {country}. The page may not have any available bundles or the structure is different.",
                        "error_code": "NO_BUNDLES",
                        "country": country,
                        "url": url,
                        "debug": f"Processed {len(rows)} table rows but found no valid bundles"
                    }
                
                # Apply limit to bundles
                total_bundles = len(bundles)
                bundles_limited = bundles[:limit]
                
                print(f"eSIM Tool: Successfully extracted {total_bundles} bundles for {country}, returning {len(bundles_limited)}")
                return {
                    "error": False,
                    "country": country,
                    "bundles": bundles_limited,
                    "count": len(bundles_limited),
                    "total_available": total_bundles,
                    "source": "esimradar.com",
                    "limited": total_bundles > limit
                }
                
        except httpx.HTTPStatusError as e:
            return {
                "error": True,
                "error_message": f"Could not fetch eSIM data for '{country}'. HTTP error: {e.response.status_code}",
                "error_code": "HTTP_ERROR",
                "country": country
            }
        except Exception as e:
            import traceback
            return {
                "error": True,
                "error_message": f"Error fetching eSIM bundles: {str(e)}",
                "error_code": "UNEXPECTED_ERROR",
                "country": country,
                "details": str(traceback.format_exc())[:200]
            }
    
    @mcp.tool(description=get_doc("get_holidays", "utilities"))
    async def get_holidays(country: str, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> Dict:
        """Get holidays for a specific country, optionally filtered by date.
        
        Args:
            country: Country name or ISO 3166-1 alpha-2 country code (e.g., "USA", "United States", "US", "Qatar", "QA", "Lebanon", "LB")
            year: Optional year (default: current year). Must be between 2000 and 2100.
            month: Optional month (1-12) to filter holidays. If provided, only holidays in that month are returned.
            day: Optional day (1-31) to filter holidays. If provided with month, only holidays on that specific date are returned.
            
        Returns:
            Dictionary with list of holidays including name, date, type, and description
        """
        import traceback
        try:
            # Check if API key is available
            if not CALENDARIFIC_API_KEY:
                return {
                    "error": True,
                    "error_message": "Calendarific API key is not configured. Please set CALENDARIFIC_API_KEY in your .env file.",
                    "error_code": "API_KEY_MISSING",
                    "suggestion": "Get a free API key from https://calendarific.com/ (free tier: 1,000 requests/month)"
                }
            
            # Map country names to ISO 3166-1 alpha-2 country codes
            country_code_map = {
                # Common country names to codes
                "united states": "US", "usa": "US", "america": "US",
                "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
                "canada": "CA",
                "australia": "AU",
                "new zealand": "NZ",
                "france": "FR",
                "germany": "DE",
                "italy": "IT",
                "spain": "ES",
                "netherlands": "NL",
                "belgium": "BE",
                "switzerland": "CH",
                "austria": "AT",
                "sweden": "SE",
                "norway": "NO",
                "denmark": "DK",
                "finland": "FI",
                "poland": "PL",
                "portugal": "PT",
                "greece": "GR",
                "ireland": "IE",
                "japan": "JP",
                "china": "CN",
                "south korea": "KR", "korea": "KR",
                "india": "IN",
                "singapore": "SG",
                "thailand": "TH",
                "malaysia": "MY",
                "indonesia": "ID",
                "philippines": "PH",
                "vietnam": "VN",
                "hong kong": "HK",
                "taiwan": "TW",
                "qatar": "QA",
                "uae": "AE", "united arab emirates": "AE", "emirates": "AE",
                "saudi arabia": "SA",
                "kuwait": "KW",
                "bahrain": "BH",
                "oman": "OM",
                "lebanon": "LB",
                "jordan": "JO",
                "egypt": "EG",
                "turkey": "TR", "türkiye": "TR",
                "israel": "IL",
                "south africa": "ZA",
                "brazil": "BR",
                "argentina": "AR",
                "mexico": "MX",
                "chile": "CL",
                "colombia": "CO",
                "peru": "PE",
                "russia": "RU",
                "ukraine": "UA",
            }
            
            # Normalize country input
            country_lower = country.strip().lower()
            
            # Try to get country code
            country_code = None
            if len(country.strip()) == 2 and country.strip().upper() in [v for v in country_code_map.values()]:
                # Already a country code
                country_code = country.strip().upper()
            elif country_lower in country_code_map:
                country_code = country_code_map[country_lower]
            else:
                # Try to find partial match
                for key, code in country_code_map.items():
                    if country_lower in key or key in country_lower:
                        country_code = code
                        break
            
            if not country_code:
                return {
                    "error": True,
                    "error_message": f"Country '{country}' not recognized. Please use a country name or ISO 3166-1 alpha-2 code (e.g., 'USA', 'US', 'Qatar', 'QA').",
                    "error_code": "INVALID_COUNTRY",
                    "suggestion": "Try using full country names like 'United States', 'Qatar', 'Lebanon', or ISO codes like 'US', 'QA', 'LB'"
                }
            
            # Determine year (default to current year)
            if year is None:
                year = datetime.now().year
            else:
                # Convert year to integer if it's a string
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    return {
                        "error": True,
                        "error_message": f"Year must be a valid integer. Provided: {year}",
                        "error_code": "INVALID_YEAR"
                    }
                
                # Validate year range
                if year < 2000 or year > 2100:
                    return {
                        "error": True,
                        "error_message": f"Year must be between 2000 and 2100. Provided: {year}",
                        "error_code": "INVALID_YEAR"
                    }
            
            # Convert month to integer if provided (handle string month names)
            if month is not None:
                try:
                    # If month is a string like "December", "Dec", "12", convert it
                    if isinstance(month, str):
                        month_lower = month.lower().strip()
                        month_map = {
                            "january": 1, "jan": 1,
                            "february": 2, "feb": 2,
                            "march": 3, "mar": 3,
                            "april": 4, "apr": 4,
                            "may": 5,
                            "june": 6, "jun": 6,
                            "july": 7, "jul": 7,
                            "august": 8, "aug": 8,
                            "september": 9, "sep": 9, "sept": 9,
                            "october": 10, "oct": 10,
                            "november": 11, "nov": 11,
                            "december": 12, "dec": 12
                        }
                        if month_lower in month_map:
                            month = month_map[month_lower]
                        else:
                            month = int(month)
                    else:
                        month = int(month)
                    
                    # Validate month range
                    if month < 1 or month > 12:
                        return {
                            "error": True,
                            "error_message": f"Month must be between 1 and 12. Provided: {month}",
                            "error_code": "INVALID_MONTH"
                        }
                except (ValueError, TypeError):
                    return {
                        "error": True,
                        "error_message": f"Month must be a valid integer (1-12) or month name. Provided: {month}",
                        "error_code": "INVALID_MONTH"
                    }
            
            # Convert day to integer if provided
            if day is not None:
                try:
                    day = int(day)
                    if day < 1 or day > 31:
                        return {
                            "error": True,
                            "error_message": f"Day must be between 1 and 31. Provided: {day}",
                            "error_code": "INVALID_DAY"
                        }
                except (ValueError, TypeError):
                    return {
                        "error": True,
                        "error_message": f"Day must be a valid integer (1-31). Provided: {day}",
                        "error_code": "INVALID_DAY"
                    }
            
            # Build API request
            params = {
                "api_key": CALENDARIFIC_API_KEY,
                "country": country_code,
                "year": year
            }
            
            # Make API request
            start_time = time.time()
            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    response = await client.get(CALENDARIFIC_API_URL, params=params)
                    response_time_ms = (time.time() - start_time) * 1000
                    response.raise_for_status()
                    data = response.json()
                    
                    # Log API call
                    success = data.get("meta", {}).get("code") == 200
                    error_msg = None
                    if not success:
                        error_msg = data.get("meta", {}).get("error", "Unknown error")
                    
                    log_api_call(
                        service="holidays",
                        endpoint="/holidays",
                        method="GET",
                        request_payload=params,
                        response_status=response.status_code,
                        response_time_ms=response_time_ms,
                        success=success,
                        error_message=error_msg
                    )
                except httpx.HTTPStatusError as e:
                    error_msg = None
                    if e.response.status_code == 401:
                        error_msg = "Invalid Calendarific API key. Please check your CALENDARIFIC_API_KEY in .env file."
                        error_code = "API_KEY_INVALID"
                    elif e.response.status_code == 429:
                        error_msg = "Calendarific API rate limit exceeded. Please try again later."
                        error_code = "RATE_LIMIT_EXCEEDED"
                    else:
                        error_msg = f"Calendarific API error: HTTP {e.response.status_code}"
                        error_code = "API_ERROR"
                    
                    log_api_call(
                        service="holidays",
                        endpoint="/holidays",
                        method="GET",
                        request_payload=params,
                        response_status=e.response.status_code,
                        response_time_ms=None,
                        success=False,
                        error_message=error_msg
                    )
                    
                    result = {
                        "error": True,
                        "error_message": error_msg,
                        "error_code": error_code
                    }
                    if error_code == "API_ERROR":
                        result["details"] = e.response.text[:200] if hasattr(e.response, 'text') else str(e)
                    return result
                except Exception as e:
                    error_msg = f"Error calling Calendarific API: {str(e)}"
                    log_api_call(
                        service="holidays",
                        endpoint="/holidays",
                        method="GET",
                        request_payload=params,
                        response_status=None,
                        response_time_ms=None,
                        success=False,
                        error_message=error_msg
                    )
                    return {
                        "error": True,
                        "error_message": error_msg,
                        "error_code": "API_ERROR"
                    }
            
            # Check API response
            if data.get("meta", {}).get("code") != 200:
                error_msg = data.get("meta", {}).get("error", "Unknown error")
                return {
                    "error": True,
                    "error_message": f"Calendarific API returned an error: {error_msg}",
                    "error_code": "API_ERROR"
                }
            
            # Extract holidays
            holidays = data.get("response", {}).get("holidays", [])
            
            # Debug logging
            print(f"[HOLIDAYS] API returned {len(holidays)} holidays for {country_code} in {year}")
            if month is not None:
                print(f"[HOLIDAYS] Filtering for month: {month} (type: {type(month)})")
            if len(holidays) > 0:
                # Show first holiday structure for debugging
                first_holiday = holidays[0]
                print(f"[HOLIDAYS] Sample holiday structure: date={first_holiday.get('date', {})}, name={first_holiday.get('name', 'N/A')[:50]}")
            
            if not holidays:
                return {
                    "error": False,
                    "country": country,
                    "country_code": country_code,
                    "year": year,
                    "holidays": [],
                    "count": 0,
                    "message": f"No holidays found for {country} in {year}"
                }
            
            # Filter by month and/or day if provided
            filtered_holidays = []
            skipped_count = 0
            parse_errors = []
            
            for holiday in holidays:
                # Try multiple date field formats
                holiday_date = holiday.get("date", {})
                if isinstance(holiday_date, dict):
                    # Try "iso" field first
                    date_str = holiday_date.get("iso", "")
                    if not date_str:
                        # Try "datetime" field
                        date_str = holiday_date.get("datetime", {}).get("iso", "")
                    if not date_str:
                        # Try direct date fields
                        date_str = holiday_date.get("date", "")
                elif isinstance(holiday_date, str):
                    date_str = holiday_date
                else:
                    skipped_count += 1
                    continue
                
                if not date_str:
                    skipped_count += 1
                    continue
                
                # Parse date - handle multiple formats
                try:
                    # Remove timezone info for parsing if present
                    date_str_clean = date_str.replace("Z", "").split("+")[0].split("-")[0] if "+" in date_str or "Z" in date_str else date_str
                    
                    # Try parsing with different formats
                    try:
                        holiday_datetime = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        # Try parsing just the date part (YYYY-MM-DD)
                        date_part = date_str.split("T")[0] if "T" in date_str else date_str.split(" ")[0]
                        holiday_datetime = datetime.strptime(date_part, "%Y-%m-%d")
                    
                    holiday_year = holiday_datetime.year
                    holiday_month = holiday_datetime.month
                    holiday_day = holiday_datetime.day
                    
                    # Apply filters (ensure month and day are integers)
                    if month is not None:
                        month_int = int(month)
                        if holiday_month != month_int:
                            if len(filtered_holidays) == 0 and skipped_count == 0:  # First holiday being checked
                                print(f"[HOLIDAYS DEBUG] Holiday '{holiday.get('name', 'Unknown')}' has month {holiday_month}, filtering for month {month_int} - SKIPPING")
                            continue
                        if day is not None:
                            day_int = int(day)
                            if holiday_day != day_int:
                                continue
                    
                    # Log first successful match
                    if len(filtered_holidays) == 0:
                        print(f"[HOLIDAYS DEBUG] First matching holiday: '{holiday.get('name', 'Unknown')}' on {holiday_datetime.strftime('%Y-%m-%d')} (month: {holiday_month})")
                    
                    # Format holiday data
                    holiday_info = {
                        "name": holiday.get("name", "Unknown Holiday"),
                        "date": date_str.split("T")[0] if "T" in date_str else date_str.split(" ")[0],  # Just the date part
                        "datetime": date_str,
                        "type": holiday.get("type", []),  # Array of types like ["National holiday", "Observance"]
                        "description": holiday.get("description", ""),
                        "country": holiday.get("country", {}).get("name", country) if isinstance(holiday.get("country"), dict) else holiday.get("country", country),
                        "locations": holiday.get("locations", ""),  # Where it's observed
                    }
                    
                    filtered_holidays.append(holiday_info)
                    
                except (ValueError, AttributeError, TypeError) as e:
                    # Skip holidays with invalid date format, but log for debugging
                    skipped_count += 1
                    parse_errors.append(f"Holiday '{holiday.get('name', 'Unknown')}': {str(e)[:50]}")
                    continue
            
            # Log if we skipped holidays
            if skipped_count > 0:
                print(f"[WARNING] Skipped {skipped_count} holidays due to date parsing issues")
                if parse_errors:
                    print(f"[DEBUG] Parse errors: {parse_errors[:3]}")  # Show first 3 errors
            
            # Sort by date
            filtered_holidays.sort(key=lambda x: x["date"])
            
            # Debug logging
            print(f"[HOLIDAYS] After filtering: {len(filtered_holidays)} holidays found")
            if skipped_count > 0:
                print(f"[HOLIDAYS] Skipped {skipped_count} holidays due to parsing issues")
            
            return {
                "error": False,
                "country": country,
                "country_code": country_code,
                "year": year,
                "month": month,
                "day": day,
                "holidays": filtered_holidays,
                "count": len(filtered_holidays),
                "source": "calendarific.com",
                "total_holidays_in_year": len(holidays),  # Include total for debugging
                "skipped_count": skipped_count  # Include skipped count for debugging
            }
            
        except Exception as e:
            import traceback
            return {
                "error": True,
                "error_message": f"Error fetching holidays: {str(e)}",
                "error_code": "UNEXPECTED_ERROR",
                "country": country,
                "details": str(traceback.format_exc())[:200]
            }

