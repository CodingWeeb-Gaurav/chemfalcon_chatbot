
# agents/address_purpose.py
import asyncio
import json
import aiohttp
import ssl
import certifi
from openai import AsyncOpenAI

import os
from dotenv import load_dotenv
load_dotenv()

# Import the order placement function
from services.order_placement import place_order_request

# Initialize Async client for OpenRouter
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Authentication token
# AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiI2OGQ2MTViMDNlZWUyNGYyNmM2MjhmNjUiLCJpYXQiOjE3NjEzMTAxMzcsImV4cCI6MTc2OTA4NjEzN30.h0rKTjeHWHHvCfWojvBMm1KweDR06CfxOt_3QmL6v9A"

async def fetch_and_cache_data(session_data: dict):
    """Fetch addresses and industries and cache them in session data"""
    print("🔄 Fetching and caching addresses and industries...")
    
    # Fetch addresses with the actual user token
    addresses_result = await fetch_user_addresses(session_data)  # Pass session_data here
    if addresses_result.get("status") == "success":
        session_data["_cached_addresses"] = addresses_result["addresses"]
        print(f"✅ Cached {len(addresses_result['addresses'])} REAL addresses")
        for addr in addresses_result["addresses"]:
            print(f"   - {addr.get('addressLine', 'Unknown')}")
    else:
        session_data["_cached_addresses"] = []
        print(f"❌ Failed to fetch addresses: {addresses_result.get('error', 'Unknown error')}")
    
    # Fetch industries (no auth needed)
    industries_result = await fetch_industries()
    if industries_result.get("status") == "success":
        session_data["_cached_industries"] = industries_result["industries"]
        print(f"✅ Cached {len(industries_result['industries'])} REAL industries")
        for industry in industries_result["industries"]:
            print(f"   - {industry.get('name_en', 'Unknown')}")
    else:
        session_data["_cached_industries"] = []
        print(f"❌ Failed to fetch industries: {industries_result.get('error', 'Unknown error')}")
    
    # Mark as fetched
    session_data["_cached_data_fetched"] = True


