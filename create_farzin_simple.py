#!/usr/bin/env python3
"""
Simple script to create a Farzin Test subaccount from Solar
"""

import sys
from GHL.Sub_Accounts.manual_clone import manual_clone_location

# Solar sub-account ID
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"

print("Starting to create Farzin Test subaccount...")

# Create the subaccount
result = manual_clone_location(
    source_location_id=SOLAR_LOCATION_ID,
    new_location_name="Farzin Test",
    new_location_email="farzin.test@theai.team"
)

# Print the result
if result.get("success"):
    print(f"\nSuccess! Created new subaccount:")
    print(f"Location ID: {result.get('new_location_id')}")
    print(f"Name: {result.get('new_location', {}).get('name')}")
    print(f"API Key: {result.get('new_location', {}).get('apiKey')}")
else:
    print(f"\nError: {result.get('error')}")

print("\nScript completed.")
