"""Flight-related tools for the MCP server."""

import os
import re
import requests
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from dotenv import load_dotenv
from tools.doc_loader import get_doc

# SerpAPI configuration
API_KEY = os.getenv("SERPAPI_KEY", "5ace04863364568bc6e013757ecaea56d0dc7d3e66401e9553d9e5e21c259453")
BASE_URL = "https://serpapi.com/search"
CURRENT_CURRENCY = "USD"


# -------------------------
# Utility helpers
# -------------------------

def _normalize_location(location: str) -> str:
    """Convert country/city names to airport codes when possible.
    
    Args:
        location: Airport code, city name, or country name
        
    Returns:
        Normalized location (airport code if mapping found, otherwise uppercase)
    """
    location = location.strip().upper()
    
    # Mapping of common country/city names to main airport codes
    location_map = {
    # ----------------------------
    # AFRICA — 54 COUNTRIES + CITIES
    # ----------------------------
    "ALGERIA": "ALG",
    "ALGIERS": "ALG",
    "ORAN": "ORN",

    "ANGOLA": "LAD",
    "LUANDA": "LAD",

    "BENIN": "COO",
    "COTONOU": "COO",

    "BOTSWANA": "GBE",
    "GABORONE": "GBE",

    "BURKINA FASO": "OUA",
    "OUAGADOUGOU": "OUA",

    "BURUNDI": "BJM",
    "BUJUMBURA": "BJM",

    "CABO VERDE": "RAI",
    "PRAIA": "RAI",

    "CAMEROON": "NSI",
    "YAOUNDE": "NSI",
    "DOUALA": "DLA",

    "CENTRAL AFRICAN REPUBLIC": "BGF",
    "BANGUI": "BGF",

    "CHAD": "NDJ",
    "N'DJAMENA": "NDJ",

    "COMOROS": "HAH",
    "MORONI": "HAH",

    "CONGO": "BZV",
    "BRAZZAVILLE": "BZV",
    "POINTE-NOIRE": "PNR",

    "DEMOCRATIC REPUBLIC OF THE CONGO": "FIH",
    "KINSHASA": "FIH",
    "LUBUMBASHI": "FBM",

    "DJIBOUTI": "JIB",
    "DJIBOUTI CITY": "JIB",

    "EGYPT": "CAI",
    "CAIRO": "CAI",
    "ALEXANDRIA": "HBE",
    "SHARM EL SHEIKH": "SSH",
    "HURGHADA": "HRG",
    "LUXOR": "LXR",

    "EQUATORIAL GUINEA": "SSG",
    "MALABO": "SSG",

    "ERITREA": "ASM",
    "ASMARA": "ASM",

    "ESWATINI": "SHO",
    "MBABANE": "SHO",

    "ETHIOPIA": "ADD",
    "ADDIS ABABA": "ADD",

    "GABON": "LBV",
    "LIBREVILLE": "LBV",

    "GAMBIA": "BJL",
    "BANJUL": "BJL",

    "GHANA": "ACC",
    "ACCRA": "ACC",
    "KUMASI": "KMS",

    "GUINEA": "CKY",
    "CONAKRY": "CKY",

    "GUINEA-BISSAU": "OXB",
    "BISSAU": "OXB",

    "KENYA": "NBO",
    "NAIROBI": "NBO",
    "MOMBASA": "MBA",

    "LESOTHO": "MSU",
    "MASERU": "MSU",

    "LIBERIA": "ROB",
    "MONROVIA": "ROB",

    "LIBYA": "TIP",
    "TRIPOLI": "TIP",
    "BENGHAZI": "BEN",

    "MADAGASCAR": "TNR",
    "ANTANANARIVO": "TNR",

    "MALAWI": "LLW",
    "LILONGWE": "LLW",
    "BLANTYRE": "BLZ",

    "MALI": "BKO",
    "BAMAKO": "BKO",

    "MAURITANIA": "NKC",
    "NOUAKCHOTT": "NKC",

    "MAURITIUS": "MRU",
    "PORT LOUIS": "MRU",

    "MOROCCO": "CMN",
    "CASABLANCA": "CMN",
    "MARRAKECH": "RAK",
    "TANGIER": "TNG",
    "AGADIR": "AGA",

    "MOZAMBIQUE": "MPM",
    "MAPUTO": "MPM",

    "NAMIBIA": "WDH",
    "WINDHOEK": "WDH",

    "NIGER": "NIM",
    "NIAMEY": "NIM",

    "NIGERIA": "LOS",
    "LAGOS": "LOS",
    "ABUJA": "ABV",
    "PORT HARCOURT": "PHC",
    "KANO": "KAN",

    "RWANDA": "KGL",
    "KIGALI": "KGL",

    "SAO TOME AND PRINCIPE": "TMS",
    "SAO TOME": "TMS",

    "SENEGAL": "DSS",
    "DAKAR": "DSS",

    "SEYCHELLES": "SEZ",
    "VICTORIA": "SEZ",

    "SIERRA LEONE": "FNA",
    "FREETOWN": "FNA",

    "SOMALIA": "MGQ",
    "MOGADISHU": "MGQ",

    "SOUTH AFRICA": "JNB",
    "JOHANNESBURG": "JNB",
    "CAPE TOWN": "CPT",
    "DURBAN": "DUR",
    "PORT ELIZABETH": "PLZ",

    "SOUTH SUDAN": "JUB",
    "JUBA": "JUB",

    "SUDAN": "KRT",
    "KHARTOUM": "KRT",

    "TANZANIA": "DAR",
    "DAR ES SALAAM": "DAR",
    "KILIMANJARO": "JRO",
    "ZANZIBAR": "ZNZ",

    "TOGO": "LFW",
    "LOME": "LFW",

    "TUNISIA": "TUN",
    "TUNIS": "TUN",

    "UGANDA": "EBB",
    "ENTEBBE": "EBB",

    "ZAMBIA": "LUN",
    "LUSAKA": "LUN",
    "NDOLA": "NLA",

    "ZIMBABWE": "HRE",
    "HARARE": "HRE",
    "VICTORIA FALLS": "VFA",

    # -----------------------------------------------------------
    # ASIA — 48 COUNTRIES + MAJOR CITIES
    # -----------------------------------------------------------
    "AFGHANISTAN": "KBL",
    "KABUL": "KBL",

    "ARMENIA": "EVN",
    "YEREVAN": "EVN",

    "AZERBAIJAN": "GYD",
    "BAKU": "GYD",

    "BAHRAIN": "BAH",
    "MANAMA": "BAH",

    "BANGLADESH": "DAC",
    "DHAKA": "DAC",
    "CHITTAGONG": "CGP",

    "BHUTAN": "PBH",
    "PARO": "PBH",

    "BRUNEI": "BWN",
    "BANDAR SERI BEGAWAN": "BWN",

    "CAMBODIA": "PNH",
    "PHNOM PENH": "PNH",
    "SIEM REAP": "REP",

    "CHINA": "PEK",
    "BEIJING": "PEK",
    "SHANGHAI": "PVG",
    "GUANGZHOU": "CAN",
    "SHENZHEN": "SZX",
    "CHENGDU": "CTU",
    "HONG KONG": "HKG",
    "MACAU": "MFM",

    "CYPRUS": "LCA",
    "LARNACA": "LCA",
    "PAPHOS": "PFO",

    "GEORGIA": "TBS",
    "TBILISI": "TBS",
    "BATUMI": "BUS",

    "INDIA": "DEL",
    "DELHI": "DEL",
    "MUMBAI": "BOM",
    "BANGALORE": "BLR",
    "CHENNAI": "MAA",
    "KOLKATA": "CCU",
    "HYDERABAD": "HYD",
    "GOA": "GOI",
    "KOCHI": "COK",
    "AHMEDABAD": "AMD",

    "INDONESIA": "CGK",
    "JAKARTA": "CGK",
    "BALI": "DPS",
    "SURABAYA": "SUB",
    "MEDAN": "KNO",

    "IRAN": "IKA",
    "TEHRAN": "IKA",
    "MASHHAD": "MHD",
    "SHIRAZ": "SYZ",

    "IRAQ": "BGW",
    "BAGHDAD": "BGW",
    "ERBIL": "EBL",
    "BASRA": "BSR",

    "ISRAEL": "TLV",
    "TEL AVIV": "TLV",
    "EILAT": "ETM",

    "JAPAN": "NRT",
    "TOKYO": "NRT",
    "OSAKA": "KIX",
    "NAGOYA": "NGO",
    "FUKUOKA": "FUK",
    "SAPPORO": "CTS",

    "JORDAN": "AMM",
    "AMMAN": "AMM",
    "AQABA": "AQJ",

    "KAZAKHSTAN": "ALA",
    "ALMATY": "ALA",
    "ASTANA": "NQZ",

    "KUWAIT": "KWI",
    "KUWAIT CITY": "KWI",

    "KYRGYZSTAN": "FRU",
    "BISHKEK": "FRU",

    "LAOS": "VTE",
    "VIENTIANE": "VTE",
    "LUANG PRABANG": "LPQ",

    "LEBANON": "BEY",
    "BEIRUT": "BEY",

    "MALAYSIA": "KUL",
    "KUALA LUMPUR": "KUL",
    "PENANG": "PEN",
    "KOTA KINABALU": "BKI",

    "MALDIVES": "MLE",
    "MALE": "MLE",

    "MONGOLIA": "UBN",
    "ULAANBAATAR": "UBN",

    "MYANMAR": "RGN",
    "YANGON": "RGN",
    "MANDALAY": "MDL",

    "NEPAL": "KTM",
    "KATHMANDU": "KTM",

    "OMAN": "MCT",
    "MUSCAT": "MCT",
    "SALALAH": "SLL",

    "PAKISTAN": "ISB",
    "ISLAMABAD": "ISB",
    "KARACHI": "KHI",
    "LAHORE": "LHE",

    "PHILIPPINES": "MNL",
    "MANILA": "MNL",
    "CEBU": "CEB",

    "QATAR": "DOH",
    "DOHA": "DOH",

    "SAUDI ARABIA": "RUH",
    "RIYADH": "RUH",
    "JEDDAH": "JED",
    "DAMMAM": "DMM",
    "MEDINA": "MED",

    "SINGAPORE": "SIN",

    "SOUTH KOREA": "ICN",
    "SEOUL": "ICN",
    "BUSAN": "PUS",

    "SRI LANKA": "CMB",
    "COLOMBO": "CMB",

    "SYRIA": "DAM",
    "DAMASCUS": "DAM",

    "TAIWAN": "TPE",
    "TAIPEI": "TPE",
    "KAOHSIUNG": "KHH",

    "TAJIKISTAN": "DYU",
    "DUSHANBE": "DYU",

    "THAILAND": "BKK",
    "BANGKOK": "BKK",
    "PHUKET": "HKT",
    "CHIANG MAI": "CNX",

    "TURKEY": "IST",
    "ISTANBUL": "IST",
    "ANKARA": "ESB",
    "IZMIR": "ADB",
    "ANTALYA": "AYT",

    "UNITED ARAB EMIRATES": "DXB",
    "DUBAI": "DXB",
    "ABU DHABI": "AUH",
    "SHARJAH": "SHJ",

    "UZBEKISTAN": "TAS",
    "TASHKENT": "TAS",
    "SAMARKAND": "SKD",

    "VIETNAM": "SGN",
    "HO CHI MINH": "SGN",
    "HANOI": "HAN",

    # -----------------------------------------------------------
    # EUROPE — 44 COUNTRIES + ALL MAJOR CITIES
    # -----------------------------------------------------------
    "ALBANIA": "TIA",
    "TIRANA": "TIA",

    "AUSTRIA": "VIE",
    "VIENNA": "VIE",
    "SALZBURG": "SZG",

    "BELARUS": "MSQ",
    "MINSK": "MSQ",

    "BELGIUM": "BRU",
    "BRUSSELS": "BRU",
    "ANTWERP": "ANR",

    "BULGARIA": "SOF",
    "SOFIA": "SOF",
    "VARNA": "VAR",

    "CROATIA": "ZAG",
    "ZAGREB": "ZAG",
    "SPLIT": "SPU",
    "DUBROVNIK": "DBV",

    "CZECH REPUBLIC": "PRG",
    "PRAGUE": "PRG",

    "DENMARK": "CPH",
    "COPENHAGEN": "CPH",

    "ESTONIA": "TLL",
    "TALLINN": "TLL",

    "FINLAND": "HEL",
    "HELSINKI": "HEL",

    "FRANCE": "CDG",
    "PARIS": "CDG",
    "NICE": "NCE",
    "LYON": "LYS",
    "MARSEILLE": "MRS",
    "TOULOUSE": "TLS",
    "BORDEAUX": "BOD",

    "GERMANY": "FRA",
    "FRANKFURT": "FRA",
    "MUNICH": "MUC",
    "BERLIN": "BER",
    "HAMBURG": "HAM",
    "DUSSELDORF": "DUS",
    "STUTTGART": "STR",
    "COLOGNE": "CGN",

    "GREECE": "ATH",
    "ATHENS": "ATH",
    "THESSALONIKI": "SKG",
    "HERAKLION": "HER",

    "HUNGARY": "BUD",
    "BUDAPEST": "BUD",

    "ICELAND": "KEF",
    "REYKJAVIK": "KEF",

    "IRELAND": "DUB",
    "DUBLIN": "DUB",
    "CORK": "ORK",

    "ITALY": "FCO",
    "ROME": "FCO",
    "MILAN": "MXP",
    "VENICE": "VCE",
    "NAPLES": "NAP",
    "FLORENCE": "FLR",
    "BOLOGNA": "BLQ",
    "PALERMO": "PMO",
    "CATANIA": "CTA",

    "LATVIA": "RIX",
    "RIGA": "RIX",

    "LITHUANIA": "VNO",
    "VILNIUS": "VNO",

    "LUXEMBOURG": "LUX",
    "LUXEMBOURG CITY": "LUX",

    "MALTA": "MLA",
    "VALLETTA": "MLA",

    "MOLDOVA": "KIV",
    "CHISINAU": "KIV",

    "MONACO": "NCE",

    "MONTENEGRO": "TGD",
    "PODGORICA": "TGD",

    "NETHERLANDS": "AMS",
    "AMSTERDAM": "AMS",
    "ROTTERDAM": "RTM",

    "NORTH MACEDONIA": "SKP",
    "SKOPJE": "SKP",

    "NORWAY": "OSL",
    "OSLO": "OSL",
    "BERGEN": "BGO",

    "POLAND": "WAW",
    "WARSAW": "WAW",
    "KRAKOW": "KRK",

    "PORTUGAL": "LIS",
    "LISBON": "LIS",
    "PORTO": "OPO",
    "FARO": "FAO",

    "ROMANIA": "OTP",
    "BUCHAREST": "OTP",
    "CLUJ": "CLJ",

    "RUSSIA": "SVO",
    "MOSCOW": "SVO",
    "SAINT PETERSBURG": "LED",

    "SERBIA": "BEG",
    "BELGRADE": "BEG",

    "SLOVAKIA": "BTS",
    "BRATISLAVA": "BTS",

    "SLOVENIA": "LJU",
    "LJUBLJANA": "LJU",

    "SPAIN": "MAD",
    "MADRID": "MAD",
    "BARCELONA": "BCN",
    "MALAGA": "AGP",
    "SEVILLE": "SVQ",
    "VALENCIA": "VLC",
    "BILBAO": "BIO",
    "PALMA": "PMI",
    "IBIZA": "IBZ",

    "SWEDEN": "ARN",
    "STOCKHOLM": "ARN",
    "GOTHENBURG": "GOT",

    "SWITZERLAND": "ZRH",
    "ZURICH": "ZRH",
    "GENEVA": "GVA",
    "BASEL": "BSL",

    "UKRAINE": "IEV",
    "KYIV": "IEV",
    "LVIV": "LWO",

    "UNITED KINGDOM": "LHR",
    "LONDON": "LHR",
    "MANCHESTER": "MAN",
    "EDINBURGH": "EDI",
    "BIRMINGHAM": "BHX",
    "GLASGOW": "GLA",
    "BRISTOL": "BRS",
    "LIVERPOOL": "LPL",
    "BELFAST": "BFS",

    # -----------------------------------------------------------
    # NORTH AMERICA — USA + CANADA + 21 OTHER COUNTRIES
    # -----------------------------------------------------------
    "UNITED STATES": "NYC",
    "NEW YORK": "NYC",
    "LOS ANGELES": "LAX",
    "CHICAGO": "ORD",
    "MIAMI": "MIA",
    "SAN FRANCISCO": "SFO",
    "ATLANTA": "ATL",
    "DALLAS": "DFW",
    "HOUSTON": "IAH",
    "LAS VEGAS": "LAS",
    "SEATTLE": "SEA",
    "BOSTON": "BOS",
    "DENVER": "DEN",
    "ORLANDO": "MCO",
    "PHILADELPHIA": "PHL",
    "WASHINGTON": "IAD",
    "DETROIT": "DTW",
    "PHOENIX": "PHX",
    "MINNEAPOLIS": "MSP",
    "CHARLOTTE": "CLT",
    "SAN DIEGO": "SAN",

    "CANADA": "YYZ",
    "TORONTO": "YYZ",
    "VANCOUVER": "YVR",
    "MONTREAL": "YUL",
    "CALGARY": "YYC",
    "OTTAWA": "YOW",
    "EDMONTON": "YEG",
    "WINNIPEG": "YWG",

    "MEXICO": "MEX",
    "MEXICO CITY": "MEX",
    "CANCUN": "CUN",
    "GUADALAJARA": "GDL",
    "MONTERREY": "MTY",

    "COSTA RICA": "SJO",
    "SAN JOSE": "SJO",

    "PANAMA": "PTY",
    "PANAMA CITY": "PTY",

    "DOMINICAN REPUBLIC": "SDQ",
    "PUNTA CANA": "PUJ",
    "SANTO DOMINGO": "SDQ",

    "JAMAICA": "KIN",
    "KINGSTON": "KIN",
    "MONTEGO BAY": "MBJ",

    "CUBA": "HAV",
    "HAVANA": "HAV",

    "PUERTO RICO": "SJU",
    "SAN JUAN": "SJU",

    "BAHAMAS": "NAS",
    "NASSAU": "NAS",

    "TRINIDAD AND TOBAGO": "POS",
    "PORT OF SPAIN": "POS",

    # -----------------------------------------------------------
    # SOUTH AMERICA — 12 COUNTRIES + CITIES
    # -----------------------------------------------------------
    "BRAZIL": "GRU",
    "SAO PAULO": "GRU",
    "RIO DE JANEIRO": "GIG",
    "BRASILIA": "BSB",
    "SALVADOR": "SSA",

    "ARGENTINA": "EZE",
    "BUENOS AIRES": "EZE",
    "CORDOBA": "COR",

    "CHILE": "SCL",
    "SANTIAGO": "SCL",

    "COLOMBIA": "BOG",
    "BOGOTA": "BOG",
    "MEDELLIN": "MDE",
    "CALI": "CLO",

    "PERU": "LIM",
    "LIMA": "LIM",

    "ECUADOR": "UIO",
    "QUITO": "UIO",
    "GUAYAQUIL": "GYE",

    "PARAGUAY": "ASU",
    "ASUNCION": "ASU",

    "URUGUAY": "MVD",
    "MONTEVIDEO": "MVD",

    "BOLIVIA": "LPB",
    "LA PAZ": "LPB",
    "SANTA CRUZ": "VVI",

    # -----------------------------------------------------------
    # OCEANIA — 14 COUNTRIES + CITIES
    # -----------------------------------------------------------
    "AUSTRALIA": "SYD",
    "SYDNEY": "SYD",
    "MELBOURNE": "MEL",
    "BRISBANE": "BNE",
    "PERTH": "PER",
    "ADELAIDE": "ADL",
    "GOLD COAST": "OOL",

    "NEW ZEALAND": "AKL",
    "AUCKLAND": "AKL",
    "WELLINGTON": "WLG",
    "CHRISTCHURCH": "CHC",

    "FIJI": "NAN",
    "VITI LEVU": "NAN",

    "PAPUA NEW GUINEA": "POM",
    "PORT MORESBY": "POM",
}

    
    # Check if we have a mapping
    if location in location_map:
        return location_map[location]
    
    # If it's already a 3-letter code, return as-is
    if len(location) == 3 and location.isalpha():
        return location
    
    # Otherwise return uppercase (might be a city code like "NYC" for New York area)
    return location