async def handle_address_purpose(user_input: str, session_data: dict):
    """
    Agent 3: Address and Purpose Handler - Collects delivery address and industry
    Automatically starts with industries when triggered
    """
    try:
        print(f"🔍 Agent 3 - Starting with session_data keys: {list(session_data.keys())}")
        
        # Check if we should hand over
        if session_data.get("agent") != "address_purpose":
            print("🚫 Handover condition - agent 3 idle")
            return "I'll hand you over to the next specialist.", session_data
        
        # 🔥 NEW: Fetch addresses and industries on first entry to Agent 3
        if not session_data.get("_cached_data_fetched"):
            print("🚀 First time in Agent 3 - Fetching addresses and industries...")
            await fetch_and_cache_data(session_data)
        
        # Check if we have valid data
        cached_industries = session_data.get("_cached_industries", [])
        cached_addresses = session_data.get("_cached_addresses", [])
        
        # 🔧 FIX: If no data available, show error immediately
        if not cached_industries and not cached_addresses:
            error_msg = "I apologize, but I'm unable to fetch the required data (industries and addresses) at the moment. Please try again later or contact support."
            session_data.setdefault("history", []).append({
                "user": user_input,
                "agent": error_msg
            })
            return error_msg, session_data
        
        # 🔥 NEW: Auto-trigger industries display on first interaction
        is_first_interaction = len(session_data.get("history", [])) == 0
        if is_first_interaction and cached_industries:
            print("🎯 Auto-triggering industries display on first interaction")
            # Add a system message to trigger industries display
            auto_trigger_msg = "SYSTEM: Auto-display industries as this is the first interaction in Agent 3. Show ONLY REAL industries from API immediately and ask user to select one."
            user_input = f"{auto_trigger_msg}\n\nUser: {user_input}"
        
        # Process with AI using tool calling
        ai_response = await process_address_purpose(user_input, session_data)
        
        # Update session from AI's tool calls
        if "session_updates" in ai_response:
            for key, value in ai_response["session_updates"].items():
                if value is not None:
                    session_data[key] = value
                    print(f"💾 Agent 3 updated session: {key} = {value}")
        
        # Add to history
        session_data.setdefault("history", []).append({
            "user": user_input.replace(auto_trigger_msg + "\n\n", "") if 'auto_trigger_msg' in locals() else user_input,
            "agent": ai_response["response"]
        })
        
        return ai_response["response"], session_data
        
    except Exception as e:
        print(f"❌ Error in handle_address_purpose: {e}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        error_msg = "I apologize, but I'm having trouble processing your address information. Please try again."
        session_data.setdefault("history", []).append({
            "user": user_input,
            "agent": error_msg
        })
        return error_msg, session_data

async def process_address_purpose(user_input: str, session_data: dict):
    """
    Process address and purpose details with cached data using GPT-4.1
    """
    # Build system prompt
    system_prompt = build_system_prompt(session_data)
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add conversation history
    history = session_data.get("history", [])
    for entry in history[-18:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["agent"]})
    
    # Check if we need to auto-show data (first interaction or user asking for data)
    cached_industries = session_data.get("_cached_industries", [])
    cached_addresses = session_data.get("_cached_addresses", [])
    
    should_auto_show = (
        len(history) == 0 or  # First interaction
        "SYSTEM: Auto-display industries" in user_input or
        "industr" in user_input.lower() or
        "address" in user_input.lower() or
        "show" in user_input.lower() or
        "list" in user_input.lower() or
        "give me" in user_input.lower()
    )
    
    if should_auto_show:
        # Add instruction to show available data
        if cached_industries and cached_addresses:
            messages.append({
                "role": "system",
                "content": "AUTO-SHOW BOTH: Display ONLY REAL industries and addresses from API as numbered lists immediately. Start with industries first."
            })
        elif cached_industries:
            messages.append({
                "role": "system", 
                "content": "AUTO-SHOW INDUSTRIES: Display ONLY REAL industries from API as numbered list immediately and ask user to select one."
            })
        elif cached_addresses:
            messages.append({
                "role": "system",
                "content": "AUTO-SHOW ADDRESSES: Display ONLY REAL addresses from API as numbered list immediately and ask user to select one."
            })
    
    messages.append({"role": "user", "content": user_input})
    
    # Get AI response with tool calling using GPT-4.1
    response = await client.chat.completions.create(
        model="openai/gpt-4.1",
        messages=messages,
        max_tokens=1000,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_cached_industries",
                    "description": "Get the ACTUAL pre-fetched industries list from API. Only use if industries are available. Auto-call this on first interaction.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cached_addresses",
                    "description": "Get the ACTUAL pre-fetched addresses list from API. Only use if addresses are available.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "select_industry",
                    "description": "Store the selected industry ID and name when user chooses from the ACTUAL list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "industry_id": {
                                "type": "string",
                                "description": "The _id of the selected industry"
                            },
                            "industry_name": {
                                "type": "string", 
                                "description": "The name_en of the selected industry"
                            }
                        },
                        "required": ["industry_id", "industry_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "select_address",
                    "description": "Store the complete address object for the selected address when user chooses from the ACTUAL list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address_object": {
                                "type": "object",
                                "description": "The complete address object with all fields"
                            }
                        },
                        "required": ["address_object"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "show_final_confirmation",
                    "description": "Display all collected data including address and industry for final confirmation. Auto-call this when both industry and address are selected.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confirmation_ready": {
                                "type": "boolean",
                                "description": "Whether both address and industry are collected"
                            }
                        },
                        "required": ["confirmation_ready"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "place_order_final",
                    "description": "Place the final order after user confirms everything. Only call when user explicitly confirms.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_confirmed": {
                                "type": "boolean",
                                "description": "Whether user has explicitly confirmed to place the order"
                            }
                        },
                        "required": ["user_confirmed"]
                    }
                }
            }
        ],
        tool_choice="auto"
    )
    
    message = response.choices[0].message
    response_content = message.content or ""
    tool_calls = message.tool_calls or []
    
    print(f"🧠 Agent 3 GPT-4.1 response: {response_content}")
    print(f"🔧 Tool calls: {len(tool_calls)}")
    
    # Process tool calls
    session_updates = {}
    final_response = response_content
    
    if tool_calls:
        follow_up_messages = messages.copy()
        follow_up_messages.append({
            "role": "assistant",
            "content": response_content,
            "tool_calls": tool_calls
        })
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            
            # Handle empty/invalid JSON arguments safely
            try:
                function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON decode error for {function_name}: {e}")
                function_args = {}
            
            print(f"🛠️ Agent 3 Processing tool call: {function_name} with args: {function_args}")
            
            if function_name == "get_cached_industries":
                result = get_cached_industries(session_data)
                follow_up_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })
                
            elif function_name == "get_cached_addresses":
                result = get_cached_addresses(session_data)
                follow_up_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })
                
            elif function_name == "select_industry":
                session_updates["industry_id"] = function_args.get("industry_id")
                session_updates["industry_name"] = function_args.get("industry_name")
                follow_up_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "success"})
                })
                
                # 🔥 NEW: Auto-trigger address selection after industry is selected
                cached_addresses = session_data.get("_cached_addresses", [])
                if cached_addresses and not session_data.get("address"):
                    print("🎯 Industry selected - auto-triggering address display")
                    follow_up_messages.append({
                        "role": "system",
                        "content": "AUTO-SHOW ADDRESSES: Industry selected. Now display ONLY REAL addresses from API as numbered list immediately and ask user to select one."
                    })
                
            elif function_name == "select_address":
                address_object = function_args.get("address_object")
                cached_addresses = session_data.get("_cached_addresses", [])
                
                print(f"🔍 Raw address_object received: {address_object}")
                print(f"🔍 Cached addresses available: {len(cached_addresses)}")
                
                # 🔥 FIX: Handle different types of address selection
                selected_address = None
                
                if isinstance(address_object, dict) and address_object.get("_id"):
                    # Complete address object provided
                    selected_address = address_object
                    print(f"✅ Using complete address object with ID: {selected_address.get('_id')}")
                
                elif isinstance(address_object, str) and address_object.isdigit():
                    # User provided a list number
                    list_number = int(address_object) - 1
                    if 0 <= list_number < len(cached_addresses):
                        selected_address = cached_addresses[list_number]
                        print(f"🔄 Converted list number {address_object} to address: {selected_address.get('_id')}")
                
                elif isinstance(address_object, str):
                    # User provided address text - try to match
                    for addr in cached_addresses:
                        if address_object.lower() in addr.get("addressLine", "").lower():
                            selected_address = addr
                            print(f"🔄 Matched address text to: {addr.get('_id')}")
                            break
                
                # 🔥 FIX: If still no address found, try to extract from user input
                if not selected_address and cached_addresses:
                    user_input_lower = user_input.lower()
                    # Look for numbers in user input
                    for word in user_input_lower.split():
                        if word.isdigit():
                            list_number = int(word) - 1
                            if 0 <= list_number < len(cached_addresses):
                                selected_address = cached_addresses[list_number]
                                print(f"🔄 Extracted address from user input: {list_number + 1}")
                                break
                
                # Store the selected address
                if selected_address:
                    session_updates["address"] = selected_address
                    print(f"✅ Stored REAL address: {selected_address.get('_id')} - {selected_address.get('addressLine', '')}")
                    
                    # 🔥 NEW: Auto-trigger final confirmation after address is selected
                    if session_data.get("industry_id") or session_updates.get("industry_id"):
                        print("🎯 Address selected - auto-triggering final confirmation")
                        follow_up_messages.append({
                            "role": "system", 
                            "content": "AUTO-SHOW FINAL CONFIRMATION: Both industry and address collected. Show final confirmation with all order details immediately."
                        })
                else:
                    # Don't create dummy addresses - fail gracefully
                    error_msg = "No valid address selected. Please choose from the available addresses."
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"status": "error", "message": error_msg})
                    })
                    # Don't update session with invalid address
                    continue
                
                follow_up_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "success", "address_id": selected_address.get("_id")})
                })              
            elif function_name == "show_final_confirmation":
                # Check if we have both industry and address
                has_industry = session_data.get("industry_id") or session_updates.get("industry_id")
                has_address = session_data.get("address") or session_updates.get("address")
                confirmation_ready = has_industry and has_address
                
                result = show_final_confirmation(session_data, confirmation_ready)
                follow_up_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })
                
            elif function_name == "place_order_final":
                if function_args.get("user_confirmed"):
                    print("🎯 User confirmed - placing order...")
                    order_result = await place_order_request(session_data)
                    
                    if order_result["status"] == "success":
                        follow_up_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "status": "success",
                                "message": order_result["message"],
                                "order_placed": True
                            })
                        })
                    else:
                        error_message = f"Order failed: {order_result['message']} (Error: {order_result.get('error_type', 'Unknown')})"
                        follow_up_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "status": "error",
                                "message": error_message,
                                "error_type": order_result.get("error_type"),
                                "order_placed": False
                            })
                        })
                else:
                    follow_up_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "status": "error", 
                            "message": "User confirmation required to place order"
                        })
                    })
        
        # Get final response with GPT-4.1
        final_response_obj = await client.chat.completions.create(
            model="openai/gpt-4.1",
            messages=follow_up_messages,
            max_tokens=800
        )
        final_response = final_response_obj.choices[0].message.content or ""
    else:
        final_response = response_content
    
    return {
        "response": final_response,
        "session_updates": session_updates
    }

