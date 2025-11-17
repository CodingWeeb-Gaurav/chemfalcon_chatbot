# agents/request_details.py
import asyncio
import json
import re
from datetime import datetime, timedelta
from openai import AsyncOpenAI
import os
import phonenumbers
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Initialize Async client for OpenRouter
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Allowed units for user selection
ALLOWED_UNITS = ["KG", "GAL", "LB", "L"]

async def handle_request_details(user_input: str, session_data: dict):
    """
    Agent 2: Request Details Handler - Collects and validates all request details
    """
    try:
        # Check if we should hand over
        if session_data.get("agent") != "request_details":
            return "I'll hand you over to the next specialist.", session_data
        
        # Process with AI using validation tools
        ai_response = await process_request_details(user_input, session_data)
        
        # Update session from AI's tool calls
        if "session_updates" in ai_response:
            for key, value in ai_response["session_updates"].items():
                if value is not None:
                    # Initialize product_details if it doesn't exist
                    if "product_details" not in session_data:
                        session_data["product_details"] = {}
                    session_data["product_details"][key] = value
                    print(f"💾 Updated field: {key} = {value}")
            
            # Check if all fields are completed and hand over
            if ai_response.get("handover_ready", False):
                session_data["agent"] = "address_purpose"
                print("🚀 All fields completed - handing over to agent 3")
        
        # Add to history
        session_data.setdefault("history", []).append({
            "user": user_input, 
            "agent": ai_response["response"]
        })
        
        return ai_response["response"], session_data
        
    except Exception as e:
        print(f"❌ Error in handle_request_details: {e}")
        error_msg = "I apologize, but I'm having trouble processing your request. Please try again."
        session_data.setdefault("history", []).append({
            "user": user_input,
            "agent": error_msg
        })
        return error_msg, session_data

