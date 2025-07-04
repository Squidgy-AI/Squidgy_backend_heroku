#!/usr/bin/env python3
"""
Script to import a specific GoHighLevel snapshot to a target location
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("import_snapshot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def make_api_request(method: str, url: str, headers: Dict, data: Dict = None, 
                   params: Dict = None, timeout: int = 30) -> Tuple[bool, Dict]:
    """Make an API request with rate limiting and error handling"""
    try:
        logger.info(f"Making {method} request to {url}")
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data, params=params, timeout=timeout)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data, params=params, timeout=timeout)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, params=params, timeout=timeout)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return False, {"error": f"Unsupported HTTP method: {method}"}
        
        # Log the response status and content
        logger.info(f"Response status: {response.status_code}")
        
        try:
            response_json = response.json()
            logger.debug(f"Response content: {json.dumps(response_json)[:500]}...")
        except Exception:
            logger.debug(f"Response content (non-JSON): {response.text[:500]}...")
            response_json = {"text": response.text}
        
        # Check if the request was successful
        if response.status_code in [200, 201, 202]:
            return True, response_json
        else:
            logger.error(f"API request failed with status {response.status_code}: {response.text[:200]}")
            return False, response_json
            
    except Exception as e:
        logger.error(f"Exception during API request: {str(e)}")
        return False, {"error": str(e)}


def import_specific_snapshot(snapshot_id: str, target_location_id: str, company_id: str = None):
    """Import a specific snapshot to a target location"""
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Get Solar company ID if not provided
    if company_id is None:
        company_id = Constant.Solar_Company_Id
    
    for token_info in tokens:
        print(f"\n📥 Trying to import snapshot with {token_info['name']}...")
        
        headers = {
            "Authorization": f"Bearer {token_info['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Try different payloads and endpoints
        endpoints = [
            # Endpoint 1: Standard endpoint with locationId
            {
                "url": "https://services.leadconnectorhq.com/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "locationId": target_location_id
                },
                "description": "Using locationId in payload"
            },
            # Endpoint 2: Standard endpoint with both companyId and locationId
            {
                "url": "https://services.leadconnectorhq.com/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "companyId": company_id,
                    "locationId": target_location_id
                },
                "description": "Using both companyId and locationId in payload"
            },
            # Endpoint 3: V2 API endpoint
            {
                "url": "https://api.gohighlevel.com/v2/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "locationId": target_location_id
                },
                "description": "Using v2 API endpoint"
            },
            # Endpoint 4: Alternative endpoint
            {
                "url": f"https://services.leadconnectorhq.com/snapshots/{snapshot_id}/import",
                "payload": {
                    "locationId": target_location_id
                },
                "description": "Using snapshot ID in URL"
            }
        ]
        
        for endpoint in endpoints:
            print(f"   🔍 Trying endpoint: {endpoint['description']}")
            
            success, response = make_api_request(
                "POST",
                endpoint["url"],
                headers,
                endpoint["payload"]
            )
            
            if success:
                print(f"      ✅ Success! Response: {json.dumps(response)[:100]}...")
                return {
                    "success": True,
                    "response": response,
                    "token_used": token_info["name"],
                    "endpoint_used": endpoint["description"]
                }
            else:
                print(f"      ❌ Failed: {json.dumps(response)[:100]}...")
    
    return {
        "success": False,
        "error": "All import attempts failed"
    }


def create_target_location(name: str):
    """Create a new target location"""
    headers = {
        "Authorization": f"Bearer {Constant.Agency_Api_Key}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    payload = {
        "name": name,
        "businessName": name,  # Adding businessName as required by the API
        "country": "US",
        "timezone": "America/New_York"
    }
    
    success, response = make_api_request(
        "POST",
        "https://rest.gohighlevel.com/v1/locations/",
        headers,
        payload
    )
    
    if success and "id" in response:
        return {
            "success": True,
            "location_id": response["id"],
            "response": response
        }
    else:
        return {
            "success": False,
            "error": "Failed to create target location",
            "response": response
        }


def main():
    """Main function to import a specific snapshot"""
    print("🚀 GoHighLevel Specific Snapshot Import")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Specific snapshot ID to import
    snapshot_id = "7oAH6Cmto5ZcWAaEsrrq"
    
    # Step 1: Create a new target location
    target_name = f"Snapshot Import {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n🏢 Step 1: Creating target location '{target_name}'...")
    
    location_result = create_target_location(target_name)
    
    if not location_result["success"]:
        print(f"❌ Failed to create target location: {location_result.get('error', 'Unknown error')}")
        return False
    
    target_location_id = location_result["location_id"]
    print(f"✅ Target location created with ID: {target_location_id}")
    
    # Step 2: Import the specific snapshot
    print(f"\n📥 Step 2: Importing snapshot {snapshot_id} to target location...")
    
    import_result = import_specific_snapshot(snapshot_id, target_location_id)
    
    if import_result["success"]:
        print(f"\n✅ Successfully imported snapshot!")
        print(f"Token used: {import_result['token_used']}")
        print(f"Endpoint used: {import_result['endpoint_used']}")
        print(f"\nThe snapshot has been imported to location: {target_location_id}")
        print(f"Location name: {target_name}")
        return True
    else:
        print(f"\n❌ Failed to import snapshot: {import_result.get('error', 'Unknown error')}")
        return False


if __name__ == "__main__":
    main()