# Cached Data Functions
def get_cached_industries(session_data: dict):
    """Get cached industries from session data - ONLY REAL DATA"""
    industries = session_data.get("_cached_industries", [])
    if not industries:
        return {
            "industries": [],
            "count": 0,
            "status": "error",
            "message": "No industries available from API"
        }
    
    # Format industries for display - ONLY REAL DATA
    formatted_industries = []
    for i, industry in enumerate(industries, 1):
        formatted_industries.append({
            "number": i,
            "id": industry.get("_id"),
            "name": industry.get("name_en", "Unknown Industry")
        })
    
    print(f"📊 Returning {len(formatted_industries)} REAL industries from API")
    return {
        "industries": formatted_industries,
        "count": len(industries),
        "status": "success",
        "message": f"Found {len(industries)} REAL industries from API"
    }

def get_cached_addresses(session_data: dict):
    """Get cached addresses from session data - ONLY REAL DATA"""
    addresses = session_data.get("_cached_addresses", [])
    if not addresses:
        return {
            "addresses": [],
            "count": 0,
            "status": "error",
            "message": "No addresses available from API"
        }
    
    # Format addresses for display - ONLY REAL DATA
    formatted_addresses = []
    for i, address in enumerate(addresses, 1):
        formatted_addresses.append({
            "number": i,
            "id": address.get("_id"),
            "addressLine": address.get("addressLine", "Unknown Address"),
            "name": address.get("name", ""),
            "email": address.get("email", ""),
            "phoneNumber": address.get("phoneNumber", ""),
            "countryCode": address.get("countryCode", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "country": address.get("country", ""),
            "latitude": address.get("latitude", ""),
            "longitude": address.get("longitude", "")
        })
    
    print(f"📊 Returning {len(formatted_addresses)} REAL addresses from API")
    return {
        "addresses": formatted_addresses,
        "count": len(addresses),
        "status": "success",
        "message": f"Found {len(addresses)} REAL addresses from API"
    }

# API Integration Functions (NO FALLBACKS - ONLY REAL DATA)
async def fetch_industries():
    """Fetch available industries from API - NO FALLBACKS"""
    print("🔍 Fetching industries from API...")
    url = "https://nischem.com:2053/category/getAllIndustries"
    headers = {
        "Content-Type": "application/json",
        "x-user-type": "Buyer",
        "x-auth-language": "English"
    }
    data = {}
    
    try:
        # Create SSL context
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"🔍 Making PATCH request to: {url}")
            async with session.patch(url, headers=headers, json=data, ssl=False) as response:
                print(f"🔍 Industries API response status: {response.status}")
                
                response_text = await response.text()
                print(f"🔍 Raw industries response: {response_text}")
                
                if response.status in [200, 201]:
                    result = json.loads(response_text)
                    print(f"✅ Industries API Response: {result.get('message', 'Unknown')}")
                    
                    industries_data = []
                    if (result.get("error") == False and 
                        result.get("results", {}).get("inventories")):
                        
                        raw_industries = result["results"]["inventories"]
                        print(f"🔍 Found {len(raw_industries)} raw industries")
                        
                        # Filter: only active and not deleted industries
                        for industry in raw_industries:
                            if (industry.get("status") == True and 
                                industry.get("isDeleted") == False):
                                industries_data.append({
                                    "_id": industry.get("_id"),
                                    "name_en": industry.get("name_en")
                                })
                    
                    print(f"✅ Filtered {len(industries_data)} active REAL industries")
                    return {
                        "industries": industries_data,
                        "count": len(industries_data),
                        "status": "success"
                    }
                else:
                    print(f"❌ Industries API returned status {response.status}")
                    return {
                        "industries": [],
                        "count": 0,
                        "status": "error",
                        "error": f"API returned status {response.status}"
                    }
                    
    except Exception as e:
        print(f"❌ Error fetching industries: {e}")
        return {
            "industries": [],
            "count": 0,
            "status": "error",
            "error": str(e)
        }