async def process_request_details(user_input: str, session_data: dict):
    """
    Process request details with validation tools - BULK PROCESSING VERSION
    """
    request_type = session_data.get("request", "").lower()
    product_details = session_data.get("product_details", {})
    
    # Get required fields for this request type
    required_fields = get_required_fields(request_type)
    completed_fields = get_completed_fields(product_details, required_fields)
    pending_fields = [f for f in required_fields if f not in completed_fields]
    
    # Build system prompt
    system_prompt = build_system_prompt(session_data, required_fields, completed_fields, pending_fields)
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add conversation history
    history = session_data.get("history", [])
    for entry in history[-20:]:  # Last 3 exchanges
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["agent"]})
    
    messages.append({"role": "user", "content": user_input})
    
    # Get AI response with tool calling
    try:
        response = await client.chat.completions.create(
            model="openai/gpt-4o",  # CHANGED: Using GPT-4o instead of Claude
            messages=messages,
            max_tokens=1000,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "extract_and_validate_all_fields",
                        "description": "Extract ALL field values from user message and validate them in bulk",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "extracted_fields": {
                                    "type": "object",
                                    "description": "All field values extracted from user message",
                                    "properties": {
                                        "unit": {
                                            "type": "string",
                                            "description": "Extracted unit value (KG, GAL, LB, L), must ask from User"
                                        },
                                        "quantity": {
                                            "type": "number",
                                            "description": "Extracted quantity value"
                                        },
                                        "price_per_unit": {
                                            "type": "number", 
                                            "description": "Extracted price per unit value"
                                        },
                                        "phone": {
                                            "type": "string",
                                            "description": "Extracted phone number"
                                        },
                                        "incoterm": {
                                            "type": "string",
                                            "description": "Extracted incoterm value"
                                        },
                                        "mode_of_payment": {
                                            "type": "string",
                                            "description": "Extracted payment method"
                                        },
                                        "packaging_pref": {
                                            "type": "string",
                                            "description": "Extracted packaging preference"
                                        },
                                        "delivery_date": {
                                            "type": "string",
                                            "description": "Extracted delivery date"
                                        }
                                    }
                                },
                                "request_type": {  # ADD THIS
                                    "type": "string",
                                    "description": "Type of request for validation rules"
                                }
                            },
                            "required": ["extracted_fields"]  # request_type is optional
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "validate_individual_field",
                        "description": "Validate a single field value",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "field_name": {
                                    "type": "string",
                                    "description": "Name of the field to validate",
                                    "enum": ["unit", "quantity", "phone", "delivery_date", "incoterm", "mode_of_payment", "packaging_pref"]
                                },
                                "field_value": {
                                    "type": "string",
                                    "description": "Value to validate"
                                },
                                "request_type": {  
                                    "type": "string", 
                                    "description": "Type of request (sample, order (order of purchase), quote (quotation or offer price), ppr (purchase price request)) for validation rules"
                                }
                            },
                            "required": ["field_name", "field_value"]  # request_type is optional
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_expected_price",
                        "description": "Calculate expected price from quantity and price per unit",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "quantity": {
                                    "type": "number",
                                    "description": "Quantity value"
                                },
                                "price_per_unit": {
                                    "type": "number",
                                    "description": "Price per unit in Bangladesh Taka"
                                }
                            },
                            "required": ["quantity", "price_per_unit"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "update_validated_field",
                        "description": "Update a field value after successful validation",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "field_name": {
                                    "type": "string",
                                    "description": "Name of the field to update"
                                },
                                "field_value": {
                                    "type": "string",
                                    "description": "Validated value to store"
                                }
                            },
                            "required": ["field_name", "field_value"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "check_completion_status",
                        "description": "Check if all required fields are completed",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "completed_fields": {
                                    "type": "array",
                                    "description": "List of completed field names",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["completed_fields"]
                        }
                    }
                }
            ],
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        response_content = message.content or ""
        tool_calls = message.tool_calls or []
        
        print(f"🧠 AI response: {response_content}")
        print(f"🔧 Tool calls: {len(tool_calls)}")
        
        # Process tool calls
        session_updates = {}
        handover_ready = False
        
        if tool_calls:
            follow_up_messages = messages.copy()
            follow_up_messages.append({
                "role": "assistant",
                "content": response_content,
                "tool_calls": tool_calls
            })
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"🛠️ Processing tool call: {function_name} with args: {function_args}")
                
                if function_name == "extract_and_validate_all_fields":
                    # Process all extracted fields in bulk
                    extracted_fields = function_args.get("extracted_fields", {})
                    req_type = function_args.get("request_type", request_type)
                    validation_results = {}
                    
                    # FIRST: Validate ALL fields before updating any
                    all_fields_valid = True
                    for field_name, field_value in extracted_fields.items():
                        if field_value is not None:
                            # Validate each field
                            if field_name == "unit":
                                result = validate_unit({"unit": field_value})
                            elif field_name == "quantity":
                                result = validate_quantity({"quantity": field_value}, product_details, req_type)
                            elif field_name == "delivery_date":
                                result = validate_date({"delivery_date": field_value})
                            elif field_name in ["incoterm", "mode_of_payment", "packaging_pref"]:
                                result = validate_selection({"field_name": field_name, "selected_value": field_value})
                            elif field_name == "phone":
                                result = validate_phone({"phone": field_value})
                            else:
                                result = {"is_valid": True, "message": f"{field_name} value accepted"}
                            
                            validation_results[field_name] = result
                            
                            # Check if any field is invalid
                            if not result.get("is_valid", False):
                                all_fields_valid = False
                                print(f"❌ Validation failed for {field_name}: {result.get('message')}")
                    
                    # SECOND: Only update session if ALL fields are valid
                    if all_fields_valid:
                        for field_name, field_value in extracted_fields.items():
                            if field_value is not None:
                                # For unit field, use the normalized value
                                if field_name == "unit":
                                    session_updates[field_name] = validation_results[field_name].get("normalized_value", field_value)
                                else:
                                    session_updates[field_name] = field_value
                                print(f"✅ Validated and will update {field_name}: {field_value}")
                    else:
                        # If any field is invalid, don't update ANY fields
                        print("🚫 Some fields failed validation - no updates will be made")
                    
                    # THIRD: Calculate expected price only if both quantity and price_per_unit are valid and provided
                    if (all_fields_valid and 
                        extracted_fields.get("quantity") and 
                        extracted_fields.get("price_per_unit") and
                        extracted_fields.get("price_per_unit") > 0):
                        
                        price_result = calculate_expected_price({
                            "quantity": extracted_fields["quantity"],
                            "price_per_unit": extracted_fields["price_per_unit"]
                        })
                        if price_result.get("status") == "success":
                            session_updates["expected_price"] = price_result["calculated_value"]
                            print(f"💰 Calculated expected price: {price_result['calculated_value']}")
                    
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "validation_results": validation_results,
                            "fields_updated": list(session_updates.keys()) if all_fields_valid else [],
                            "all_fields_valid": all_fields_valid
                        })
                    })
                    
                elif function_name == "validate_individual_field":
                    field_name = function_args["field_name"]
                    field_value = function_args["field_value"]
                    # GET THE REQUEST TYPE FROM ARGS OR USE THE ONE FROM SESSION
                    req_type = function_args.get("request_type", request_type)
                    
                    if field_name == "unit":
                        result = validate_unit({"unit": field_value})
                    elif field_name == "quantity":
                        # PASS THE REQUEST TYPE HERE
                        result = validate_quantity({"quantity": field_value}, product_details, req_type)
                    elif field_name == "delivery_date":
                        result = validate_date({"delivery_date": field_value})
                    elif field_name in ["incoterm", "mode_of_payment", "packaging_pref"]:
                        result = validate_selection({"field_name": field_name, "selected_value": field_value})
                    elif field_name == "phone":
                        result = validate_phone({"phone": field_value})
                    else:
                        result = {"is_valid": True, "message": f"{field_name} value accepted"}
                    
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
                    
                elif function_name == "calculate_expected_price":
                    result = calculate_expected_price(function_args)
                    if result.get("status") == "success":
                        session_updates["expected_price"] = result["calculated_value"]
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
                    
                elif function_name == "update_validated_field":
                    # For unit field, ensure we're storing the normalized value
                    if function_args["field_name"] == "unit":
                        unit_result = validate_unit({"unit": function_args["field_value"]})
                        if unit_result.get("is_valid", False):
                            session_updates[function_args["field_name"]] = unit_result.get("normalized_value", function_args["field_value"])
                        else:
                            # If invalid, don't update and return error
                            follow_up_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps({"status": "error", "message": f"Invalid unit: {function_args['field_value']}"})
                            })
                            continue
                    else:
                        session_updates[function_args["field_name"]] = function_args["field_value"]
                    
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"status": "success", "field_updated": function_args["field_name"]})
                    })
                    
                elif function_name == "check_completion_status":
                    result = check_completion_status(function_args, required_fields)
                    handover_ready = result.get("all_completed", False)
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            
            # Get final response after tool processing
            final_response_obj = await client.chat.completions.create(
                model="openai/gpt-4o",  # CHANGED: Using GPT-4o instead of Claude
                messages=follow_up_messages,
                max_tokens=800
            )
            final_response = final_response_obj.choices[0].message.content or ""
        else:
            final_response = response_content
        
        return {
            "response": final_response,
            "session_updates": session_updates,
            "handover_ready": handover_ready
        }
        
    except Exception as e:
        print(f"❌ Error in process_request_details: {e}")
        # Return a helpful response even when AI processing fails
        pending_fields = [f for f in get_required_fields(session_data.get("request", "").lower()) 
                         if session_data.get("product_details", {}).get(f) in [None, ""]]
        
        if pending_fields:
            response_msg = f"I need some additional information to process your {session_data.get('request', 'request')}. Please provide: {', '.join(pending_fields)}"
        else:
            response_msg = "Thank you for the information. I'm ready to proceed with your request."
            
        return {
            "response": response_msg,
            "session_updates": {},
            "handover_ready": len(pending_fields) == 0
        }

