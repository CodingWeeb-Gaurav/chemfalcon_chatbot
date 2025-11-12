from fastapi import APIRouter, Request
from pydantic import BaseModel
from services.agent_manager import route_message
from core.db import db
from core.utils import is_supported_language
import uuid
import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Language mapping function
def normalize_language(language_input: str) -> str:
    """
    Convert frontend language names to backend language codes.
    Frontend sends: "Arabic", "Bangla", "English" 
    Backend expects: "ar", "bn", "en"
    """
    language_map = {
        "arabic": "ar",
        "bangla": "bn", 
        "bengali": "bn",  # alias for bangla
        "english": "en",
        "en": "en",  # In case frontend is modified to send ar, bn, en
        "ar": "ar",  # 
        "bn": "bn"   # 
    }
    
    if not language_input:
        return "en"
    
    normalized_input = language_input.strip().lower()
    return language_map.get(normalized_input, "en").lower()

class ChatMessage(BaseModel):
    sessionId: str # sessionID is mandatory for it to work
    userAuth: str
    message: str
    language: Optional[str] = "English"  # Frontend sends names by default

@router.post("/")
async def chat_endpoint(chat: ChatMessage):
    session_id = chat.sessionId or str(uuid.uuid4()) #create sessionid if not exist (useless now)
    user_message = chat.message
    user_auth = chat.userAuth
    language_input = chat.language or "English"

    # Check if user is authenticated
    if not user_auth or user_auth.strip() == "":
        logger.warning(f"❌ UNAUTHENTICATED ACCESS ATTEMPT - Session: {session_id}")
        
        # Normalize language for error message
        language_code = normalize_language(language_input)
        
        # Return appropriate error message based on language
        if language_code == "ar":
            error_message = "يرجى تسجيل الدخول أو الاشتراك لتفعيل الدردشة."
        elif language_code == "bn":
            error_message = "চ্যাটবট সক্রিয় করতে সাইন ইন বা সাইন আপ করুন।"
        else:
            error_message = "Please sign in or sign up to activate the chatbot."
        
        return {"reply": error_message, "sessionId": session_id}
        
    # Normalize language from frontend format to backend format
    language_code = normalize_language(language_input)
    
    # Validate and normalize language
    if not is_supported_language(language_code):
        logger.warning(f"Unsupported language received: {language_input} (normalized: {language_code}), defaulting to 'en'")
        language_code = "en"
    
    # Log both original and normalized language (FIXED: removed .upper())
    logger.info(f"🌐 CHAT REQUEST - Language: {language_input} -> {language_code}, Session: {session_id}")
    
    # Save incoming message to Mongo (with normalized language code)
    await db.chat_sessions.update_one(
        {"_id": session_id},
        {"$push": {"messages": {"role": "user", "message": user_message, "time": datetime.datetime.utcnow()}},
         "$set": {"language": language_code}  # Store normalized code
        },
        upsert=True
    )

    # Run agent manager pipeline WITH LANGUAGE SUPPORT
    try:
        ai_reply = await route_message(
            user_input=user_message, 
            session_id=session_id, 
            user_auth=user_auth,
            language=language_code  # Pass normalized code
        )
        
        if not ai_reply:
            ai_reply = "Sorry, something went wrong in the Agent or Manager. Please try again."
            
    except Exception as e:
        logger.error(f"❌ Error in route_message: {e}")
        
        # Language-specific error messages using normalized code
        if language_code == "ar":
            ai_reply = "عذرًا، حدث خطأ. يرجى المحاولة مرة أخرى."
        elif language_code == "bn":
            ai_reply = "দুঃখিত, একটি ত্রুটি ঘটেছে। অনুগ্রহ করে আবার চেষ্টা করুন।"
        else:
            ai_reply = "Sorry, something went wrong. Please try again."

    # Save AI reply to Mongo
    await db.chat_sessions.update_one(
        {"_id": session_id},
        {"$push": {"messages": {"role": "ai", "message": ai_reply, "time": datetime.datetime.utcnow()}}},
        upsert=True
    )

    # FIXED: removed .upper() from language code
    logger.info(f"✅ CHAT RESPONSE - Language: {language_code}, Session: {session_id}")
    
    return {"reply": ai_reply, "sessionId": session_id}


# Health check endpoint to verify translation service
@router.get("/translation-status")
async def translation_status():
    """Check if translation services are working"""
    from core.utils import translator
    
    # Test the language mapping
    test_mappings = {
        "Arabic": "ar",
        "Bangla": "bn", 
        "English": "en",
        "arabic": "ar",
        "bangla": "bn",
        "english": "en"
    }
    
    status = {
        "translation_service": "active",
        "supported_languages": ["en", "ar", "bn"],
        "language_mapping": test_mappings,
        "test_results": {}
    }
    
    # Test translation for each language code
    for lang_code in ["en", "ar", "bn"]:
        try:
            test_phrase = "Hello, how are you?"
            if lang_code != "en":
                # Test translation to English
                translated = await translator.translate_to_english("مرحبا" if lang_code == "ar" else "হ্যালো", lang_code)
                status["test_results"][lang_code] = {
                    "original": "مرحبا" if lang_code == "ar" else "হ্যালো",
                    "translated": translated,
                    "status": "working"
                }
            else:
                status["test_results"][lang_code] = {
                    "original": test_phrase,
                    "translated": test_phrase,
                    "status": "working"
                }
        except Exception as e:
            status["test_results"][lang_code] = {
                "original": "test phrase",
                "translated": None,
                "status": f"error: {str(e)}"
            }
    
    return status