def fetch_booking_details(
    booking_token,
    departure_id=None,
    arrival_id=None,
    outbound_date=None,
    return_date=None,
    trip_type=2,  # default: one-way
):
    """Fetch detailed booking options using booking_token + flight context."""
    params = {
        "engine": "google_flights",
        "booking_token": booking_token,
        "api_key": API_KEY,
        "type": trip_type,
    }
    if departure_id:
        params["departure_id"] = departure_id
    if arrival_id:
        params["arrival_id"] = arrival_id
    if outbound_date:
        params["outbound_date"] = outbound_date
    if return_date:
        params["return_date"] = return_date

    try:
        # Use very short timeout to avoid blocking (3 seconds max)
        resp = requests.get(BASE_URL, params=params, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        
        # Check if response has error
        if "error" in data:
            return {"error": data.get("error", "Unknown error from API")}
        
        return data
    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}  # Don't raise, just return error
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}  # Don't raise, just return error
    except Exception as e:
        return {"error": f"Booking details fetch failed: {e}"}  # Don't raise, just return error


def _extract_booking_links(booking_details):
    """Extract booking links from booking details response.
    
    Returns:
        dict with 'booking_link' (deep link) and 'book_with' (seller name)
        Returns None if no booking options found
    """
    if not booking_details or "error" in booking_details:
        return None
    
    try:
        booking_options = booking_details.get("booking_options", [])
        if not booking_options:
            return None
        
        # Get the first booking option (usually the best/cheapest)
        first_option = booking_options[0]
        
        # Check for 'together' or 'separate' booking options
        booking_info = first_option.get("together") or first_option.get("separate")
        if not booking_info:
            return None
        
        booking_request = booking_info.get("booking_request")
        if not booking_request:
            return None
        
        url = booking_request.get("url")
        post_data = booking_request.get("post_data")
        
        if url and post_data:
            # Create deep link: url + "?" + post_data
            deep_link = f"{url}?{post_data}"
            book_with = booking_info.get("book_with", "Unknown")
            
            return {
                "booking_link": deep_link,
                "book_with": book_with,
                "price": booking_info.get("price")
            }
    except Exception as e:
        print(f"[FLIGHT_TOOLS] Error extracting booking links: {e}")
        return None
    
    return None