# Validation Functions - ADD UNIT VALIDATION
def validate_unit(args: dict) -> dict:
    """Validate unit is one of the allowed values"""
    unit_value = args["unit"].strip().upper()
    
    if unit_value in ALLOWED_UNITS:
        return {
            "is_valid": True,
            "message": f"Unit {unit_value} is valid",
            "normalized_value": unit_value,
            "allowed_units": ALLOWED_UNITS
        }
    else:
        return {
            "is_valid": False,
            "message": f"Invalid unit. Please select from: {', '.join(ALLOWED_UNITS)}",
            "allowed_units": ALLOWED_UNITS
        }

def validate_quantity(args: dict, product_details: dict, request_type: str = "") -> dict:
    """Validate quantity against product limits - with special rules for samples"""
    try:
        quantity = float(args["quantity"])
        min_quantity = float(product_details.get("minQuantity", 1))
        max_quantity = float(product_details.get("maxQuantity", float('inf')))
        
        # Special handling for sample requests
        if request_type.lower() == "sample":
            # For samples: allow decimal quantities like 0.01, no minimum, but still check maximum
            if quantity > max_quantity:
                return {
                    "is_valid": False,
                    "message": f"Sample quantity {quantity} exceeds available stock of {max_quantity}",
                    "suggested_max": max_quantity
                }
            else:
                return {
                    "is_valid": True,
                    "message": f"Sample quantity {quantity} is valid (max: {max_quantity})"
                }
        else:
            # For order/quotation: apply normal validation with minimum
            if quantity < min_quantity:
                return {
                    "is_valid": False,
                    "message": f"Quantity must be at least {min_quantity} (minimum order quantity)",
                    "suggested_min": min_quantity
                }
            elif quantity > max_quantity:
                return {
                    "is_valid": False,
                    "message": f"Quantity exceeds available stock of {max_quantity}",
                    "suggested_max": max_quantity
                }
            else:
                return {
                    "is_valid": True,
                    "message": f"Quantity {quantity} is valid (min: {min_quantity}, max: {max_quantity})"
                }
    except (ValueError, TypeError):
        return {
            "is_valid": False,
            "message": "Invalid quantity format. Please enter a valid number."
        }

