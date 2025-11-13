# core/utils.py also manages translation with enhanced logging

import logging
import re
import json
from deep_translator import GoogleTranslator
from typing import Optional, Dict, Any, Tuple
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
    Uses deep-translator (free Google Translate API) with translation memory for Arabic only
    """
    
    def __init__(self):
        self.supported_languages = {
            'en': {'name': 'english', 'color': Fore.GREEN},
            'ar': {'name': 'arabic', 'color': Fore.CYAN}, 
            'bn': {'name': 'bengali', 'color': Fore.YELLOW}
        }
        self._current_source_lang = None
        self._current_target_lang = None
        
        # Initialize translation memory - ARABIC ONLY
        self._translation_memory = self._initialize_translation_memory()
    
    def _initialize_translation_memory(self) -> Dict[str, Dict[str, str]]:
        """
        Initialize translation memory with industry-specific terms - ARABIC ONLY
        Structure: { 'english_term': { 'ar': 'arabic_translation' } }
        """
        return {
            # Client-provided Arabic translations
            'sample': {
                'ar': 'العينة'
            },
            'order': {
                'ar': 'الطلب'
            },
            'quotation': {
                'ar': 'عرض الأسعار'
            },
            'bulk tanker': {
                'ar': 'ناقل البضائع السائبة'
            },
            'ex factory': {
                'ar': 'التسليم من المصنع'
            },
            # ADD CURRENCY TERMS TO PREVENT WRONG TRANSLATIONS
            'bdt': {
                'ar': 'تاكا بنغلاديشي'
            },
            'bangladeshi taka': {
                'ar': 'تاكا بنغلاديشي'
            },
            'taka': {
                'ar': 'تاكا'
            },
            'bdt (bangladeshi taka)': {
                'ar': 'تاكا بنغلاديشي'
            },
            
            # Add more currency protection
            'price in bdt': {
                'ar': 'السعر بالتاكا البنغلاديشي'
            },
            'bangladeshi taka (bdt)': {
                'ar': 'تاكا بنغلاديشي'
            },
            # 'lc': {
            #     'ar': 'نموذج خطاب الاعتماد الكامل'
            # },
            # 'tt': {
            #     'ar': 'نموذج خطاب الاعتماد الكامل'
            # }
        }
    
    def _normalize_term(self, term: str) -> str:
        """
        Normalize terms for matching (case-insensitive, handle variations)
        """
        # Convert to lowercase and strip whitespace
        normalized = term.lower().strip()
        
        # Handle common variations
        variations = {
            'ex factory': 'ex factory',
            'ex-factory': 'ex factory', 
            'ex works': 'ex factory',
            'bulk tanker': 'bulk tanker',
            'bulk-tanker': 'bulk tanker',
            'bulk carrier': 'bulk carrier',
            'bulk-carrier': 'bulk carrier',
            'tt': 'tt',
            't.t': 'tt',
            'telegraphic transfer': 'tt',
            'lc': 'lc',
            'letter of credit': 'lc',
            'full lc': 'full letter of credit'
        }
        
        return variations.get(normalized, normalized)
    
    def _find_terms_in_text(self, text: str, language: str) -> Dict[str, str]:
        """
        Find known terms in text and return their translations
        Only for Arabic language
        """
        if language != 'ar':
            return {}
            
        found_terms = {}
        
        # Check each term in translation memory
        for english_term, translations in self._translation_memory.items():
            # Create pattern to match the term (case-insensitive, word boundaries)
            pattern = r'\b' + re.escape(english_term) + r'\b'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                if 'ar' in translations:
                    found_terms[match.group()] = translations['ar']
        
        return found_terms
    
    def _apply_translation_memory_after_translation(self, translated_text: str, target_lang: str) -> Tuple[str, Dict[str, str]]:
        """
        Apply translation memory AFTER main translation
        ONLY for Arabic language to prevent mixed-language issues
        """
        if target_lang != 'ar':
            return translated_text, {}
        
        # Find and replace known terms in the already-translated text
        term_translations = self._find_terms_in_text(translated_text, target_lang)
        processed_text = translated_text
        applied_translations = {}
        
        for original_term, correct_translation in term_translations.items():
            # Replace the term while preserving context
            pattern = re.compile(re.escape(original_term), re.IGNORECASE)
            
            def replace_preserve_case(match):
                return correct_translation
            
            processed_text = pattern.sub(replace_preserve_case, processed_text)
            applied_translations[original_term] = correct_translation
        
        return processed_text, applied_translations
    
    def _reverse_translation_lookup(self, text: str, source_lang: str) -> Tuple[str, Dict[str, str]]:
        """
        For translation to English: find Arabic terms and convert back to English
        Only for Arabic source language
        """
        if source_lang != 'ar':
            return text, {}
        
        processed_text = text
        applied_translations = {}
        
        # Check each term in translation memory for reverse lookup
        for english_term, translations in self._translation_memory.items():
            if 'ar' in translations:
                translated_term = translations['ar']
                
                # Look for the translated term in the text
                if translated_term in text:
                    processed_text = processed_text.replace(translated_term, english_term)
                    applied_translations[translated_term] = english_term
        
        return processed_text, applied_translations
    
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
    
    def _log_translation_flow(self, original: str, translated: str, direction: str, session_id: str = "", memory_applied: Dict[str, str] = None):
        """Enhanced logging for translation flow"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if direction == "to_english":
            source_lang = self._current_source_lang if self._current_source_lang else 'unknown'
            target_lang = 'en'
            arrow = "🔄"
            color = Fore.BLUE
        else:
            source_lang = 'en'
            target_lang = self._current_target_lang if self._current_target_lang else 'unknown'
            arrow = "🔄"
            color = Fore.MAGENTA
        
        session_info = f" | Session: {session_id}" if session_id else ""
        
        logger.info(f"{color}{arrow} TRANSLATION FLOW [{source_lang.upper()} → {target_lang.upper()}]{session_info}")
        
        # Log memory applications if any
        if memory_applied:
            logger.info(f"{color}   🧠 TRANSLATION MEMORY APPLIED: {memory_applied}")
        
        logger.info(f"{color}   Original ({source_lang.upper()}): {Fore.WHITE}\"{original}\"")
        logger.info(f"{color}   Translated ({target_lang.upper()}): {Fore.WHITE}\"{translated}\"")
        logger.info(f"{color}{'-' * 60}")
        
        # Reset the current languages after logging
        self._current_source_lang = None
        self._current_target_lang = None
    
    async def translate_to_english(self, text: str, source_lang: str, session_id: str = "") -> str:
        """
        Translate any text to English with enhanced logging and translation memory
        """
        if source_lang == 'en':
            return text
            
        try:
            lang_display = self._get_language_display(source_lang)
            logger.info(f"{Fore.CYAN}🎯 RECEIVED INPUT [{lang_display}]: {Fore.WHITE}\"{text}\"")
            
            # Set current source language for proper logging
            self._current_source_lang = source_lang
            
            # Apply reverse translation memory first (Arabic only)
            processed_text, memory_applied = self._reverse_translation_lookup(text, source_lang)
            
            if memory_applied:
                logger.info(f"{Fore.YELLOW}🔄 REVERSE TRANSLATION MEMORY: {memory_applied}")
            
            # Translate the processed text
            translated = GoogleTranslator(source=source_lang, target='en').translate(processed_text)
            
            # Log the translation flow with memory info
            self._log_translation_flow(text, translated, "to_english", session_id, memory_applied)
            
            return translated
            
        except Exception as e:
            logger.error(f"{Fore.RED}❌ TRANSLATION TO ENGLISH FAILED: {e}")
            logger.info(f"{Fore.YELLOW}⚠️  Using original text as fallback")
            return text
    
    async def translate_from_english(self, english_text: str, target_lang: str, session_id: str = "") -> str:
        """
        Translate English text to target language with enhanced logging
        PRESERVES language-specific fields and applies translation memory AFTER translation (Arabic only)
        """
        if target_lang == 'en':
            return english_text
            
        try:
            # Set current target language for proper logging
            self._current_target_lang = target_lang
            
            # Step 1: Extract and preserve language-specific fields
            cleaned_text, preserved_fields = self._extract_and_preserve_language_fields(english_text, target_lang)
            
            if preserved_fields:
                logger.info(f"{Fore.MAGENTA}🛡️  PRESERVING {len(preserved_fields)} {target_lang.upper()} FIELDS: {list(preserved_fields.keys())}")
            
            # Step 2: Translate the cleaned text FIRST (without memory interference)
            translated_cleaned = GoogleTranslator(source='en', target=target_lang).translate(cleaned_text)
            
            # Step 3: Apply translation memory AFTER main translation (Arabic only)
            memory_corrected_text, memory_applied = self._apply_translation_memory_after_translation(translated_cleaned, target_lang)
            
            if memory_applied:
                logger.info(f"{Fore.GREEN}🧠 TRANSLATION MEMORY CORRECTIONS: {memory_applied}")
            
            # Step 4: Restore preserved language fields
            final_translated = self._restore_preserved_fields(memory_corrected_text, preserved_fields)
            
            # Log the translation flow with memory info
            self._log_translation_flow(english_text, final_translated, "from_english", session_id, memory_applied)
            
            lang_display = self._get_language_display(target_lang)
            logger.info(f"{Fore.GREEN}📤 FINAL OUTPUT [{lang_display}]: {Fore.WHITE}\"{final_translated}\"")
            
            return final_translated
            
        except Exception as e:
            logger.error(f"{Fore.RED}❌ TRANSLATION FROM ENGLISH FAILED: {e}")
            logger.info(f"{Fore.YELLOW}⚠️  Using English text as fallback")
            return english_text
    
    def add_translation_memory_entry(self, english_term: str, arabic_translation: str = None):
        """
        Add new terms to translation memory - Arabic only
        """
        self._translation_memory[english_term.lower()] = {
            'ar': arabic_translation or english_term
        }
        logger.info(f"{Fore.GREEN}✅ Added to Arabic translation memory: '{english_term}' -> '{arabic_translation}'")
    
    def get_translation_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the translation memory
        """
        total_terms = len(self._translation_memory)
        arabic_terms = sum(1 for term in self._translation_memory.values() if term.get('ar'))
        
        return {
            'total_terms': total_terms,
            'arabic_translations': arabic_terms,
            'terms': list(self._translation_memory.keys())
        }
    
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

def add_translation_memory_entry(english_term: str, arabic_translation: str = None):
    """Add new terms to translation memory - Arabic only"""
    translator.add_translation_memory_entry(english_term, arabic_translation)

def get_translation_memory_stats() -> Dict[str, Any]:
    """Get translation memory statistics"""
    return translator.get_translation_memory_stats()

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