async def fetch_user_addresses(session_data: dict):
    """Fetch user addresses using the ACTUAL user token from session - NO FALLBACKS"""
    print("🔍 Fetching user addresses from API...")
    
    # Get the actual user token from session data
    user_auth_token = session_data.get("userAuth")
    if not user_auth_token:
        print("❌ No userAuth token found in session data")
        return {
            "addresses": [],
            "count": 0,
            "status": "error", 
            "error": "No authentication token available"
        }
    
    print(f"🔍 Using userAuth token from session: {user_auth_token[:20]}...")
    
    url = "https://nischem.com:2053/user/getAddresses"
    headers = {
        "x-auth-token-user": user_auth_token,  # Use the actual user token
        "Content-Type": "application/json",
        "x-auth-language": "English",
        "x-user-type": "Buyer"
    }
    data = {}
    
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"🔍 Making PATCH request to: {url}")
            async with session.patch(url, headers=headers, json=data, ssl=False) as response:
                print(f"🔍 Address API response status: {response.status}")
                
                response_text = await response.text()
                print(f"🔍 Raw addresses response: {response_text}")
                
                if response.status in [200, 201]:
                    result = json.loads(response_text)
                    print(f"📡 Addresses API Response: {result.get('message', 'Unknown')}")
                    
                    addresses = []
                    if result.get("error") == False and result.get("results", {}).get("address"):
                        addresses = result["results"]["address"]
                    
                    print(f"📡 Found {len(addresses)} REAL addresses")
                    for addr in addresses:
                        print(f"   - {addr.get('addressLine', 'Unknown')}")
                    return {
                        "addresses": addresses,
                        "count": len(addresses),
                        "status": "success"
                    }
                else:
                    print(f"❌ Address API returned status {response.status}")
                    return {
                        "addresses": [],
                        "count": 0,
                        "status": "error", 
                        "error": f"API returned status {response.status}"
                    }
                
    except Exception as e:
        print(f"❌ Failed to fetch addresses: {e}")
        return {
            "addresses": [],
            "count": 0,
            "status": "error", 
            "error": str(e)
        }

