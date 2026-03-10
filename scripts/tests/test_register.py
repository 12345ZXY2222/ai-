import requests
import sys

try:
    print("Sending registration request...")
    response = requests.post(
        "http://localhost:8001/api/register",
        json={"username": "debug_user_3", "password": "password123"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