def validate_date(args: dict) -> dict:
    """Validate delivery date is in the future"""
    delivery_date_str = args["delivery_date"]
    today = datetime.now().date()
    
    try:
        delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
        if delivery_date <= today:
            return {
                "is_valid": False,
                "message": f"Delivery date must be after today ({today.strftime('%Y-%m-%d')})",
                "today": today.strftime("%Y-%m-%d")
            }
        else:
            return {
                "is_valid": True,
                "message": f"Delivery date {delivery_date_str} is valid"
            }
    except ValueError:
        return {
            "is_valid": False,
            "message": "Invalid date format. Please use YYYY-MM-DD format (e.g., 2024-12-31)"
        }

def validate_selection(args: dict) -> dict:
    """Validate selection from allowed options"""
    field_name = args["field_name"]
    selected_value = args["selected_value"].strip()
    
    options_map = {
        "unit": ["KG", "GAL", "LB", "L"],
        "incoterm": ["Ex Factory", "Deliver to Buyer Factory"],
        "mode_of_payment": ["LC", "TT", "Cash"],
        "packaging_pref": ["Bulk Tanker", "PP Bag", "Jerry Can", "Drum"]
    }
    
    allowed_options = options_map.get(field_name, [])
    
    # Case-insensitive matching
    normalized_selected = selected_value.lower()
    normalized_options = [opt.lower() for opt in allowed_options]
    
    if normalized_selected in normalized_options:
        actual_value = allowed_options[normalized_options.index(normalized_selected)]
        return {
            "is_valid": True,
            "message": f"Selected {actual_value} is valid for {field_name}",
            "allowed_options": allowed_options,
            "normalized_value": actual_value
        }
    else:
        return {
            "is_valid": False,
            "message": f"Invalid selection for {field_name}. Allowed options: {', '.join(allowed_options)}",
            "allowed_options": allowed_options
        }