def build_system_prompt(session_data: dict) -> str:
    """Build system prompt for address and purpose collection"""
    request_type = session_data.get("request", "").upper()
    product_name = session_data.get("product_name", "the product")
    
    cached_industries = session_data.get("_cached_industries", [])
    cached_addresses = session_data.get("_cached_addresses", [])
    
    # Show actual available data in prompt
    actual_industries = "\n".join([f"- {ind.get('name_en', 'Unknown')}" for ind in cached_industries[:5]])
    actual_addresses = "\n".join([f"- {addr.get('addressLine', 'Unknown')}" for addr in cached_addresses[:3]])
    
    prompt = f"""You are the **Finalization Agent** for chemical product orders.
you are the third agent in a multi-agent system designed to finalize orders for chemical products.
    
🚨 **CRITICAL RULES - NO HALLUCINATION:**
1. **ONLY USE REAL DATA**: Only show industries/addresses that were successfully fetched from API
2. **NO DUMMY DATA**: Never invent or show placeholder industries or addresses
3. **NO FAKE NAMES**: Never invent names, emails, or phone numbers for addresses
4. **DISPLAY ENTIRE LIST OF INDUSTRIES/ADDRESSES**: Always show the complete list of available industries/addresses from API.
5. Always display clean numbered lists with proper markdown formatting and line breaks but no enlarged heading text.
ACTUAL AVAILABLE DATA FROM API:
- Industries ({len(cached_industries)}): 
{actual_industries}

- Addresses ({len(cached_addresses)}):
{actual_addresses}

WORKFLOW:
1. Auto-show REAL industries (get_cached_industries)
2. User selects industry → store with select_industry
3. Auto-show REAL addresses (get_cached_addresses) 
4. User selects address → store COMPLETE REAL address object with select_address
5. Auto-show final confirmation (show_final_confirmation)
6. Place order when user confirms (place_order_final)
7. After succesful completion, tell the user to refresh the page if he wants to place a new request. Because you cannot do anything more after the order is placed.
ADDRESS SELECTION:
- When user selects address by number, ALWAYS use the complete address object from get_cached_addresses
- NEVER invent contact details - use only what's in the address object from API
- If address object has missing fields, use what's available

PROHIBITED:
- ❌ Never show fake addresses like "123 Business Bay", "Priya Mehta", "Rahul Sharma"
- ❌ Never invent email addresses or phone numbers
- ❌ Never create placeholder addresses
- ❌ Only use data from get_cached_industries and get_cached_addresses
- ❌ You are unable to update any details except industry and address, if user asks to change other details, politely refuse and tell them to refresh the session to start a new order.
- ❌ After an order is placed successfully, you cannot make any more changes or place new orders in the same session.
START by showing ONLY REAL industries immediately."""

    return prompt

