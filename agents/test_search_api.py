import requests
import json

def test_chatbot():
    url = ""
    
    payload = {
        "sessionId": "test-session-123",
        "userAuth": "test-user", 
        "message": "i want sulphuric acid"
    }
    
    try:
        response = requests.post(url, json=payload)
        print("Status:", response.status_code)
        print("Response:", response.json())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_chatbot()