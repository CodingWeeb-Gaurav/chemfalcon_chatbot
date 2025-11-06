# services/order_placement.py
import asyncio
import json
import aiohttp
import ssl
import certifi

async def place_order_request(session_data: dict):
    """
    Backend function to place the order - COMPLIANT with API structure
    """
    print("🚀 Placing order request...")
    
    # Get the actual user token from session data
    user_auth_token = session_data.get("userAuth")
    if not user_auth_token:
        print("❌ No userAuth token found in session data")
        return {
            "status": "error",
            "error_type": "AUTH_ERROR",
            "message": "No authentication token available"
        }
    
    print(f"🔍 Using userAuth token from session: {user_auth_token[:20]}...")
    
    # Extract data from session
    product_details = session_data.get("product_details", {})
    address_data = session_data.get("address", {})
    
    # 🔥 FIX: Proper industry ID resolution
    industry_id = session_data.get("industry_id")
    industry_name = session_data.get("industry_name")
    cached_industries = session_data.get("_cached_industries", [])
    
    print(f"🔍 Industry resolution - ID: {industry_id}, Name: {industry_name}")
    
    # Resolve industry ID properly
    resolved_industry_id = None
    if industry_id:
        # Check if it's already a valid MongoDB ID (24 char hex)
        if isinstance(industry_id, str) and len(industry_id) == 24 and all(c in '0123456789abcdef' for c in industry_id.lower()):
            resolved_industry_id = industry_id
            print(f"✅ Using valid MongoDB industry ID: {resolved_industry_id}")
        else:
            # Try to find by name in cached industries
            for industry in cached_industries:
                if (industry.get("name_en") == industry_name or 
                    str(industry.get("_id")) == str(industry_id)):
                    resolved_industry_id = industry.get("_id")
                    print(f"🔄 Resolved industry: {industry_name} -> {resolved_industry_id}")
                    break
    
    # 🔥 FIX: Prepare address EXACTLY as required by API
    if isinstance(address_data, str):
        # If address is just a string, create minimal object
        simplified_address = {
            "addressLine": address_data,
            "email": "",
            "name": "",
            "phoneNumber": "",
            "countryCode": "",
            "latitude": "",
            "longitude": ""
        }
    else:
        # Use the complete address object from API
        simplified_address = {
            "email": address_data.get("email", ""),
            "name": address_data.get("name", ""),
            "phoneNumber": address_data.get("phoneNumber", ""),
            "countryCode": address_data.get("countryCode", ""),
            "addressLine": address_data.get("addressLine", ""),
            "latitude": str(address_data.get("latitude", "")),
            "longitude": str(address_data.get("longitude", ""))
        }
    
    print(f"📦 Using address: {simplified_address.get('addressLine')}")
    print(f"📦 Address ID: {address_data.get('_id', 'N/A')}")
    print(f"📦 Using industry ID: {resolved_industry_id}")
    
    # 🔥 FIX: Prepare FormData EXACTLY like curl command
    form_data = aiohttp.FormData()
    
    # Required fields (must be in this order for compatibility)
    form_data.add_field('address', json.dumps(simplified_address))
    form_data.add_field('product', session_data.get("product_id", ""))
    form_data.add_field('quantity', str(product_details.get("quantity", "")))
    form_data.add_field('expectedAmount', str(product_details.get("expected_price", "")))
    form_data.add_field('quantityType', product_details.get("unit", ""))
    
    # Request type handling
    request_type = session_data.get("request", "").capitalize()
    form_data.add_field('type', request_type)
    
    # Sample order handling
    if session_data.get("request", "").lower() == "sample":
        form_data.add_field('isSampleOrder', 'TRUE')  # Must be uppercase TRUE
    
    # Optional fields (only add if they have values)
    if resolved_industry_id:
        form_data.add_field('industry', resolved_industry_id)
    
    if product_details.get("incoterm"):
        form_data.add_field('incoterm', product_details.get("incoterm"))
    
    if product_details.get("mode_of_payment"):
        form_data.add_field('modeOfPayment', product_details.get("mode_of_payment"))
    
    if product_details.get("packaging_pref"):
        form_data.add_field('packingType', product_details.get("packaging_pref"))
    
    if product_details.get("delivery_date"):
        form_data.add_field('expectedPurchaseDate', product_details.get("delivery_date"))
    
    if product_details.get("phone"):
        form_data.add_field('shippingContactNumber', product_details.get("phone"))
    
    # Debug: Print all form fields for verification
    print("📋 FormData fields being sent:")
    print(f"   - address: {json.dumps(simplified_address)}")
    print(f"   - product: {session_data.get('product_id')}")
    print(f"   - quantity: {product_details.get('quantity')}")
    print(f"   - expectedAmount: {product_details.get('expected_price')}")
    print(f"   - quantityType: {product_details.get('unit')}")
    print(f"   - type: {request_type}")
    print(f"   - isSampleOrder: {'TRUE' if session_data.get('request', '').lower() == 'sample' else 'NOT SET'}")
    print(f"   - industry: {resolved_industry_id}")
    print(f"   - incoterm: {product_details.get('incoterm', 'NOT SET')}")
    print(f"   - modeOfPayment: {product_details.get('mode_of_payment', 'NOT SET')}")
    print(f"   - packingType: {product_details.get('packaging_pref', 'NOT SET')}")
    print(f"   - expectedPurchaseDate: {product_details.get('delivery_date', 'NOT SET')}")
    print(f"   - shippingContactNumber: {product_details.get('phone', 'NOT SET')}")
    
    # API endpoint
    url = "https://chemfalcon.com:2053/order/placeOrder"
    headers = {
        "x-auth-token-user": user_auth_token,  # Use the actual user token from session
        "x-user-type": "Buyer"
        # Note: Don't set Content-Type - aiohttp will set it automatically for FormData
    }
    
    try:
        # Create SSL context
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"🔍 Making POST request to: {url}")
            async with session.post(url, headers=headers, data=form_data, ssl=False) as response:
                response_text = await response.text()
                print(f"🔍 Order API response status: {response.status}")
                print(f"🔍 Raw response: {response_text}")
                
                # Handle successful responses
                if response.status in [200, 201]:
                    try:
                        result = json.loads(response_text)
                        print(f"✅ Order API success: {result.get('message')}")
                        
                        if result.get("error") == False:
                            return {
                                "status": "success",
                                "message": result.get("message", "Order placed successfully!"),
                                "data": result.get("results", {}).get("order"),
                                "order_id": result.get("results", {}).get("order", {}).get("_id")
                            }
                        else:
                            error_msg = result.get("message", "Unknown API error")
                            print(f"❌ API returned error: {error_msg}")
                            return {
                                "status": "error",
                                "error_type": "API_ERROR",
                                "message": error_msg,
                                "status_code": response.status
                            }
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON parse error: {e}")
                        return {
                            "status": "error",
                            "error_type": "PARSING_ERROR",
                            "message": "Invalid response from server",
                            "status_code": response.status
                        }
                
                # Handle 206 Partial Content as success (based on your API behavior)
                elif response.status == 206:
                    try:
                        result = json.loads(response_text)
                        if result.get("error") == False:
                            return {
                                "status": "success", 
                                "message": result.get("message", "Order processed successfully!"),
                                "data": result.get("results", {}).get("order"),
                                "order_id": result.get("results", {}).get("order", {}).get("_id")
                            }
                        else:
                            return {
                                "status": "error",
                                "error_type": "PARTIAL_ERROR",
                                "message": result.get("message", "Order partially processed"),
                                "status_code": response.status
                            }
                    except:
                        return {
                            "status": "success",
                            "message": "Order processed successfully (206)",
                            "status_code": response.status
                        }
                
                else:
                    # Handle other error codes
                    error_mapping = {
                        400: ("BAD_REQUEST", "Invalid request data"),
                        401: ("UNAUTHORIZED", "Authentication required"),
                        403: ("FORBIDDEN", "Access forbidden"),
                        404: ("NOT_FOUND", "API endpoint not found"),
                        500: ("SERVER_ERROR", "Server error occurred"),
                    }
                    
                    error_info = error_mapping.get(response.status, ("UNKNOWN_ERROR", f"HTTP {response.status}"))
                    
                    return {
                        "status": "error",
                        "error_type": error_info[0],
                        "message": error_info[1],
                        "status_code": response.status
                    }
                    
    except asyncio.TimeoutError:
        return {
            "status": "error", 
            "error_type": "TIMEOUT_ERROR",
            "message": "Request timeout"
        }
    except aiohttp.ClientConnectionError:
        return {
            "status": "error",
            "error_type": "CONNECTION_ERROR",
            "message": "Network connection failed"
        }
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "error_type": "UNKNOWN_ERROR",
            "message": f"Unexpected error: {str(e)}"
        }