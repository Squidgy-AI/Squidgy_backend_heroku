#!/usr/bin/env python3
"""
Test the Facebook pages API endpoint
"""
import requests
import json
from datetime import datetime

# API endpoint
url = "http://localhost:8000/api/facebook/get-pages"

# Test payload
payload = {
    "location_id": "GJSb0aPcrBRne73LK3A3",
    "user_id": "ExLH8YJG8qfhdmeZTzMX",
    "email": "somashekhar34@gmail.com",
    "password": "Dummy@123",
    "firm_user_id": "test_firm_user_" + datetime.now().strftime("%Y%m%d_%H%M%S")
}

print("🚀 Testing Facebook Pages API Endpoint")
print("=" * 80)
print(f"📍 URL: {url}")
print(f"📦 Payload: {json.dumps(payload, indent=2)}")
print("=" * 80)

try:
    print("\n⏳ Sending request to API...")
    response = requests.post(url, json=payload, timeout=120)
    
    print(f"\n📡 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Success: {result.get('success', False)}")
        
        if result.get('success'):
            print(f"\n📱 Pages Found: {result.get('total_pages', 0)}")
            
            pages = result.get('pages', [])
            if pages:
                print("\n📋 Pages List:")
                for idx, page in enumerate(pages, 1):
                    print(f"\n   Page #{idx}:")
                    print(f"   - Name: {page.get('page_name', 'N/A')}")
                    print(f"   - ID: {page.get('page_id', 'N/A')}")
                    print(f"   - Instagram: {page.get('instagram_available', False)}")
                    print(f"   - Connected: {page.get('is_connected', False)}")
            
            if result.get('jwt_token_captured'):
                print(f"\n🔑 JWT Token: Captured successfully")
            
            print(f"\n💾 Database Save: {'Success' if result.get('database_saved') else 'Failed'}")
        else:
            print(f"\n❌ Error: {result.get('message', 'Unknown error')}")
            if result.get('manual_mode'):
                print("\n⚠️ Manual mode required - browser automation was detected")
    else:
        print(f"\n❌ HTTP Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("\n⏰ Request timed out after 120 seconds")
except requests.exceptions.ConnectionError:
    print("\n❌ Connection Error: Could not connect to the API")
    print("   Make sure the backend server is running on http://localhost:8000")
except Exception as e:
    print(f"\n💥 Unexpected Error: {type(e).__name__}: {str(e)}")