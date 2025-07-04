#!/usr/bin/env python3
"""
Test script for getting custom values from a GoHighLevel location
"""

import json
from GHL.Sub_Accounts.clone_sub_acc import get_custom_values

def test_get_custom_values():
    """Test the get_custom_values function directly"""
    
    print("\n==== Testing get_custom_values Function ====")
    
    # Call the function directly
    result = get_custom_values(
        location_id="JUTFTny8EXQOSB5NcvAA"
    )
    
    # Print the result
    print("\nFunction Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    print("Starting test of get_custom_values function...")
    test_get_custom_values()
    print("\nTest completed.")