def validate_phone(args: dict) -> dict:
    """Validate international phone numbers - minimal version"""
    phone = args["phone"].strip()
    
    try:
        parsed_number = phonenumbers.parse(phone, None)
        is_valid = phonenumbers.is_valid_number(parsed_number)
        
        return {
            "is_valid": is_valid,
            "message": "Phone number is valid" if is_valid else "Invalid phone number format"
        }
            
    except phonenumbers.NumberParseException:
        return {
            "is_valid": False,
            "message": "Unable to parse phone number"
        }

def calculate_expected_price(args: dict) -> dict:
    """Calculate expected price from quantity and price per unit"""
    try:
        quantity = float(args["quantity"])
        price_per_unit = float(args["price_per_unit"])
        expected_price = quantity * price_per_unit
        
        return {
            "calculated_value": expected_price,
            "formula": f"{quantity} × {price_per_unit} = {expected_price}",
            "status": "success",
            "expected_price": expected_price
        }
    except (ValueError, TypeError) as e:
        return {
            "calculated_value": 0,
            "error": "Invalid input values for calculation",
            "status": "error"
        }

def check_completion_status(args: dict, required_fields: list) -> dict:
    """Check if all required fields are completed"""
    completed_fields = args["completed_fields"]
    pending_fields = [f for f in required_fields if f not in completed_fields]
    
    return {
        "all_completed": len(pending_fields) == 0,
        "completed_count": len(completed_fields),
        "total_required": len(required_fields),
        "pending_fields": pending_fields
    }

# Helper Functions
def get_required_fields(request_type: str) -> list:
    """Get required fields based on request type"""
    # Convert to lowercase for consistent comparison
    request_type_lower = request_type.lower()
    
    # Map request types to their required fields
    field_requirements = {
        "order":  ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],
        "sample": ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],
        "quote":  ["unit", "quantity", "price_per_unit", "expected_price", "phone", "incoterm", "mode_of_payment", "packaging_pref", "delivery_date"],  
        "ppr":    ["unit", "quantity", "price_per_unit", "expected_price", "delivery_date"]  # PPR has different requirements
    }
    
    # Return fields for the specific request type, or base fields if not found
    return field_requirements.get(request_type_lower, ["unit", "quantity", "price_per_unit", "expected_price"])

def get_completed_fields(product_details: dict, required_fields: list) -> list:
    """Get list of completed fields"""
    completed = []
    for field in required_fields:
        value = product_details.get(field)
        if value not in [None, "", 0, "0"]:
            completed.append(field)
    return completed

