from typing import Dict, Any
import datetime
import logging
from colorama import Fore, Style  # NEW: Import colorama for colored logging
from core.db import db  # your MongoDB client
from agents.product_request import handle_product_request
from agents.request_details import handle_request_details
from agents.address_purpose import handle_address_purpose
from core.utils import translator, is_supported_language  # Import translation utilities

# Set up logging
logger = logging.getLogger(__name__)

# ---------- Field Definitions ---------- #

FIELD_METADATA = {
    "unit": {
        "type": "select",
        "options": ["KG", "GAL", "LB", "L"],
        "required_for": ["Order", "Sample", "Quote", "ppr"],  # CHANGED HERE
        "agent": 2,
        "description": "Unit of measurement for the product - select from KG, GAL, LB, or L"
    },
    "quantity": {
        "type": "number", 
        "validation": "positive_number",
        "required_for": ["Order", "Sample", "Quote", "ppr"],  # CHANGED HERE
        "agent": 2,
        "description": "Quantity required (must be positive number), greater than or equal to minQuantity and less than available stock" 
    },
    "price_per_unit": {
        "type": "number",
        "validation": "positive_number", 
        "required_for": ["Order", "Sample", "Quote", "ppr"],  # CHANGED HERE
        "agent": 2,
        "description": "Price per unit (must be positive number)"
    },
    "expected_price": {
        "type": "calculated",
        "calculation": "quantity * price_per_unit",
        "required_for": ["Order", "Sample", "Quote", "ppr"],  # CHANGED HERE
        "agent": 2,
        "description": "Automatically calculated total price"
    },
    "address": {
        "type": "select",
        "options": "fetch_from_user_account via API",
        "required_for": ["Order", "Sample", "Quote", "ppr"],  # CHANGED HERE
        "agent": 3,
        "description": "Delivery address (choose from saved addresses)"
    },
    "phone": {
        "type": "phone",
        "validation": "phone_number",
        "required_for": ["Order", "Sample", "Quote"],  # CHANGED HERE
        "agent": 2,
        "description": "Contact phone number"
    },
    "incoterm": {
        "type": "select",
        "options": ["Ex Factory", "Deliver to Buyer Factory"],
        "required_for": ["Order", "Sample", "Quote"],  # CHANGED HERE
        "agent": 2,
        "description": "International commercial terms"
    },
    "mode_of_payment": {
        "type": "select", 
        "options": ["LC", "TT", "Cash"],
        "required_for": ["Order", "Sample", "Quote"],  # CHANGED HERE
        "agent": 2,
        "description": "Payment method"
    },
    "packaging_pref": {
        "type": "select",
        "options": ["Bulk Tanker", "PP Bag", "Jerry Can", "Drum"],
        "required_for": ["Order", "Sample", "Quote"],  # CHANGED HERE
        "agent": 2,
        "description": "Packaging preference"
    },
    "delivery_date": {
        "type": "date",
        "validation": "future_date",
        "required_for": ["Order", "Sample","Quote", "ppr"],  # CHANGED HERE
        "agent": 2,
        "description": "Delivery date (must be after today)"
    },
    "market": {
        "type": "select",
        "options": "fetch_from_site via API",
        "required_for": ["Order"],  # CHANGED HERE
        "agent": 3,
        "description": "Target market"
    }
}

# Allowed units for validation in the 2nd agent
ALLOWED_UNITS = ["KG", "GAL", "LB", "L"]

# ---------- Helper Functions ---------- #

async def save_to_mongo_stub(session_id: str, message: str, response: str):
    """
    Placeholder for saving conversation logs to MongoDB.
    Currently does nothing. Can implement detailed logging here later.
    """
    pass

async def create_new_session(session_id: str, user_auth: str) -> Dict[str, Any]:
    """
    Create a new session document in MongoDB.
    """
    data = {
        "agent": "product_request",
        "product_id": "",
        "product_name": "",
        "product_details": {},
        "request": "",
        "session_id": session_id,
        "userAuth": user_auth,
        "history": [],
        "field_metadata": FIELD_METADATA,  # Store field definitions
        "last_updated": datetime.datetime.utcnow()
    }
    await db.agent_sessions.update_one(
        {"_id": session_id},
        {"$set": data},
        upsert=True
    )
    return data

async def load_session(session_id: str) -> Dict[str, Any]:
    """
    Load session document from MongoDB.
    """
    # Clean old sessions (>1 day)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    await db.agent_sessions.delete_many({"last_updated": {"$lt": cutoff}})

    session = await db.agent_sessions.find_one({"_id": session_id})
    return session

async def save_session(session_id: str, data: Dict[str, Any]):
    """
    Save session document to MongoDB.
    """
    data["last_updated"] = datetime.datetime.utcnow()
    await db.agent_sessions.update_one(
        {"_id": session_id},
        {"$set": data},
        upsert=True
    )

# ---------- Dynamic Field Management ---------- #

# In agent_manager.py - replace the expand_session_for_request function