def _attach_booking_links_to_flights(flights, search_metadata, departure_id, arrival_id, 
                                     outbound_date, return_date=None, trip_type=2, max_flights=5):
    """Attach booking links to each flight in the list.
    
    Args:
        flights: List of flight objects
        search_metadata: Metadata from search response (contains google_flights_url)
        departure_id: Departure airport code
        arrival_id: Arrival airport code
        outbound_date: Outbound date
        return_date: Return date (for round-trip)
        trip_type: 1 for round-trip, 2 for one-way
        max_flights: Maximum number of flights to process (reduced to 5 for performance)
    
    Returns:
        List of flights with booking links attached
    """
    if not flights:
        return flights
    
    google_flights_url = search_metadata.get("google_flights_url") if search_metadata else None
    
    # Fallback: Construct Google Flights URL if not in metadata
    if not google_flights_url and departure_id and arrival_id and outbound_date:
        # Construct a basic Google Flights search URL
        # Use a simple format: /flights?q=Flights from DEP to ARR on DATE
        from urllib.parse import quote
        query = f"Flights from {departure_id} to {arrival_id} on {outbound_date}"
        google_flights_url = (
            f"https://www.google.com/travel/flights"
            f"?q={quote(query)}"
            f"&hl=en&gl=us&curr=USD"
        )
        print(f"[FLIGHT_TOOLS] ⚠️ Constructed fallback Google Flights URL for {departure_id}→{arrival_id} on {outbound_date}")
    
    # CRITICAL: Attach Google Flights URL to ALL flights FIRST (before any processing)
    # This ensures every flight has at least the Google Flights link
    if google_flights_url:
        for i, flight in enumerate(flights):
            # Always set it, even if flight already has one (ensures consistency)
            flight["google_flights_url"] = google_flights_url
        print(f"[FLIGHT_TOOLS] Attached Google Flights URL to {len(flights)} flights")
    else:
        print(f"[FLIGHT_TOOLS] ⚠️ WARNING: No Google Flights URL available (search_metadata={search_metadata is not None})")
    
    # Process only first max_flights to get booking links (for performance)
    # We prioritize the first flights which are usually the best/cheapest
    # REDUCED to 5 to avoid blocking the system
    flights_to_process = flights[:max_flights]
    
    # Process booking links (with timeout protection via fetch_booking_details)
    for idx, flight in enumerate(flights_to_process):
        booking_token = flight.get("booking_token")
        
        if booking_token:
            try:
                # Fetch booking details with very short timeout to avoid blocking
                booking_details = fetch_booking_details(
                    booking_token,
                    departure_id=departure_id,
                    arrival_id=arrival_id,
                    outbound_date=outbound_date,
                    return_date=return_date,
                    trip_type=trip_type
                )
                
                # Extract booking links
                if booking_details and "error" not in booking_details:
                    booking_info = _extract_booking_links(booking_details)
                    
                    if booking_info:
                        flight["booking_link"] = booking_info["booking_link"]
                        flight["book_with"] = booking_info["book_with"]
                        if booking_info.get("price"):
                            flight["booking_price"] = booking_info["price"]
                    else:
                        # If extraction failed, get airline name from flight data as fallback
                        airline_name = None
                        if flight.get("flights") and len(flight["flights"]) > 0:
                            airline_name = flight["flights"][0].get("airline")
                        
                        if airline_name:
                            flight["book_with"] = airline_name
            except Exception as e:
                # Silent fail - we already have google_flights_url for all flights
                # Don't log to avoid spam
                pass
    
    # Final verification: Ensure ALL flights have google_flights_url (double-check)
    if google_flights_url:
        missing_count = 0
        for flight in flights:
            if not flight.get("google_flights_url"):
                flight["google_flights_url"] = google_flights_url
                missing_count += 1
        if missing_count > 0:
            print(f"[FLIGHT_TOOLS] ⚠️ Added missing Google Flights URL to {missing_count} flights")
    
    return flights