def show_final_confirmation(session_data: dict, confirmation_ready: bool):
    """Generate final confirmation summary with all collected data"""
    if not confirmation_ready:
        return {"status": "not_ready", "message": "Address and industry not collected"}
    
    product_details = session_data.get("product_details", {})
    
    # Handle address safely whether it's string or object
    address_data = session_data.get("address", {})
    if isinstance(address_data, str):
        address_display = address_data
        contact_info = "Contact details not available"
    else:
        address_display = address_data.get("addressLine", "N/A")
        # Include contact details if available
        contact_parts = []
        if address_data.get("name"):
            contact_parts.append(f"Name: {address_data.get('name')}")
        if address_data.get("email"):
            contact_parts.append(f"Email: {address_data.get('email')}")
        if address_data.get("phoneNumber"):
            contact_parts.append(f"Phone: +{address_data.get('countryCode', '')} {address_data.get('phoneNumber')}")
        
        contact_info = ", ".join(contact_parts) if contact_parts else "Contact details not specified"
    
    confirmation = {
        "status": "ready",
        "order_summary": {
            "product": {
                "name": session_data.get("product_name", "N/A"),
                "id": session_data.get("product_id", "N/A"),
                "brand": product_details.get("brand_en", "N/A")
            },
            "request_type": session_data.get("request", "N/A"),
            "quantity_details": {
                "quantity": product_details.get("quantity", "N/A"),
                "unit": product_details.get("unit", "N/A"),
                "price_per_unit": product_details.get("price_per_unit", "N/A"),
                "total_price": product_details.get("expected_price", "N/A")
            },
            "delivery": {
                "address": address_display,
                "contact": contact_info,
                "delivery_date": product_details.get("delivery_date", "N/A"),
                "incoterm": product_details.get("incoterm", "N/A")
            },
            "payment": {
                "method": product_details.get("mode_of_payment", "N/A"),
                "contact_phone": product_details.get("phone", "N/A")
            },
            "packaging": product_details.get("packaging_pref", "N/A"),
            "industry_use": session_data.get("industry_name", "N/A")
        },
        "message": "Please review your order details above and confirm if everything is correct."
    }
    
    return confirmation
