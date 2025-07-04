import requests
import time
import logging
from typing import Dict, Optional, Any
from GHL.environment.constant import Constant

def clone_sub_account(
    source_location_id: str,
    new_location_name: str,
    new_location_email: str,
    custom_values: Optional[Dict[str, str]] = None,
    plan_id: Optional[str] = None,
    sub_account_type: str = "location",
    access_token: Optional[str] = None,
    wait_time: int = 5
) -> Dict[str, Any]:
    """
    Clone an existing sub-account (Location) into a new one and update custom values.
    
    Args:
        source_location_id (str): The location ID you're cloning from
        new_location_name (str): Name for the new cloned location
        new_location_email (str): Email for the new cloned location
        custom_values (dict, optional): Dictionary of custom values to update {key: value}
        plan_id (str, optional): Plan ID if using SaaS mode
        sub_account_type (str): Type of sub-account ("location" or "SaaS")
        access_token (str, optional): Bearer token for authorization
        wait_time (int): Time to wait between clone and custom value updates
        
    Returns:
        dict: Response containing clone result and custom value update results
        
    Raises:
        requests.exceptions.RequestException: If the API request fails
    """
    
    # Use provided access token or default from constants
    if access_token is None:
        access_token = Constant.Agency_Api_Key
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Prepare clone payload
    clone_payload = {
        "location": {
            "sourceLocationId": source_location_id,
            "name": new_location_name,
            "email": new_location_email
        }
    }
    
    # Add SaaS configuration if specified
    if sub_account_type.lower() == "saas" and plan_id:
        clone_payload["subAccountType"] = "SaaS"
        clone_payload["planId"] = plan_id
    
    try:
        # Step 1: Clone the sub-account
        print(f"Cloning sub-account from {source_location_id}...")
        print(f"Using API endpoint: https://api.gohighlevel.com/v2/locations/clone")
        print(f"Request payload: {clone_payload}")
        print(f"Using authorization header: Bearer {access_token[:10]}...")
        
        clone_response = requests.post(
            "https://api.gohighlevel.com/v2/locations/clone",
            json=clone_payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Response status code: {clone_response.status_code}")
        print(f"Response content: {clone_response.text}")
        
        
        if clone_response.status_code != 200:
            return {
                "success": False,
                "error": "Failed to clone sub-account",
                "status_code": clone_response.status_code,
                "response": clone_response.text
            }
        
        new_location = clone_response.json()
        new_location_id = new_location.get("locationId")
        
        if not new_location_id:
            return {
                "success": False,
                "error": "No location ID returned from clone operation",
                "response": new_location
            }
        
        print(f"✅ Cloned successfully. New location ID: {new_location_id}")
        
        result = {
            "success": True,
            "new_location_id": new_location_id,
            "clone_response": new_location,
            "custom_values_updated": []
        }
        
        # Step 2: Update custom values if provided
        if custom_values:
            print(f"Waiting {wait_time} seconds before updating custom values...")
            time.sleep(wait_time)
            
            custom_value_results = []
            
            for key, value in custom_values.items():
                try:
                    custom_value_payload = {
                        "key": key,
                        "value": value
                    }
                    
                    custom_response = requests.post(
                        f"https://rest.gohighlevel.com/v1/locations/{new_location_id}/customValues",
                        json=custom_value_payload,
                        headers=headers,
                        timeout=30
                    )
                    
                    if custom_response.status_code in [200, 201]:
                        print(f"✅ Updated custom value {key}")
                        custom_value_results.append({
                            "key": key,
                            "value": value,
                            "success": True,
                            "response": custom_response.json()
                        })
                    else:
                        print(f"❌ Failed to update {key}: {custom_response.text}")
                        custom_value_results.append({
                            "key": key,
                            "value": value,
                            "success": False,
                            "error": custom_response.text,
                            "status_code": custom_response.status_code
                        })
                        
                except Exception as e:
                    print(f"❌ Exception updating {key}: {str(e)}")
                    custom_value_results.append({
                        "key": key,
                        "value": value,
                        "success": False,
                        "error": str(e)
                    })
            
            result["custom_values_updated"] = custom_value_results
            result["custom_values_success_count"] = len([r for r in custom_value_results if r["success"]])
            result["custom_values_total_count"] = len(custom_value_results)
        
        return result
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}",
            "exception_type": type(e).__name__
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "exception_type": type(e).__name__
        }


def get_custom_values(location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all custom values for a location.
    
    Args:
        location_id (str): The location ID to get custom values for
        access_token (str, optional): Bearer token for authorization
        
    Returns:
        dict: Response containing custom values
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/locations/{location_id}/customValues",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "custom_values": response.json()
            }
        else:
            return {
                "success": False,
                "error": "Failed to get custom values",
                "status_code": response.status_code,
                "response": response.text
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Error getting custom values: {str(e)}",
            "exception_type": type(e).__name__
        }


# Example usage:
"""
try:
    # Example custom values
    custom_vals = {
        "{{company_name}}": "Cloned Co",
        "{{support_email}}": "support@clonedco.com",
        "{{phone_number}}": "+1-555-0123"
    }
    
    result = clone_sub_account(
        source_location_id="lBPqgBowX1CsjHay12LY",
        new_location_name="Cloned Business Name",
        new_location_email="cloned@email.com",
        custom_values=custom_vals
    )
    
    if result["success"]:
        print(f"Successfully cloned to location ID: {result['new_location_id']}")
        print(f"Custom values updated: {result['custom_values_success_count']}/{result['custom_values_total_count']}")
    else:
        print(f"Clone failed: {result['error']}")
        
except Exception as e:
    print(f"Error: {e}")
"""
