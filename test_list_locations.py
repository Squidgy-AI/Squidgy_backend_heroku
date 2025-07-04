#!/usr/bin/env python3
"""
Test script to list all active locations in GoHighLevel
"""

import requests
import json
from GHL.environment.constant import Constant

def list_locations():
    """List all active locations in GoHighLevel"""
    
    print("\n==== Listing All Active GoHighLevel Locations ====")
    
    # Use the agency API key from constants
    access_token = Constant.Agency_Api_Key
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        print("Sending request to GET https://rest.gohighlevel.com/v1/locations/")
        response = requests.get(
            "https://rest.gohighlevel.com/v1/locations/",
            headers=headers,
            timeout=30
        )
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\nLocations found:")
            
            # Format and print each location
            if "locations" in result:
                for idx, location in enumerate(result["locations"], 1):
                    print(f"\nLocation #{idx}:")
                    print(f"  ID: {location.get('id')}")
                    print(f"  Name: {location.get('name')}")
                    print(f"  Email: {location.get('email')}")
                    print(f"  Status: {location.get('status')}")
                
                print(f"\nTotal locations: {len(result['locations'])}")
            else:
                print("No locations found in the response")
                print("Full response:")
                print(json.dumps(result, indent=2))
        else:
            print("\nError response:")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Starting GoHighLevel locations test...")
    list_locations()
    print("\nTest completed.")
