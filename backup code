# core/utils.py also manages translation with enhanced logging

import logging
import re
import json
from deep_translator import GoogleTranslator
from typing import Optional, Dict, Any
import colorama
from colorama import Fore, Back, Style
import datetime

# Initialize colorama for colored logging
colorama.init(autoreset=True)

# Set up enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class TranslationManager:
    """
    Handles translation between English, Arabic, and Bengali
    Uses deep-translator (free Google Translate API)
    """
    
    def __init__(self):
        self.supported_languages = {
            'en': {'name': 'english', 'color': Fore.GREEN},
            'ar': {'name': 'arabic', 'color': Fore.CYAN}, 
            'bn': {'name': 'bengali', 'color': Fore.YELLOW}
        }
        self._current_source_lang = None
        self._current_target_lang = None
    
    def _get_language_display(self, lang_code: str) -> str:
        """Get colored language display"""
        lang_info = self.supported_languages.get(lang_code, {'name': lang_code, 'color': Fore.WHITE})
        return f"{lang_info['color']}{lang_code.upper()}{Style.RESET_ALL}"
    
    def _extract_and_preserve_language_fields(self, text: str, target_lang: str) -> tuple[str, Dict[str, str]]:
        """
        Extract language-specific fields from text and preserve them
        Returns: (cleaned_text, preserved_fields)
        """
        # Pattern to match fields like name_bn, description_bn, specification_bn, etc.
        field_patterns = {
            'name': r'name_(en|ar|bn)\s*:\s*"([^"]*)"',
            'description': r'description_(en|ar|bn)\s*:\s*"([^"]*)"', 
            'specification': r'specification_(en|ar|bn)\s*:\s*"([^"]*)"',
            'brand': r'brand_(en|ar|bn)\s*:\s*"([^"]*)"'
        }
        
        preserved_fields = {}
        cleaned_text = text
        
        for field_type, pattern in field_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for lang_suffix, field_value in matches:
                field_key = f"{field_type}_{lang_suffix}"
                # Only preserve fields that match our target language
                if lang_suffix == target_lang:
                    preserved_fields[field_key] = field_value
                    # Remove the preserved field from text to avoid translation
                    cleaned_text = re.sub(f'{field_key}\\s*:\\s*"[^"]*"', f'{field_key}: "[PRESERVED]"', cleaned_text)
        
        return cleaned_text, preserved_fields
    
    def _restore_preserved_fields(self, translated_text: str, preserved_fields: Dict[str, str]) -> str:
        """Restore preserved language-specific fields back into translated text"""
        result_text = translated_text
        
        for field_key, field_value in preserved_fields.items():
            # Replace the placeholder with the actual preserved value
            placeholder = f'{field_key}: "[PRESERVED]"'
            if placeholder in result_text:
                result_text = result_text.replace(placeholder, f'{field_key}: "{field_value}"')
            else:
                # If placeholder not found, try to insert it at the end or appropriate location
                result_text += f'\n{field_key}: "{field_value}"'
        
        return result_text
    
    def _log_translation_flow(self, original: str, translated: str, direction: str, session_id: str = ""):
        """Enhanced logging for translation flow"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if direction == "to_english":
            # FIXED: Use actual source language instead of parsing from text
            source_lang = self._current_source_lang if self._current_source_lang else 'unknown'
            target_lang = 'en'
            arrow = "🔄"
            color = Fore.BLUE
        else:
            source_lang = 'en'
            # FIXED: Use actual target language instead of parsing from text
            target_lang = self._current_target_lang if self._current_target_lang else 'unknown'
            arrow = "🔄"
            color = Fore.MAGENTA
        
        session_info = f" | Session: {session_id}" if session_id else ""
        
        logger.info(f"{color}{arrow} TRANSLATION FLOW [{source_lang.upper()} → {target_lang.upper()}]{session_info}")
        logger.info(f"{color}   Original ({source_lang.upper()}): {Fore.WHITE}\"{original}\"")
        logger.info(f"{color}   Translated ({target_lang.upper()}): {Fore.WHITE}\"{translated}\"")
        logger.info(f"{color}{'-' * 60}")
        
        # Reset the current languages after logging
        self._current_source_lang = None
        self._current_target_lang = None
    
    async def translate_to_english(self, text: str, source_lang: str, session_id: str = "") -> str:
        """
        Translate any text to English with enhanced logging
        """
        if source_lang == 'en':
            return text
            
        try:
            lang_display = self._get_language_display(source_lang)
            logger.info(f"{Fore.CYAN}🎯 RECEIVED INPUT [{lang_display}]: {Fore.WHITE}\"{text}\"")
            
            # FIXED: Set current source language for proper logging
            self._current_source_lang = source_lang
            
            # For translation to English, we don't need to preserve language fields
            translated = GoogleTranslator(source=source_lang, target='en').translate(text)
            
            # Log the translation flow
            self._log_translation_flow(text, translated, "to_english", session_id)
            
            return translated
            
        except Exception as e:
            logger.error(f"{Fore.RED}❌ TRANSLATION TO ENGLISH FAILED: {e}")
            logger.info(f"{Fore.YELLOW}⚠️  Using original text as fallback")
            return text
    
    async def translate_from_english(self, english_text: str, target_lang: str, session_id: str = "") -> str:
        """
        Translate English text to target language with enhanced logging
        PRESERVES language-specific fields (name_bn, description_bn, etc.)
        """
        if target_lang == 'en':
            return english_text
            
        try:
            # FIXED: Set current target language for proper logging
            self._current_target_lang = target_lang
            
            # NEW: Extract and preserve language-specific fields before translation
            cleaned_text, preserved_fields = self._extract_and_preserve_language_fields(english_text, target_lang)
            
            logger.info(f"{Fore.MAGENTA}🛡️  PRESERVING {len(preserved_fields)} {target_lang.upper()} FIELDS: {list(preserved_fields.keys())}")
            
            # Translate only the cleaned text (without language fields)
            translated_cleaned = GoogleTranslator(source='en', target=target_lang).translate(cleaned_text)
            
            # NEW: Restore preserved language fields
            final_translated = self._restore_preserved_fields(translated_cleaned, preserved_fields)
            
            # Log the translation flow
            self._log_translation_flow(english_text, final_translated, "from_english", session_id)
            
            lang_display = self._get_language_display(target_lang)
            logger.info(f"{Fore.GREEN}📤 FINAL OUTPUT [{lang_display}]: {Fore.WHITE}\"{final_translated}\"")
            
            return final_translated
            
        except Exception as e:
            logger.error(f"{Fore.RED}❌ TRANSLATION FROM ENGLISH FAILED: {e}")
            logger.info(f"{Fore.YELLOW}⚠️  Using English text as fallback")
            return english_text
    
    def validate_language(self, language: str) -> bool:
        """
        Check if language is supported
        """
        return language in self.supported_languages

# Create global translator instance
translator = TranslationManager()

# Convenience functions for direct use
async def translate_to_english(text: str, source_lang: str, session_id: str = "") -> str:
    """Convenience function to translate any text to English"""
    return await translator.translate_to_english(text, source_lang, session_id)

async def translate_from_english(text: str, target_lang: str, session_id: str = "") -> str:
    """Convenience function to translate English text to target language"""
    return await translator.translate_from_english(text, target_lang, session_id)

def is_supported_language(language: str) -> bool:
    """Check if language code is supported"""
    return translator.validate_language(language)

def log_chat_session_start(session_id: str, language: str, user_message: str):
    """Log the start of a chat session"""
    lang_display = translator._get_language_display(language)
    logger.info(f"{Fore.BLUE}🚀 {'=' * 70}")
    logger.info(f"{Fore.BLUE}🚀 CHAT SESSION STARTED [{lang_display}] | Session: {session_id}")
    logger.info(f"{Fore.BLUE}🚀 {'=' * 70}")
    logger.info(f"{Fore.CYAN}📥 USER INPUT [{lang_display}]: {Fore.WHITE}\"{user_message}\"")

def log_chat_session_end(session_id: str, language: str, ai_response: str):
    """Log the end of a chat session"""
    lang_display = translator._get_language_display(language)
    logger.info(f"{Fore.GREEN}✅ CHAT SESSION COMPLETED [{lang_display}] | Session: {session_id}")
    logger.info(f"{Fore.GREEN}📤 AI RESPONSE [{lang_display}]: {Fore.WHITE}\"{ai_response}\"")
    logger.info(f"{Fore.GREEN}✅ {'=' * 70}")