def expand_session_for_request(data: Dict[str, Any]):
    """
    Add new fields dynamically based on request type with validation rules.
    Uses the same logic as the second agent's get_required_fields function.
    """
    request_type = data.get("request", "").lower()
    
    # Use the same field requirements as the second agent
    field_requirements = {
        "order":  ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],
        "sample": ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],
        "quote":  ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],  
        "ppr":    ["unit", "quantity", "price_per_unit", "expected_price", "delivery_date"]  # PPR has different requirements
    }
    
    # Get the required fields for this request type
    required_fields = field_requirements.get(request_type, ["unit", "quantity", "price_per_unit", "expected_price"])
    
    # Initialize only the required fields
    for field_name in required_fields:
        if field_name not in data["product_details"]:
            data["product_details"][field_name] = ""
        
        # Store validation info with the field
        if "validation_info" not in data["product_details"]:
            data["product_details"]["validation_info"] = {}
        
        # Get field metadata
        field_meta = FIELD_METADATA.get(field_name, {})
        data["product_details"]["validation_info"][field_name] = {
            "type": field_meta.get("type", "text"),
            "options": field_meta.get("options", []),
            "validation": field_meta.get("validation", ""),
            "description": field_meta.get("description", field_name),
            "required": True
        }
    

    return data

def expand_session_for_address_purpose(data: Dict[str, Any]):
    """
    Add address and industry fields for final agent.
    """
    data["address"] = ""
    data["industry"] = ""
    return data

def validate_unit_field(unit_value: str) -> bool:
    """
    Validate that the unit is one of the 4 allowed values.
    This will be used by the 2nd agent when saving user input.
    """
    if not unit_value:
        return False
    return unit_value.upper() in ALLOWED_UNITS

def get_allowed_units() -> list:
    """
    Return the list of allowed units for the 2nd agent to use.
    """
    return ALLOWED_UNITS.copy()

# ---------- Agent Manager Core ---------- #

async def route_message(user_input: str, session_id: str, user_auth: str, language: str = "en") -> str:
    """
    MAIN FUNCTION - UPDATED WITH ENHANCED TRANSLATION LOGGING
    Routes user input to the correct agent with translation support.
    """
    # Import enhanced logging functions
    from core.utils import log_chat_session_start, log_chat_session_end
    
    # Validate language
    if not is_supported_language(language):
        logger.warning(f"{Fore.RED}⚠️ Unsupported language: {language}, defaulting to English")
        language = "en"
    
    # Log session start
    log_chat_session_start(session_id, language, user_input)
    
    # Step 1: Translate input to English if needed
    if language != "en":
        english_input = await translator.translate_to_english(user_input, language, session_id)
    else:
        english_input = user_input
        logger.info(f"{Fore.GREEN}🎯 PROCESSING ENGLISH INPUT: {Fore.WHITE}\"{english_input}\"")
    
    # Load session data
    session_data = await load_session(session_id)

    # If session doesn't exist, start a new one
    if not session_data:
        session_data = await create_new_session(session_id, user_auth)
        current_agent = "product_request"
        logger.info(f"{Fore.YELLOW}🆕 NEW SESSION CREATED | Agent: {current_agent}")
    else:
        current_agent = session_data.get("agent", "product_request")
        logger.info(f"{Fore.YELLOW}🔄 CONTINUING SESSION | Current Agent: {current_agent}")

    english_response = ""

    # ---------- Agent Routing (ALL AGENTS WORK WITH ENGLISH) ----------
    try:
        logger.info(f"{Fore.BLUE}🤖 AGENT PROCESSING STARTED...")
        
        if current_agent == "product_request":
            english_response, session_data = await handle_product_request(english_input, session_data)
            if session_data.get("agent") == "request_details":
                session_data = expand_session_for_request(session_data)
                logger.info(f"{Fore.CYAN}🔄 AGENT TRANSITION: product_request → request_details")

        elif current_agent == "request_details":
            english_response, session_data = await handle_request_details(english_input, session_data)
            if session_data.get("agent") == "address_purpose":
                session_data = expand_session_for_address_purpose(session_data)
                logger.info(f"{Fore.CYAN}🔄 AGENT TRANSITION: request_details → address_purpose")

        elif current_agent == "address_purpose":
            english_response, session_data = await handle_address_purpose(english_input, session_data)

        else:
            english_response = "⚠️ Unknown agent state. Restarting session..."
            session_data = await create_new_session(session_id, user_auth)
            
        logger.info(f"{Fore.GREEN}🤖 AGENT RESPONSE (EN): {Fore.WHITE}\"{english_response}\"")

    except Exception as e:
        logger.error(f"{Fore.RED}❌ AGENT PROCESSING ERROR: {e}")
        english_response = "Sorry, I encountered an error. Please try again."

    # Step 2: Translate response back to user's language if needed
    if language != "en":
        final_response = await translator.translate_from_english(english_response, language, session_id)
    else:
        final_response = english_response
        logger.info(f"{Fore.GREEN}📤 FINAL ENGLISH RESPONSE: {Fore.WHITE}\"{final_response}\"")

    # Save session to MongoDB
    await save_session(session_id, session_data)
    await save_to_mongo_stub(session_id, user_input, final_response)

    # Log session completion
    log_chat_session_end(session_id, language, final_response)

    return final_response


# ---------- Backward Compatibility ---------- #
# Keep the original function for existing calls without language parameter
async def route_message_legacy(user_input: str, session_id: str, user_auth: str) -> str:
    """
    Legacy function for backward compatibility
    Uses English as default language
    """
    return await route_message(user_input, session_id, user_auth, "en")