def _parse_price(text):
    if isinstance(text, (int, float)):
        return float(text)
    try:
        return float("".join(c for c in str(text) if c.isdigit() or c == "."))
    except Exception:
        return float("inf")


def _total_duration(flight_obj):
    try:
        return sum(leg["duration"] for leg in flight_obj["flights"])
    except Exception:
        return 10**9


def _dep_minutes(leg_time_str):
    if not leg_time_str:
        return None
    if "T" in leg_time_str:
        t = leg_time_str.split("T")[-1]
    elif " " in leg_time_str:
        t = leg_time_str.split(" ")[-1]
    else:
        t = leg_time_str
    try:
        h, m = t[:5].split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def _to_list(data_or_list):
    """Normalize input to always return a list of flight objects."""
    if isinstance(data_or_list, list):
        return data_or_list

    if not isinstance(data_or_list, dict):
        return []

    out = []
    for k in ("best_flights", "other_flights", "outbound", "return", "flights"):
        if k in data_or_list and isinstance(data_or_list[k], list):
            out.extend(data_or_list[k])

    return out


def normalize_travel_class(user_input):
    """Converts user input (text or number) to SerpAPI numeric travel_class (1–4)."""
    mapping = {
        "economy": 1,
        "eco": 1,
        "premium": 2,
        "premium economy": 2,
        "business": 3,
        "biz": 3,
        "first": 4,
    }
    if isinstance(user_input, int):
        return min(max(user_input, 1), 4)
    try:
        if str(user_input).strip().isdigit():
            return min(max(int(user_input), 1), 4)
    except:
        pass
    return mapping.get(str(user_input).strip().lower(), 1)


