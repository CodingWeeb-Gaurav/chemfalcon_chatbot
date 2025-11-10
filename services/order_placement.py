# services/order_placement.py
import asyncio
import json
import aiohttp
import ssl
import certifi


async def place_order_request(session_data: dict):
    """
    Main backend function to place orders or PPR requests.
    Automatically detects when request == "ppr"
    """
    print("🚀 Processing order request...")

    # Extract auth token
    user_auth_token = session_data.get("userAuth")
    if not user_auth_token:
        return {
            "status": "error",
            "error_type": "AUTH_ERROR",
            "message": "No authentication token provided"
        }

    print(f"🔑 Using userAuth token: {user_auth_token[:15]}...")

    request_type = session_data.get("request", "").lower()

    # ✅ If PPR → process with JSON API
    if request_type == "ppr":
        return await _process_ppr(session_data, user_auth_token)

    # ✅ Otherwise → normal order
    return await _process_normal_order(session_data, user_auth_token)



# ----------------------------------------------------------------------
# ✅ PPR ORDER HANDLER
# ----------------------------------------------------------------------
async def _process_ppr(session_data: dict, user_auth_token: str):
    """
    Handles PPR requests EXACTLY like the curl reference
    """
    print("📌 Request type = PPR → Using createRequirement API")

    product_details = session_data.get("product_details", {})
    address_data = session_data.get("address", {})

    # ❌ NO PLACEHOLDER: Strict validation
    if not isinstance(address_data, dict):
        return {
            "status": "error",
            "error_type": "ADDRESS_ERROR",
            "message": "Address data is corrupted. Please restart the order process."
        }

    address_id = address_data.get("_id")
    if not address_id or address_id == "unknown":
        return {
            "status": "error", 
            "error_type": "ADDRESS_ERROR",
            "message": "Valid address ID not found. Please select a valid address."
        }

    # Validate required fields for PPR
    required_fields = ["product_id", "quantity", "unit", "delivery_date"]
    for field in required_fields:
        if field == "product_id" and not session_data.get("product_id"):
            return {
                "status": "error",
                "error_type": "DATA_ERROR", 
                "message": "Product information missing. Please restart the order process."
            }
        elif field in ["quantity", "unit", "delivery_date"] and not product_details.get(field):
            return {
                "status": "error",
                "error_type": "DATA_ERROR",
                "message": f"Required field '{field}' is missing. Please restart the order process."
            }

    # ✅ JSON payload EXACT as required
    payload = {
        "product": session_data.get("product_id"),
        "expectedPrice": product_details.get("expected_price", 0),
        "address": address_id,
        "quantity": product_details.get("quantity"),
        "quantityType": product_details.get("unit"),
        "endDate": product_details.get("delivery_date")
    }

    print("📦 PPR JSON Payload:")
    print(json.dumps(payload, indent=2))

    url = "https://chemfalcon.com:2053/order/createRequirement"
    headers = {
        "Content-Type": "application/json",
        "x-auth-token-user": user_auth_token,
        "x-user-type": "Buyer"
    }

    # ✅ Send JSON request
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"🌐 Sending PPR request → {url}")
            async with session.post(url, headers=headers, json=payload, ssl=False) as response:
                response_text = await response.text()

                print(f"🔍 PPR Response Status: {response.status}")
                print(f"🔍 PPR Response Body: {response_text}")

                try:
                    result = json.loads(response_text)
                except:
                    return {
                        "status": "error",
                        "error_type": "PARSING_ERROR",
                        "message": "Invalid JSON returned from PPR API"
                    }

                if response.status in (200, 201) and result.get("error") == False:
                    return {
                        "status": "success",
                        "message": result.get("message", "Requirement created successfully"),
                        "data": result.get("results", {}).get("requirement"),
                        "requirement_id": result.get("results", {}).get("requirement", {}).get("_id")
                    }

                return {
                    "status": "error",
                    "error_type": "API_ERROR",
                    "message": result.get("message", "Unknown error"),
                    "status_code": response.status
                }

    except Exception as e:
        print(f"❌ Unexpected PPR error: {e}")
        return {
            "status": "error",
            "error_type": "UNKNOWN_ERROR",
            "message": f"Unexpected error: {str(e)}"
        }



# ----------------------------------------------------------------------
# ✅ NORMAL ORDER HANDLER (placeOrder)
# ----------------------------------------------------------------------
async def _process_normal_order(session_data: dict, user_auth_token: str):
    """
    Processes normal order placement using multipart/form-data
    EXACTLY matching backend expectations.
    """
    print("📌 Request type = Normal Order → Using placeOrder API")

    product_details = session_data.get("product_details", {})
    address_data = session_data.get("address", {})

    # ✅ Build FormData
    form_data = aiohttp.FormData()

    # ✅ Add address without stringifying
    for key, value in address_data.items():
        if key == "_id":
            continue
        if value not in (None, "", []):
            form_data.add_field(f"address[{key}]", str(value))

    # ✅ Standard required fields
    form_data.add_field("product", session_data.get("product_id", ""))
    form_data.add_field("quantity", str(product_details.get("quantity", "")))
    form_data.add_field("expectedAmount", str(product_details.get("expected_price", "")))
    form_data.add_field("quantityType", product_details.get("unit", ""))
    form_data.add_field("type", session_data.get("request", "").capitalize())

    # ✅ Sample order flag
    if session_data.get("request", "").lower() == "sample":
        form_data.add_field("isSampleOrder", "TRUE")

    # ✅ Optional fields
    if session_data.get("industry_id"):
        form_data.add_field("industry", session_data["industry_id"])

    if product_details.get("incoterm"):
        form_data.add_field("incoterm", product_details["incoterm"])

    if product_details.get("mode_of_payment"):
        form_data.add_field("modeOfPayment", product_details["mode_of_payment"])

    if product_details.get("packaging_pref"):
        form_data.add_field("packingType", product_details["packaging_pref"])

    if product_details.get("delivery_date"):
        form_data.add_field("expectedPurchaseDate", product_details["delivery_date"])

    if product_details.get("phone"):
        form_data.add_field("shippingContactNumber", product_details["phone"])

    # ✅ API endpoint
    url = "https://chemfalcon.com:2053/order/placeOrder"
    headers = {
        "x-auth-token-user": user_auth_token,
        "x-user-type": "Buyer"
    }

    # ✅ Send POST request
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"🌐 Sending normal order → {url}")
            async with session.post(url, headers=headers, data=form_data, ssl=False) as response:
                response_text = await response.text()

                print(f"🔍 Order Response Status: {response.status}")
                print(f"🔍 Order Response Body: {response_text}")

                try:
                    result = json.loads(response_text)
                except:
                    return {
                        "status": "error",
                        "error_type": "PARSING_ERROR",
                        "message": "Invalid JSON from server"
                    }

                if response.status in (200, 201) and result.get("error") == False:
                    return {
                        "status": "success",
                        "message": result.get("message", "Order placed successfully!"),
                        "data": result.get("results", {}).get("order"),
                        "order_id": result.get("results", {}).get("order", {}).get("_id")
                    }

                return {
                    "status": "error",
                    "error_type": "API_ERROR",
                    "message": result.get("message", "Unknown error"),
                    "status_code": response.status
                }

    except Exception as e:
        print(f"❌ Unexpected normal order error: {e}")
        return {
            "status": "error",
            "error_type": "UNKNOWN_ERROR",
            "message": f"Unexpected error: {str(e)}"
        }
