"""Utilities-related tools for the MCP server (weather, currency, date/time, eSIM)."""

import os
import httpx
import json
import requests
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv
from tools.doc_loader import get_doc
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    params = {
                        "q": location,
                        "appid": WEATHER_API_KEY,
                        "units": "metric"  # Use metric for Celsius
                    }
                    response = await client.get(WEATHER_API_URL, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    url = f"https://wttr.in/{location}?format=j1"
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
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
            return {
                "error": True,
                "error_message": f"Could not fetch weather data for '{location}'. Please check the location name and try again.",
                "error_code": "API_ERROR"
            }
        except Exception as e:
            return {
                "error": True,
                "error_message": f"Error fetching weather: {str(e)}",
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
    async def get_real_time_date_time(location: str = "UTC") -> Dict:
        """Get real-time date and time for a specific country or city.
        
        Args:
            location: Country name or city name (e.g., "New York", "London", "Japan", "Lebanon"). 
                     If not specified or "global"/"utc"/"gmt", defaults to UTC.
            
        Returns:
            Dictionary with current date, time, timezone, and related information
        """
        # Method 1: Try using Python's zoneinfo (Python 3.9+) or pytz as fallback
        try:
            location_lower = location.lower().strip()
            
            # Handle special cases: global, utc, gmt -> use UTC
            if location_lower in ["global", "utc", "gmt", ""]:
                location = "UTC"
                location_lower = "utc"
                timezone = "UTC"
            else:
                timezone = None
            
            # Comprehensive timezone mapping
            timezone_map = {
                # Special cases
                "utc": "UTC", "gmt": "UTC", "global": "UTC",
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
            
            # Try to find timezone in map (if not already set to UTC)
            if not timezone:
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
                if timezone == "UTC":
                    tz = ZoneInfo("UTC")
                else:
                    tz = ZoneInfo(timezone)
            except (ImportError, Exception):
                # Fallback to pytz if zoneinfo not available
                try:
                    import pytz
                    if timezone == "UTC":
                        tz = pytz.UTC
                    else:
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
            # Handle special cases: global, utc, gmt -> use UTC
            if location_lower in ["global", "utc", "gmt", ""]:
                timezone = "UTC"
                location = "UTC"
            else:
                timezone = None
            
            # Use provided timezone_map if available, otherwise use default
            if not timezone_map:
                timezone_map = {
                # Special cases
                "utc": "UTC", "gmt": "UTC", "global": "UTC",
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
            
            # Try to find timezone in map (if not already set to UTC)
            if not timezone:
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
            
            # For UTC, use a simpler approach
            if timezone == "UTC":
                from datetime import timezone as tz
                now = datetime.now(tz.utc)
                return {
                    "error": False,
                    "location": "UTC",
                    "timezone": "UTC",
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "day_of_week": now.strftime("%A"),
                    "utc_offset": "+00:00",
                    "abbreviation": "UTC",
                    "timezone_name": "UTC"
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
    async def get_esim_bundles(country: str) -> Dict:
        """Get available eSIM bundles for a specific country from esimradar.com.
        
        Args:
            country: Country name (e.g., "Qatar", "USA", "UAE", "Lebanon", "Japan")
            
        Returns:
            Dictionary with list of eSIM bundles including provider, plan, validity, price, and link
        """
        try:
            # Map country names to esimradar.com URL patterns
            # Format: (country_name_slug, country_code, country_short_slug)
            # country_name_slug: for /esim/{name}/ pattern (e.g., "united-arab-emirates")
            # country_short_slug: for /esim-{short}/ pattern (e.g., "qatar", "usa")
            # country_code: for /esim-{code}/ pattern (e.g., "qa", "us")
            country_mapping = {
                # Middle East
                "qatar": ("qatar", "qa", "qatar"),
                "uae": ("united-arab-emirates", "ae", "uae"),
                "united arab emirates": ("united-arab-emirates", "ae", "uae"),
                "emirates": ("united-arab-emirates", "ae", "uae"),
                "dubai": ("united-arab-emirates", "ae", "uae"),  # Dubai -> UAE
                "saudi arabia": ("saudi-arabia", "sa", "saudi-arabia"),
                "kuwait": ("kuwait", "kw", "kuwait"),
                "bahrain": ("bahrain", "bh", "bahrain"),
                "oman": ("oman", "om", "oman"),
                "lebanon": ("lebanon", "lb", "lebanon"),
                "jordan": ("jordan", "jo", "jordan"),
                "egypt": ("egypt", "eg", "egypt"),
                "turkey": ("turkey", "tr", "turkey"),
                # Asia
                "japan": ("japan", "jp", "japan"),
                "china": ("china", "cn", "china"),
                "south korea": ("south-korea", "kr", "south-korea"),
                "korea": ("south-korea", "kr", "south-korea"),
                "singapore": ("singapore", "sg", "singapore"),
                "thailand": ("thailand", "th", "thailand"),
                "malaysia": ("malaysia", "my", "malaysia"),
                "indonesia": ("indonesia", "id", "indonesia"),
                "philippines": ("philippines", "ph", "philippines"),
                "vietnam": ("vietnam", "vn", "vietnam"),
                "india": ("india", "in", "india"),
                "hong kong": ("hong-kong", "hk", "hong-kong"),
                "taiwan": ("taiwan", "tw", "taiwan"),
                # Europe
                "uk": ("united-kingdom", "gb", "uk"),
                "united kingdom": ("united-kingdom", "gb", "uk"),
                "britain": ("united-kingdom", "gb", "uk"),
                "france": ("france", "fr", "france"),
                "germany": ("germany", "de", "germany"),
                "italy": ("italy", "it", "italy"),
                "spain": ("spain", "es", "spain"),
                "netherlands": ("netherlands", "nl", "netherlands"),
                "belgium": ("belgium", "be", "belgium"),
                "switzerland": ("switzerland", "ch", "switzerland"),
                "austria": ("austria", "at", "austria"),
                "sweden": ("sweden", "se", "sweden"),
                "norway": ("norway", "no", "norway"),
                "denmark": ("denmark", "dk", "denmark"),
                "finland": ("finland", "fi", "finland"),
                "ireland": ("ireland", "ie", "ireland"),
                "portugal": ("portugal", "pt", "portugal"),
                "greece": ("greece", "gr", "greece"),
                "poland": ("poland", "pl", "poland"),
                "czech republic": ("czech-republic", "cz", "czech-republic"),
                "hungary": ("hungary", "hu", "hungary"),
                "russia": ("russia", "ru", "russia"),
                # Americas
                "usa": ("united-states", "us", "usa"),
                "united states": ("united-states", "us", "usa"),
                "us": ("united-states", "us", "usa"),
                "canada": ("canada", "ca", "canada"),
                "mexico": ("mexico", "mx", "mexico"),
                "brazil": ("brazil", "br", "brazil"),
                "argentina": ("argentina", "ar", "argentina"),
                "chile": ("chile", "cl", "chile"),
                "colombia": ("colombia", "co", "colombia"),
                # Oceania
                "australia": ("australia", "au", "australia"),
                "new zealand": ("new-zealand", "nz", "new-zealand"),
                # Africa
                "south africa": ("south-africa", "za", "south-africa"),
            }
            
            country_lower = country.lower().strip()
            
            # Try to find country in mapping
            country_name_slug, country_code, country_short_slug = None, None, None
            if country_lower in country_mapping:
                country_name_slug, country_code, country_short_slug = country_mapping[country_lower]
            else:
                # Try variations
                variations = [
                    country_lower.replace("the ", ""),
                    country_lower.replace(" country", ""),
                ]
                for var in variations:
                    if var in country_mapping:
                        country_name_slug, country_code, country_short_slug = country_mapping[var]
                        break
                
                if not country_name_slug:
                    return {
                        "error": True,
                        "error_message": f"Country '{country}' not found in eSIM database. Please try using a supported country name.",
                        "error_code": "INVALID_COUNTRY",
                        "suggestion": "Try using country names like 'Qatar', 'USA', 'UAE', 'Japan', 'Lebanon', etc."
                    }
            
            # Generate URLs to try in order of likelihood
            # Based on testing, different countries use different URL patterns
            urls_to_try = [
                # Pattern 1: /esim/{country-name-slug}/ (works for UAE, Qatar, Japan, etc.)
                f"https://esimradar.com/esim/{country_name_slug}/",
                # Pattern 2: /esim-{country-short-slug}/ (works for Qatar, Japan, USA, etc.)
                f"https://esimradar.com/esim-{country_short_slug}/",
                # Pattern 3: /esim-{country-code}/ (works for some countries like QA, US)
                f"https://esimradar.com/esim-{country_code.lower()}/",
            ]
            
            # For Lebanon, also try Middle East regional page (Lebanon is included there)
            if country_lower == "lebanon" or country_code.lower() == "lb":
                urls_to_try.insert(1, "https://esimradar.com/esim/middle-east/")
                urls_to_try.insert(2, "https://esimradar.com/esim-middle-east/")
            
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
                    return {
                        "error": True,
                        "error_message": f"Could not fetch eSIM data for '{country}'. The country may not be available on esimradar.com or the website structure has changed.",
                        "error_code": "HTTP_ERROR",
                        "country": country,
                        "urls_tried": urls_to_try
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
                
                # Find the table with eSIM bundles - try multiple possible table IDs
                table = soup.find("table", id="table_1")
                
                # If table_1 not found, try other common table IDs or just find any table
                if not table:
                    # Try alternative table IDs
                    for table_id in ["table_1", "esim-table", "bundles-table", "data-table"]:
                        table = soup.find("table", id=table_id)
                        if table:
                            break
                    
                    # If still not found, try to find any table with class or data attributes
                    if not table:
                        table = soup.find("table", class_=lambda x: x and ("esim" in str(x).lower() or "bundle" in str(x).lower()))
                    
                    # Last resort: find any table
                    if not table:
                        tables = soup.find_all("table")
                        if tables:
                            table = tables[0]  # Use first table found
                
                if not table:
                    # Debug: Check what tables exist
                    all_tables = soup.find_all("table")
                    table_info = [{"id": t.get("id", "no-id"), "class": t.get("class", [])} for t in all_tables[:5]]
                    return {
                        "error": True,
                        "error_message": f"Could not find eSIM data table for {country}. The website structure may have changed.",
                        "error_code": "PARSING_ERROR",
                        "country": country,
                        "url": url,
                        "debug_info": f"Found {len(all_tables)} table(s) on page. First few: {table_info}"
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
                    # Check column 8 which often has "View Details" link, or check all columns
                    if len(cols) > 8:
                        link_tag = cols[8].find("a")
                    
                    if not link_tag:
                        cols_to_check = [c for c in [img_col, provider_col, info_col] if c is not None]
                        for col in cols_to_check:
                            link_tag = col.find("a")
                            if link_tag:
                                break
                    
                    if link_tag:
                        link = link_tag.get("href", "")
                        # Make link absolute if relative
                        if link and not link.startswith("http"):
                            if link.startswith("/"):
                                link = f"https://esimradar.com{link}"
                            else:
                                link = f"https://esimradar.com/{link}"
                        
                        # Try to extract provider from link if still unknown
                        if not provider_text or provider_text == "Unknown Provider":
                            # Link might contain provider name in URL or text
                            link_text = link_tag.get_text(strip=True)
                            if link_text and link_text != "View Details":
                                provider_text = link_text
                            # Or check URL for provider name
                            if provider_text == "Unknown Provider" and "/" in link:
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
                    return {
                        "error": True,
                        "error_message": f"No eSIM bundles found for {country}. The page may not have any available bundles or the structure is different.",
                        "error_code": "NO_BUNDLES",
                        "country": country,
                        "url": url,
                        "debug": f"Processed {len(rows)} table rows but found no valid bundles"
                    }
                
                print(f"eSIM Tool: Successfully extracted {len(bundles)} bundles for {country}")
                return {
                    "error": False,
                    "country": country,
                    "bundles": bundles,
                    "count": len(bundles),
                    "source": "esimradar.com"
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
            # Convert to int if it's a string (LLM might pass strings)
            if year is None:
                year = datetime.now().year
            else:
                try:
                    if isinstance(year, str):
                        year = int(year)
                    elif not isinstance(year, int):
                        year = int(year)
                except (ValueError, TypeError):
                    return {
                        "error": True,
                        "error_message": f"Invalid year format: {year}. Year must be a number between 2000 and 2100.",
                        "error_code": "INVALID_YEAR"
                    }
                
                if year < 2000 or year > 2100:
                    return {
                        "error": True,
                        "error_message": f"Year must be between 2000 and 2100. Provided: {year}",
                        "error_code": "INVALID_YEAR"
                    }
            
            # Convert month to int if it's a string
            if month is not None:
                try:
                    if isinstance(month, str):
                        month = int(month)
                    elif not isinstance(month, int):
                        month = int(month)
                    if month < 1 or month > 12:
                        return {
                            "error": True,
                            "error_message": f"Month must be between 1 and 12. Provided: {month}",
                            "error_code": "INVALID_MONTH"
                        }
                except (ValueError, TypeError):
                    return {
                        "error": True,
                        "error_message": f"Invalid month format: {month}. Month must be a number between 1 and 12.",
                        "error_code": "INVALID_MONTH"
                    }
            
            # Convert day to int if it's a string
            if day is not None:
                try:
                    if isinstance(day, str):
                        day = int(day)
                    elif not isinstance(day, int):
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
                        "error_message": f"Invalid day format: {day}. Day must be a number between 1 and 31.",
                        "error_code": "INVALID_DAY"
                    }
            
            # Build API request
            params = {
                "api_key": CALENDARIFIC_API_KEY,
                "country": country_code,
                "year": year
            }
            
            # Make API request
            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    response = await client.get(CALENDARIFIC_API_URL, params=params)
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        return {
                            "error": True,
                            "error_message": "Invalid Calendarific API key. Please check your CALENDARIFIC_API_KEY in .env file.",
                            "error_code": "API_KEY_INVALID"
                        }
                    elif e.response.status_code == 429:
                        return {
                            "error": True,
                            "error_message": "Calendarific API rate limit exceeded. Please try again later.",
                            "error_code": "RATE_LIMIT_EXCEEDED"
                        }
                    else:
                        return {
                            "error": True,
                            "error_message": f"Calendarific API error: HTTP {e.response.status_code}",
                            "error_code": "API_ERROR",
                            "details": e.response.text[:200] if hasattr(e.response, 'text') else str(e)
                        }
                except Exception as e:
                    return {
                        "error": True,
                        "error_message": f"Error calling Calendarific API: {str(e)}",
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
            for holiday in holidays:
                holiday_date = holiday.get("date", {}).get("iso", "")
                if not holiday_date:
                    continue
                
                # Parse date
                try:
                    holiday_datetime = datetime.fromisoformat(holiday_date.replace("Z", "+00:00"))
                    holiday_year = holiday_datetime.year
                    holiday_month = holiday_datetime.month
                    holiday_day = holiday_datetime.day
                    
                    # Apply filters
                    if month is not None:
                        if holiday_month != month:
                            continue
                        if day is not None:
                            if holiday_day != day:
                                continue
                    
                    # Format holiday data
                    holiday_info = {
                        "name": holiday.get("name", "Unknown Holiday"),
                        "date": holiday_date.split("T")[0],  # Just the date part
                        "datetime": holiday_date,
                        "type": holiday.get("type", []),  # Array of types like ["National holiday", "Observance"]
                        "description": holiday.get("description", ""),
                        "country": holiday.get("country", {}).get("name", country),
                        "locations": holiday.get("locations", ""),  # Where it's observed
                    }
                    
                    filtered_holidays.append(holiday_info)
                    
                except (ValueError, AttributeError) as e:
                    # Skip holidays with invalid date format
                    continue
            
            # Sort by date
            filtered_holidays.sort(key=lambda x: x["date"])
            
            return {
                "error": False,
                "country": country,
                "country_code": country_code,
                "year": year,
                "month": month,
                "day": day,
                "holidays": filtered_holidays,
                "count": len(filtered_holidays),
                "source": "calendarific.com"
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