def date_range(center_date_str, days_flex=3):
    """Return list of date strings ±days_flex around center_date."""
    base = datetime.strptime(center_date_str, "%Y-%m-%d")
    return [
        (base + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(-days_flex, days_flex + 1)
    ]


# -------------------------
# Fetch from SerpAPI
# -------------------------

def fetch_one_way_flights(departure, arrival, date, currency,
                          adults=1, children=0, infants=0, travel_class=1):
    """Fetch one-way flights from SerpApi Google Flights engine."""
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": date,
        "currency": currency,
        "type": 2,
        "adults": adults,
        "children": children,
        "infants_in_seat": infants,
        "travel_class": normalize_travel_class(travel_class),
        "show_booking_options": True,
        "api_key": API_KEY,
    }

    resp = requests.get(BASE_URL, params=params)
    data = resp.json()

    # Debug logging
    print(f"[FLIGHT TOOLS] API Response status: {resp.status_code}")
    print(f"[FLIGHT TOOLS] API Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    if "error" in data:
        print(f"[FLIGHT TOOLS] API Error: {data.get('error')}")
        return {"outbound": []}
    
    best_flights = data.get("best_flights", [])
    other_flights = data.get("other_flights", [])
    print(f"[FLIGHT TOOLS] best_flights count: {len(best_flights) if isinstance(best_flights, list) else 'N/A'}")
    print(f"[FLIGHT TOOLS] other_flights count: {len(other_flights) if isinstance(other_flights, list) else 'N/A'}")
    
    # Check for flights in various possible response structures
    flights = best_flights or other_flights or []
    
    # If no flights found, check for alternative response structures
    if not flights:
        # Check if there's a different structure (e.g., "flights" key)
        if "flights" in data and isinstance(data["flights"], list):
            flights = data["flights"]
            print(f"[FLIGHT TOOLS] Found flights in 'flights' key: {len(flights)}")
        # Check search_metadata for any hints
        search_metadata = data.get("search_metadata", {})
        if search_metadata:
            print(f"[FLIGHT TOOLS] search_metadata keys: {list(search_metadata.keys())}")
            if "status" in search_metadata:
                print(f"[FLIGHT TOOLS] API status: {search_metadata.get('status')}")
    
    if not flights:
        print(f"[FLIGHT TOOLS] ⚠️ WARNING: No flights found in API response. Full response structure: {list(data.keys())}")
        # Log a sample of the response for debugging (truncated)
        import json
        response_sample = json.dumps(data, indent=2, default=str)[:1000]
        print(f"[FLIGHT TOOLS] Response sample (first 1000 chars): {response_sample}")
    
    # Attach booking links to each flight
    if flights:
        search_metadata = data.get("search_metadata", {})
        flights = _attach_booking_links_to_flights(
            flights,
            search_metadata,
            departure_id=departure,
            arrival_id=arrival,
            outbound_date=date,
            return_date=None,
            trip_type=2,
            max_flights=5  # Process up to 5 flights to get booking links (reduced for performance)
        )
        # Update the data with flights that now have booking links
        if data.get("best_flights"):
            data["best_flights"] = flights
        elif data.get("other_flights"):
            data["other_flights"] = flights
    
    return data


def fetch_round_trip_flights(departure, arrival, dep_date, arr_date, currency,
                             adults=1, children=0, infants=0, travel_class=1):
    """Fetch round-trip flights from SerpApi Google Flights engine."""
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": dep_date,
        "return_date": arr_date,
        "currency": currency,
        "type": 1,
        "adults": adults,
        "children": children,
        "infants_in_seat": infants,
        "travel_class": normalize_travel_class(travel_class),
        "show_booking_options": True,
        "api_key": API_KEY,
    }

    resp = requests.get(BASE_URL, params=params)
    data = resp.json()

    if "error" in data:
        return {"outbound": [], "return": []}, {"outbound": [], "return": []}

    outbound = data.get("best_flights") or data.get("other_flights") or []
    inbound = data.get("return_flights") or []
    
    search_metadata = data.get("search_metadata", {})
    
    # Attach booking links to outbound flights
    if outbound:
        outbound = _attach_booking_links_to_flights(
            outbound,
            search_metadata,
            departure_id=departure,
            arrival_id=arrival,
            outbound_date=dep_date,
            return_date=arr_date,
            trip_type=1,
            max_flights=5
        )
        # Update the data with outbound flights that now have booking links
        if data.get("best_flights"):
            data["best_flights"] = outbound
        elif data.get("other_flights"):
            data["other_flights"] = outbound
    
    # Attach booking links to return flights
    # For return flights, each flight should have its own booking_token
    # We'll fetch booking details using the return flight's booking_token
    if inbound:
        inbound = _attach_booking_links_to_flights(
            inbound,
            search_metadata,
            departure_id=arrival,  # For return, departure is the arrival airport
            arrival_id=departure,  # For return, arrival is the departure airport
            outbound_date=arr_date,  # Return date becomes the outbound for return flight
            return_date=None,
            trip_type=2,  # Treat return leg as one-way for booking link purposes
            max_flights=5
        )
        # Update return flights in data
        if data.get("return_flights"):
            data["return_flights"] = inbound
    
    return data, data


# -------------------------
# Filters
# -------------------------

def filter_by_airline(flights_list, airline_name):
    flights = _to_list(flights_list)
    if not airline_name:
        return flights
    target = airline_name.lower()
    return [
        f for f in flights
        if any(target in str(leg.get("airline", "")).lower()
               for leg in f.get("flights", []))
    ]


def filter_by_price(flights_list, max_price):
    flights = _to_list(flights_list)
    if not max_price:
        return flights
    return [f for f in flights if _parse_price(f.get("price")) <= max_price]


