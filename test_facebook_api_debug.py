#!/usr/bin/env python3
"""
Debug script to test Facebook API with stored tokens
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

# Initialize Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)

# Test user
USER_ID = "8f1b1cea-094d-439a-a575-feaffb7f6faf"

def check_stored_tokens():
    """Check what tokens are stored in the database"""
    print("=" * 60)
    print("Checking stored tokens for user:", USER_ID)
    print("=" * 60)
    
    # Get setup data
    result = supabase.table('squidgy_agent_business_setup').select(
        'highlevel_tokens, ghl_location_id, setup_json, created_at, updated_at'
    ).eq('firm_user_id', USER_ID).eq('agent_id', 'SOLAgent').eq('setup_type', 'GHLSetup').single().execute()
    
    if not result.data:
        print("❌ No GHL setup found for this user")
        return
    
    setup_data = result.data
    print(f"\n📅 Created: {setup_data.get('created_at')}")
    print(f"📅 Updated: {setup_data.get('updated_at')}")
    print(f"📍 Location ID: {setup_data.get('ghl_location_id')}")
    
    # Check tokens
    tokens = setup_data.get('highlevel_tokens', {})
    if tokens:
        print("\n📦 Stored Tokens Structure:")
        print(json.dumps(tokens, indent=2))
        
        # Extract specific tokens
        if 'tokens' in tokens:
            token_data = tokens['tokens']
            print("\n🔑 Available Tokens:")
            print(f"  - Firebase Token: {'✅' if token_data.get('firebase_token') else '❌'}")
            print(f"  - PIT Token: {'✅' if token_data.get('private_integration_token') else '❌'}")
            print(f"  - Access Token: {'✅' if token_data.get('access_token') else '❌'}")
            print(f"  - Refresh Token: {'✅' if token_data.get('refresh_token') else '❌'}")
            
            if token_data.get('private_integration_token'):
                print(f"\n🎯 PIT Token: {token_data['private_integration_token']}")
            
            if token_data.get('firebase_token'):
                print(f"\n🔥 Firebase Token (first 50 chars): {token_data['firebase_token'][:50]}...")
    
    # Check setup_json for Facebook data
    setup_json = setup_data.get('setup_json', {})
    if setup_json:
        print("\n📱 Setup JSON contains:")
        if 'facebook_pages' in setup_json:
            pages = setup_json['facebook_pages']
            print(f"  - Facebook Pages: {len(pages)} pages stored")
            for i, page in enumerate(pages[:3]):  # Show first 3
                print(f"    {i+1}. {page}")
        else:
            print("  - No Facebook pages stored")

if __name__ == "__main__":
    check_stored_tokens()