def build_system_prompt(session_data: dict, required_fields: list, completed_fields: list, pending_fields: list) -> str:
    """Build comprehensive system prompt for BULK PROCESSING"""
    request_type = session_data.get("request", "").upper()
    product_details = session_data.get("product_details", {})
    
    # ADD SPECIAL NOTE FOR SAMPLE QUANTITIES
    sample_note = ""
    if request_type.lower() == "sample":
        sample_note = "\n🚨 **SPECIAL SAMPLE RULE**: For sample requests, ANY quantity is allowed (even below the minQuantity) as long as it doesn't exceed maximum stock and is a number without decimal. NO minimum quantity requirement for samples!"
    
    prompt = f"""You are a **Request Details Specialist** for chemical product orders.
You are the second agent in a triple-agent system where you collect and validate all necessary details for processing user requests.
The first agent has already provided the product and request type. After your completion, you will hand over to the third agent who manages address and purpose by changing the session's agent to "address_purpose".
Your job is to collect and validate all required details for a {request_type} request.
Always respond with a markdown formatted message with proper line breaks but no text enlargement (headings).

🚨 **CRITICAL VALIDATION POLICY**: 
- The user MUST select a unit from these 4 options only: KG, GAL, LB, L
- There is NO default unit from the product data - user chooses freely from the 4 options
- Never convert or assume any unit. If user gives 1200 grams, ask them to choose from the 4 options.
- All prices must be in Bangladeshi Taka. Never convert currencies yourself.
- Always ask for Bangladeshi Taka price upfront (converted from user side)
- Always write full name of currency as "Bangladeshi Taka" in your messages, never use BDT or ৳ symbol.

PRODUCT INFORMATION:
- Product: {session_data.get('product_name', 'N/A')}
- Request Type: {request_type}
- Available Stock: {product_details.get('maxQuantity', 'N/A')}
- Minimum Order: {product_details.get('minQuantity', 'N/A')}
{sample_note}

ALL REQUIRED FIELDS for {request_type}:
{format_fields_info(required_fields, session_data)}

FIELD OPTIONS:
- Unit: KG (kilogram), GAL (gallon), LB (pound), L (liter) (user MUST choose one)
- Incoterm: 1. Ex Factory (Ex Works or Delivery From Factory) 2. Deliver to Buyer Factory
- Payment: 1. LC (Letter of Credit), 2. TT (Telegraphic transfer or Bank Transfer), 3. Cash
- Packaging: 1. Bulk Tanker (in Truck), 2. PP Bag, 3. Jerry Can, 4. Drum
- PPR requests do not need Incoterm, Payment Method or Packaging preference.

CURRENT PROGRESS:
Completed: {len(completed_fields)}/{len(required_fields)} fields
{format_progress(completed_fields, pending_fields, product_details)}

## 🚀 PROCESSING STRATEGY

### **TOOL SELECTION GUIDE:**
- **For NEW multi-field data**: Use `extract_and_validate_all_fields` (processes all fields at once)
- **For INDIVIDUAL field changes**: Use `update_validated_field` (changes one specific field)
- **For validation checks**: Use `validate_individual_field` (validate without updating)
- **For price calculation**: Use `calculate_expected_price` (when both quantity and price_per_unit are valid)

### **VALIDATION RULES:**
🚨 **ALL-OR-NOTHING VALIDATION**: When using `extract_and_validate_all_fields`, ALL extracted fields must pass validation for ANY to be saved. If ANY field fails validation, NO fields are updated.
  **WHEN USER REQUESTS FIELD CHANGES, YOU MUST CALL update_validated_field TOOL:**
  **NEVER** just acknowledge changes in your response without calling the tool. The session data will NOT be updated unless you call update_validated_field.

### **WORKFLOW STEPS:**

1. **INITIAL COLLECTION**:
   - Show ALL missing fields in first message
   - Use `extract_and_validate_all_fields` to process user's response
   - If validation fails for any field, inform user and ask for correction
   - If all fields valid, proceed to confirmation
   - When showing the Field options in initial message, use '•' points like 'Incoterm : • Ex Factory (Delivery from factory or ex works) • Deliver to Buyer Factory' or 'Payment Method : • LC • TT • Cash' or 'Packaging Preference : • Bulk Tanker (in Truck) • PP Bag • Jerry Can • Drum' or 'Unit : • KG (Kilogram) • GAL (Gallon) • LB (Pound) • L (Liter)'
   - If user gives unclear or ambiguous input of Packaging Preference, Incoterm, Unit or Mode of Payment, then you must ask for clarification by showing the options again using ordered indexed list instead of bullet points(e.g., 1. Bulk Tanker (in Truck), \n 2. PP Bag, \n 3. Jerry Can, \n 4. Drum) and ask to select by index. But each field should be asked separately, not all at once in such case.


2. **FIELD UPDATES**:
   - If user wants to change specific fields, use `update_validated_field` for each changed field
   - Always validate before updating
   - Confirm the change was successful

3. **FINAL CONFIRMATION**:
   - When ALL fields are completed and validated, show summary:
     ```
     Please confirm your order details:
     • Unit: [value]
     • Quantity: [value] 
     • Price per unit: [value] Bangladeshi Taka
     • Expected price: [value] Bangladeshi Taka
     • Phone: [value]
     • Incoterm: [value]
     • Payment: [value]
     • Packaging: [value]
     • Delivery: [value]
     ```
   - Ask: "Please reply 'Yes' to confirm all details are correct, or specify any changes needed."
   - Only proceed after user explicitly confirms with "Yes"

4. **HANDOVER**:
   - After user confirmation, call `check_completion_status`
   - Hand over to next agent silently (do not mention agent change to user)

### **RESPONSE GUIDELINES:**
- Always validate silently in background
- If validation fails, mention ONLY the invalid fields and what needs correction
- Keep conversation flowing naturally without unnecessary confirmations
- Calculate expected_price automatically when both quantity and price_per_unit are valid
- For ambiguous inputs (packaging, incoterm, payment), show options and ask for clarification
- Use bullet points (•) when showing field options

### **ERROR HANDLING:**
- **Invalid quantity**: Show min/max limits and ask for correction
- **Invalid unit**: Show the 4 allowed options
- **Invalid currency**: Ask for Bangladeshi Taka price
- **Invalid date**: Show correct format (YYYY-MM-DD) and ensure future date
- **Invalid selection**: Show allowed options for that field

### **LIMITATIONS:**
- You can only update required fields for the current request
- If user wants to change product or request type, politely refuse and suggest refreshing session
- After final confirmation and handover, no more changes can be made

## **TOOLS AVAILABLE:**
- `extract_and_validate_all_fields`: Process multiple fields at once (all-or-nothing validation)
- `update_validated_field`: Update individual validated fields  
- `validate_individual_field`: Validate single field without updating
- `calculate_expected_price`: Compute total price from quantity × price per unit
- `check_completion_status`: Verify all required fields are completed

**START NOW: Show missing fields and invite user to provide all details.**"""

    return prompt