def filter_direct_flights(flights_list, direct_only=True):
    flights = _to_list(flights_list)
    if not direct_only:
        return flights
    return [f for f in flights if len(f.get("flights", [])) == 1]


def filter_by_duration(flights_list, max_duration_minutes):
    flights = _to_list(flights_list)
    if not max_duration_minutes:
        return flights
    return [f for f in flights if _total_duration(f) <= max_duration_minutes]


def filter_by_departure_time(flights_list, after=None, before=None):
    flights = _to_list(flights_list)
    after_min = None if not after else _dep_minutes(after)
    before_min = None if not before else _dep_minutes(before)
    return [
        f for f in flights
        if (dep_m := _dep_minutes(f.get("flights", [{}])[0].get("departure_airport", {}).get("time")))
        and (after_min is None or dep_m >= after_min)
        and (before_min is None or dep_m <= before_min)
    ]


def filter_by_arrival_time(flights_list, after=None, before=None):
    flights = _to_list(flights_list)
    after_min = None if not after else _dep_minutes(after)
    before_min = None if not before else _dep_minutes(before)
    return [
        f for f in flights
        if (arr_m := _dep_minutes(f.get("flights", [{}])[-1].get("arrival_airport", {}).get("time")))
        and (after_min is None or arr_m >= after_min)
        and (before_min is None or arr_m <= before_min)
    ]


def filter_by_stopover(flights_list, airport_code):
    flights = _to_list(flights_list)
    if not airport_code:
        return flights
    code = airport_code.lower()
    return [
        f for f in flights
        if any(code == leg.get("arrival_airport", {}).get("id", "").lower()
               for leg in f.get("flights", [])[:-1])
    ]


# -------------------------
# Sorting
# -------------------------

def sort_flights(flights_list, by="price", ascending=True):
    flights = _to_list(flights_list)
    key_fn = {
        "price": lambda f: _parse_price(f.get("price")),
        "duration": _total_duration,
        "departure": lambda f: _dep_minutes(
            f.get("flights", [{}])[0].get("departure_airport", {}).get("time")
        ),
        "arrival": lambda f: _dep_minutes(
            f.get("flights", [{}])[-1].get("arrival_airport", {}).get("time")
        )
    }.get(by, lambda f: 0)
    return sorted(flights, key=key_fn, reverse=not ascending)


# -------------------------
# Error handling
# -------------------------

def explain_error(response_json):
    if "error" in response_json:
        return f"⚠️ API Error: {response_json['error']}"
    if not _to_list(response_json):
        return "No flights found. Try changing the date or route."
    return None


# -------------------------
# Filter pipeline
# -------------------------

def get_filtered_flights(
    data_or_list,
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True
):
    flights = _to_list(data_or_list)
    if airline:
        flights = filter_by_airline(flights, airline)
    if max_price:
        flights = filter_by_price(flights, max_price)
    if direct_only:
        flights = filter_direct_flights(flights, True)
    if max_duration:
        flights = filter_by_duration(flights, max_duration)
    if dep_after or dep_before:
        flights = filter_by_departure_time(flights, dep_after, dep_before)
    if arr_after or arr_before:
        flights = filter_by_arrival_time(flights, arr_after, arr_before)
    if stopover:
        flights = filter_by_stopover(flights, stopover)
    if sort_by:
        flights = sort_flights(flights, by=sort_by, ascending=ascending)
    return flights


# -------------------------
# Unified agent API
# -------------------------

