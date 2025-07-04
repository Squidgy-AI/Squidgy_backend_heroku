#!/usr/bin/env python3
"""
Test script to list all agency locations in GoHighLevel
"""

import requests
import json
from colorama import init, Fore, Style
from GHL.environment.constant import Constant

# Initialize colorama
init(autoreset=True)

def print_colored(message, color=Fore.WHITE, style=Style.NORMAL):
    """Print colored text"""
    print(f"{style}{color}{message}")

def print_header(message):
    """Print a header"""
    print("\n" + "=" * 40)
    print_colored(message, Fore.CYAN, Style.BRIGHT)
    print("=" * 40)

def print_success(message):
    """Print a success message"""
    print_colored(f"✓ {message}", Fore.GREEN, Style.BRIGHT)

def print_error(message):
    """Print an error message"""
    print_colored(f"✗ {message}", Fore.RED, Style.BRIGHT)

def print_info(message):
    """Print an info message"""
    print_colored(f"ℹ {message}", Fore.BLUE)

def list_agency_locations(access_token=None):
    """List all agency locations"""
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        print_info("Fetching all agency locations...")
        response = requests.get(
            "https://rest.gohighlevel.com/v1/locations/",
            headers=headers,
            timeout=30
        )
        
        print_info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            locations = response.json().get("locations", [])
            print_success(f"Found {len(locations)} locations")
            
            print_header("Agency Locations")
            for idx, location in enumerate(locations, 1):
                print_colored(f"Location #{idx}", Fore.MAGENTA, Style.BRIGHT)
                print_info(f"ID: {location.get('id')}")
                print_info(f"Name: {location.get('name')}")
                print_info(f"Email: {location.get('email')}")
                print_info(f"Business Name: {location.get('businessName', 'N/A')}")
                print_info(f"Status: {location.get('status', 'N/A')}")
                print()
                
            # Check if solar sub-account is in the list
            solar_id = "JUTFTny8EXQOSB5NcvAA"  # The ID you've been using
            solar_location = next((loc for loc in locations if loc.get('id') == solar_id), None)
            
            if solar_location:
                print_success(f"✓ Solar sub-account (ID: {solar_id}) is accessible")
                print_info(f"Solar sub-account name: {solar_location.get('name')}")
            else:
                print_error(f"✗ Solar sub-account (ID: {solar_id}) was not found in the list")
                
            return {
                "success": True,
                "locations": locations
            }
        else:
            print_error("Failed to get locations")
            print_error(f"Response: {response.text}")
            return {
                "success": False,
                "error": "Failed to get locations",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return {
            "success": False,
            "error": f"Error getting locations: {str(e)}",
            "exception_type": type(e).__name__
        }

def main():
    """Main function"""
    print_colored("Starting GoHighLevel Agency Locations Test...", Fore.MAGENTA, Style.BRIGHT)
    
    result = list_agency_locations()
    
    if result.get("success"):
        print_success("Successfully retrieved agency locations")
    else:
        print_error("Failed to retrieve agency locations")
        
    print_colored("\nTest completed.", Fore.MAGENTA, Style.BRIGHT)

if __name__ == "__main__":
    main()