def format_fields_info(required_fields: list, session_data: dict) -> str:
    """Format field information for prompt"""
    product_details = session_data.get("product_details", {})
    request_type = session_data.get("request", "").lower()
    
    field_descriptions = {
        "unit": "Unit of measurement • KG • GAL • LB • L (choose one)",
        "price_per_unit": "Your offered price per unit in Bangladeshi Taka",
        "expected_price": "Total expected price (auto-calculated)",
        "phone": "Contact phone number (international format: +(country code)(phone number))",
        "incoterm": "Delivery terms (1. Ex Factory [ex works or Delivery From Factory] or 2. Deliver to Buyer Factory)",
        "mode_of_payment": "Payment method (1. LC (Letter of Credit), 2. TT (Telegraphic or Bank Transfer), 3. Cash)",
        "packaging_pref": "Packaging preference (1. Bulk Tanker (in Truck), 2. PP Bag, 3. Jerry Can, 4. Drum)",
        "delivery_date": f"Delivery date (after {datetime.now().strftime('%Y-%m-%d')}, YYYY-MM-DD format)"
    }
    
    # SPECIAL HANDLING FOR QUANTITY FIELD BASED ON REQUEST TYPE
    if request_type == "sample":
        field_descriptions["quantity"] = f"Sample quantity required (any amount up to {product_details.get('maxQuantity', 'available')} - no minimum for samples)"
    else:
        field_descriptions["quantity"] = f"Quantity required (≥{product_details.get('minQuantity', 1)} and ≤{product_details.get('maxQuantity', 'available')})"
    
    return "\n".join([f"- {field}: {field_descriptions.get(field, field)}" for field in required_fields])

def format_progress(completed_fields: list, pending_fields: list, product_details: dict) -> str:
    """Format progress information"""
    lines = []
    
    if completed_fields:
        lines.append("✅ Completed:")
        for field in completed_fields:
            value = product_details.get(field, "")
            lines.append(f"  - {field}: {value}")
    
    if pending_fields:
        lines.append("📋 Still needed:")
        for field in pending_fields:
            lines.append(f"  - {field}")
    
    return "\n".join(lines) if lines else "No fields completed yet."