def agent_get_flights(
    trip_type, dep, arr, dep_date, arr_date=None, currency="USD",
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True,
    adults=1, children=0, infants=0, travel_class=1
):
    global CURRENT_CURRENCY
    CURRENT_CURRENCY = currency
    result = {"outbound": [], "return": []}

    if trip_type == "one-way":
        raw = fetch_one_way_flights(dep, arr, dep_date, currency,
                                    adults, children, infants, travel_class)
        err = explain_error(raw)
        if err:
            return result
        result["outbound"] = get_filtered_flights(
            raw, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["_passengers"] = {"adults": adults, "children": children, "infants": infants}
        return result

    if trip_type == "round-trip":
        raw_out, raw_back = fetch_round_trip_flights(
            dep, arr, dep_date, arr_date, currency,
            adults, children, infants, travel_class
        )
        err = explain_error(raw_out)
        if err:
            return result
        result["outbound"] = get_filtered_flights(
            raw_out, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["return"] = get_filtered_flights(
            raw_back, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["_passengers"] = {"adults": adults, "children": children, "infants": infants}
        return result

    raise ValueError("trip_type must be 'one-way' or 'round-trip'")


def agent_get_flights_flexible(
    trip_type, dep, arr, dep_date, arr_date=None, currency="USD",
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True,
    adults=1, children=0, infants=0, travel_class=1,
    days_flex=3
):
    """Perform the same flight search for ±days_flex around dep_date."""
    all_flights = []

    for d in date_range(dep_date, days_flex):
        result = agent_get_flights(
            trip_type, dep, arr, d, arr_date, currency,
            airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending,
            adults, children, infants, travel_class
        )

        if result["outbound"]:
            for f in result["outbound"]:
                f_copy = deepcopy(f)
                f_copy["search_date"] = d
                all_flights.append(f_copy)

    if sort_by:
        all_flights = sort_flights(all_flights, by=sort_by, ascending=ascending)
    else:
        all_flights = sort_flights(all_flights, by="price", ascending=True)

    # Attach passenger info for automatic summary
    result_info = {
        "_passengers": {
            "adults": adults,
            "children": children,
            "infants": infants,
        }
    }

    return {"flights": all_flights, **result_info}


def _validate_flight_inputs(
    trip_type: str,
    departure: str,
    arrival: str,
    departure_date: str,
    arrival_date: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Validate flight search inputs and return (is_valid, error_message).
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not trip_type or not isinstance(trip_type, str):
        return False, "Trip type is required and must be a string ('one-way' or 'round-trip')."
    
    trip_type_lower = trip_type.lower().strip()
    if trip_type_lower not in ["one-way", "round-trip", "oneway", "roundtrip"]:
        return False, f"Invalid trip type: '{trip_type}'. Must be 'one-way' or 'round-trip'."
    
    if not departure or not isinstance(departure, str) or not departure.strip():
        return False, "Departure airport/city code is required and must be a non-empty string (e.g., 'JFK', 'NYC', 'LAX')."
    
    if not arrival or not isinstance(arrival, str) or not arrival.strip():
        return False, "Arrival airport/city code is required and must be a non-empty string (e.g., 'LAX', 'LHR', 'CDG')."
    
    if not departure_date or not isinstance(departure_date, str) or not departure_date.strip():
        return False, "Departure date is required and must be a non-empty string in YYYY-MM-DD format (e.g., '2025-12-10')."
    
    # Basic date format check
    import re
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, departure_date):
        return False, f"Invalid departure date format: '{departure_date}'. Expected format: YYYY-MM-DD (e.g., 2025-12-10)."
    
    # For round-trip, arrival_date is required
    if trip_type_lower in ["round-trip", "roundtrip"]:
        if not arrival_date or not isinstance(arrival_date, str) or not arrival_date.strip():
            return False, "Arrival date is required for round-trip flights and must be in YYYY-MM-DD format (e.g., '2025-12-17')."
        if not re.match(date_pattern, arrival_date):
            return False, f"Invalid arrival date format: '{arrival_date}'. Expected format: YYYY-MM-DD (e.g., 2025-12-17)."
    
    return True, None


def register_flight_tools(mcp):
    """Register all flight-related tools with the MCP server."""
    
    @mcp.tool(description=get_doc("agent_get_flights", "flight"))
    def agent_get_flights_tool(
        trip_type: str,
        departure: str,
        arrival: str,
        departure_date: str,
        arrival_date: Optional[str] = None,
        currency: str = "USD",
        airline: Optional[str] = None,
        max_price: Optional[float] = None,
        direct_only: bool = False,
        max_duration: Optional[int] = None,
        dep_after: Optional[str] = None,
        dep_before: Optional[str] = None,
        arr_after: Optional[str] = None,
        arr_before: Optional[str] = None,
        stopover: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: str = "economy"
    ) -> Dict:
        """Search for flights using SerpAPI Google Flights.
        
        This tool searches for one-way or round-trip flights with extensive
        filtering and sorting options. Supports filtering by airline, price,
        duration, departure/arrival times, direct flights, and more.
        
        Args:
            trip_type: "one-way" or "round-trip" (required)
            departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX") (required)
            arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG") (required)
            departure_date: Departure date in YYYY-MM-DD format (required)
            arrival_date: Return date for round-trip in YYYY-MM-DD format (required for round-trip)
            currency: Currency code (default: "USD")
            airline: Filter by airline name (optional)
            max_price: Maximum price filter (optional)
            direct_only: Only show direct flights (default: False)
            max_duration: Maximum flight duration in minutes (optional)
            dep_after: Departure time after (HH:MM format, optional)
            dep_before: Departure time before (HH:MM format, optional)
            arr_after: Arrival time after (HH:MM format, optional)
            arr_before: Arrival time before (HH:MM format, optional)
            stopover: Filter by stopover airport code (optional)
            sort_by: Sort by "price", "duration", "departure", or "arrival" (optional)
            ascending: Sort ascending (default: True)
            adults: Number of adults (default: 1)
            children: Number of children (default: 0)
            infants: Number of infants (default: 0)
            travel_class: "economy", "premium", "business", or "first" (default: "economy")
        
        Returns:
            Dictionary with flight search results
        """
        # Normalize trip_type
        trip_type_normalized = trip_type.lower().strip()
        if trip_type_normalized == "oneway":
            trip_type_normalized = "one-way"
        elif trip_type_normalized == "roundtrip":
            trip_type_normalized = "round-trip"
        
        # Convert string numeric parameters to proper types
        if max_price is not None:
            try:
                max_price = float(max_price) if not isinstance(max_price, (int, float)) else max_price
            except (ValueError, TypeError):
                max_price = None
        
        if max_duration is not None:
            try:
                max_duration = int(max_duration) if not isinstance(max_duration, int) else max_duration
            except (ValueError, TypeError):
                max_duration = None
        
        # Validate inputs first
        is_valid, validation_error = _validate_flight_inputs(
            trip_type_normalized, departure, arrival, departure_date, arrival_date
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "outbound": [],
                "return": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        
        # Convert numeric parameters (might come as strings from JSON)
        try:
            adults = int(adults)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid adults value: {adults}. Must be an integer.",
                "outbound": [],
                "return": []
            }
        
        try:
            children = int(children)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid children value: {children}. Must be an integer.",
                "outbound": [],
                "return": []
            }
        
        try:
            infants = int(infants)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid infants value: {infants}. Must be an integer.",
                "outbound": [],
                "return": []
            }
        
        # Validate numeric inputs
        if adults < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of adults: {adults}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of adults (0 or more)."
            }
        
        if children < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of children: {children}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of children (0 or more)."
            }
        
        if infants < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of infants: {infants}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of infants (0 or more)."
            }
        
        if max_price is not None and max_price <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price: {max_price}. Must be a positive number.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a positive number for max_price."
            }
        
        try:
            # Normalize locations (convert country/city names to airport codes)
            normalized_departure = _normalize_location(departure)
            normalized_arrival = _normalize_location(arrival)
            
            # Call the flight search function
            result = agent_get_flights(
                trip_type=trip_type_normalized,
                dep=normalized_departure,
                arr=normalized_arrival,
                dep_date=departure_date.strip(),
                arr_date=arrival_date.strip() if arrival_date else None,
                currency=currency.upper() if currency else "USD",
                airline=airline.strip() if airline else None,
                max_price=max_price,
                direct_only=direct_only,
                max_duration=max_duration,
                dep_after=dep_after.strip() if dep_after else None,
                dep_before=dep_before.strip() if dep_before else None,
                arr_after=arr_after.strip() if arr_after else None,
                arr_before=arr_before.strip() if arr_before else None,
                stopover=stopover.strip().upper() if stopover else None,
                sort_by=sort_by.lower() if sort_by else None,
                ascending=ascending,
                adults=adults,
                children=children,
                infants=infants,
                travel_class=travel_class
            )
            
            return {
                "error": False,
                "outbound": result.get("outbound", []),
                "return": result.get("return", []),
                "passengers": result.get("_passengers", {"adults": adults, "children": children, "infants": infants}),
                "trip_type": trip_type_normalized,
                "departure": normalized_departure,
                "arrival": normalized_arrival,
                "departure_date": departure_date.strip(),
                "arrival_date": arrival_date.strip() if arrival_date else None,
                "currency": currency.upper() if currency else "USD",
                "travel_class": travel_class.lower() if travel_class else "economy"
            }
            
        except ValueError as e:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid parameter: {str(e)}",
                "outbound": [],
                "return": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            # Provide helpful error messages
            if "timeout" in error_message.lower() or "Timeout" in error_type:
                return {
                    "error": True,
                    "error_code": "TIMEOUT",
                    "error_message": "The flight search took too long to complete. The flight service may be slow or unavailable.",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please try again in a few moments. If the problem persists, the flight service may be temporarily unavailable."
                }
            elif "api" in error_message.lower() or "serpapi" in error_message.lower():
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": f"Flight API error: {error_message}",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please verify your API credentials and try again. If the problem persists, contact support."
                }
            else:
                return {
                    "error": True,
                    "error_code": "UNEXPECTED_ERROR",
                    "error_message": f"An unexpected error occurred while searching for flights: {error_message}",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please try again. If the problem persists, contact support."
                }
    
    @mcp.tool(description=get_doc("agent_get_flights_flexible", "flight"))
    def agent_get_flights_flexible_tool(
        trip_type: str,
        departure: str,
        arrival: str,
        departure_date: str,
        arrival_date: Optional[str] = None,
        currency: str = "USD",
        airline: Optional[str] = None,
        max_price: Optional[float] = None,
        direct_only: bool = False,
        max_duration: Optional[int] = None,
        dep_after: Optional[str] = None,
        dep_before: Optional[str] = None,
        arr_after: Optional[str] = None,
        arr_before: Optional[str] = None,
        stopover: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: str = "economy",
        days_flex: int = 3
    ) -> Dict:
        """Search for flights with flexible dates (±days_flex around departure_date).
        
        This tool performs the same flight search for multiple dates around the
        specified departure date, allowing users to find the best prices across
        a date range. Useful for finding cheaper flights when travel dates are flexible.
        
        Args:
            trip_type: "one-way" or "round-trip" (required)
            departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX") (required)
            arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG") (required)
            departure_date: Center departure date in YYYY-MM-DD format (required)
            arrival_date: Return date for round-trip in YYYY-MM-DD format (required for round-trip)
            currency: Currency code (default: "USD")
            airline: Filter by airline name (optional)
            max_price: Maximum price filter (optional)
            direct_only: Only show direct flights (default: False)
            max_duration: Maximum flight duration in minutes (optional)
            dep_after: Departure time after (HH:MM format, optional)
            dep_before: Departure time before (HH:MM format, optional)
            arr_after: Arrival time after (HH:MM format, optional)
            arr_before: Arrival time before (HH:MM format, optional)
            stopover: Filter by stopover airport code (optional)
            sort_by: Sort by "price", "duration", "departure", or "arrival" (optional)
            ascending: Sort ascending (default: True)
            adults: Number of adults (default: 1)
            children: Number of children (default: 0)
            infants: Number of infants (default: 0)
            travel_class: "economy", "premium", "business", or "first" (default: "economy")
            days_flex: Number of days flexibility (±days_flex around departure_date, default: 3, max: 7)
        
        Returns:
            Dictionary with flight search results across multiple dates
        """
        # Normalize trip_type
        trip_type_normalized = trip_type.lower().strip()
        if trip_type_normalized == "oneway":
            trip_type_normalized = "one-way"
        elif trip_type_normalized == "roundtrip":
            trip_type_normalized = "round-trip"
        
        # Convert string numeric parameters to proper types
        if max_price is not None:
            try:
                max_price = float(max_price) if not isinstance(max_price, (int, float)) else max_price
            except (ValueError, TypeError):
                max_price = None
        
        if max_duration is not None:
            try:
                max_duration = int(max_duration) if not isinstance(max_duration, int) else max_duration
            except (ValueError, TypeError):
                max_duration = None
        
        if days_flex is not None:
            try:
                days_flex = int(days_flex) if not isinstance(days_flex, int) else days_flex
            except (ValueError, TypeError):
                days_flex = 3
        
        # Validate inputs first
        is_valid, validation_error = _validate_flight_inputs(
            trip_type_normalized, departure, arrival, departure_date, arrival_date
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "flights": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        
        # Validate days_flex
        if days_flex < 0 or days_flex > 7:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid days_flex: {days_flex}. Must be between 0 and 7.",
                "flights": [],
                "suggestion": "Please provide days_flex between 0 and 7."
            }
        
        # Convert passenger counts (might come as strings from JSON)
        try:
            adults = int(adults)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid adults value: {adults}. Must be an integer.",
                "flights": []
            }
        
        try:
            children = int(children)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid children value: {children}. Must be an integer.",
                "flights": []
            }
        
        try:
            infants = int(infants)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid infants value: {infants}. Must be an integer.",
                "flights": []
            }
        
        # Validate numeric inputs (same as agent_get_flights_tool)
        if adults < 0 or children < 0 or infants < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Number of passengers (adults, children, infants) must be 0 or greater.",
                "flights": [],
                "suggestion": "Please provide valid passenger counts."
            }
        
        if max_price is not None and max_price <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price: {max_price}. Must be a positive number.",
                "flights": [],
                "suggestion": "Please provide a positive number for max_price."
            }
        
        try:
            # Normalize locations (convert country/city names to airport codes)
            normalized_departure = _normalize_location(departure)
            normalized_arrival = _normalize_location(arrival)
            
            # Call the flexible flight search function
            result = agent_get_flights_flexible(
                trip_type=trip_type_normalized,
                dep=normalized_departure,
                arr=normalized_arrival,
                dep_date=departure_date.strip(),
                arr_date=arrival_date.strip() if arrival_date else None,
                currency=currency.upper() if currency else "USD",
                airline=airline.strip() if airline else None,
                max_price=max_price,
                direct_only=direct_only,
                max_duration=max_duration,
                dep_after=dep_after.strip() if dep_after else None,
                dep_before=dep_before.strip() if dep_before else None,
                arr_after=arr_after.strip() if arr_after else None,
                arr_before=arr_before.strip() if arr_before else None,
                stopover=stopover.strip().upper() if stopover else None,
                sort_by=sort_by.lower() if sort_by else None,
                ascending=ascending,
                adults=adults,
                children=children,
                infants=infants,
                travel_class=travel_class,
                days_flex=days_flex
            )
            
            return {
                "error": False,
                "flights": result.get("flights", []),
                "passengers": result.get("_passengers", {"adults": adults, "children": children, "infants": infants}),
                "trip_type": trip_type_normalized,
                "departure": normalized_departure,
                "arrival": normalized_arrival,
                "departure_date": departure_date.strip(),
                "arrival_date": arrival_date.strip() if arrival_date else None,
                "days_flex": days_flex,
                "currency": currency.upper() if currency else "USD",
                "travel_class": travel_class.lower() if travel_class else "economy"
            }
            
        except ValueError as e:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid parameter: {str(e)}",
                "flights": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            # Provide helpful error messages
            if "timeout" in error_message.lower() or "Timeout" in error_type:
                return {
                    "error": True,
                    "error_code": "TIMEOUT",
                    "error_message": "The flexible flight search took too long to complete. The flight service may be slow or unavailable.",
                    "flights": [],
                    "suggestion": "Please try again in a few moments. If the problem persists, the flight service may be temporarily unavailable."
                }
            elif "api" in error_message.lower() or "serpapi" in error_message.lower():
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": f"Flight API error: {error_message}",
                    "flights": [],
                    "suggestion": "Please verify your API credentials and try again. If the problem persists, contact support."
                }
            else:
                return {
                    "error": True,
                    "error_code": "UNEXPECTED_ERROR",
                    "error_message": f"An unexpected error occurred while searching for flights: {error_message}",
                    "flights": [],
                    "suggestion": "Please try again. If the problem persists, contact support."
                }

