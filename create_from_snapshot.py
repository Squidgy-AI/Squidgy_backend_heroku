#!/usr/bin/env python3
"""
Create a new Solar sub-account directly from an existing snapshot
This script focuses exclusively on using the snapshot endpoint
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
        logging.FileHandler("create_from_snapshot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def make_api_request(method: str, url: str, headers: Dict, data: Dict = None, 
                   params: Dict = None, timeout: int = 30) -> Tuple[bool, Dict]:
    """Make an API request with detailed logging"""
    try:
        logger.info(f"Making {method} request to {url}")
        if data:
            logger.info(f"Request payload: {json.dumps(data)[:500]}...")
        
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
            logger.info(f"Response content: {json.dumps(response_json)[:500]}...")
        except Exception:
            logger.info(f"Response content (non-JSON): {response.text[:500]}...")
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


def create_location_from_snapshot(snapshot_id: str, location_name: str, company_id: str = None):
    """Create a new location directly from a snapshot"""
    logger.info(f"Creating location '{location_name}' from snapshot {snapshot_id}")
    
    # Use Solar company ID if not provided
    if company_id is None:
        company_id = Constant.Solar_Company_Id
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Define potential endpoints for snapshot-based location creation
    endpoints = [
        # Endpoint 1: Direct snapshot creation endpoint
        {
            "url": "https://services.leadconnectorhq.com/snapshots/create",
            "payload": {
                "snapshotId": snapshot_id,
                "name": location_name,
                "businessName": location_name,
                "companyId": company_id
            },
            "description": "Direct snapshot creation endpoint"
        },
        # Endpoint 2: Alternative creation endpoint
        {
            "url": f"https://services.leadconnectorhq.com/snapshots/{snapshot_id}/create",
            "payload": {
                "name": location_name,
                "businessName": location_name,
                "companyId": company_id
            },
            "description": "Snapshot ID in URL path"
        },
        # Endpoint 3: V2 API endpoint
        {
            "url": "https://api.gohighlevel.com/v2/snapshots/create",
            "payload": {
                "snapshotId": snapshot_id,
                "name": location_name,
                "businessName": location_name,
                "companyId": company_id
            },
            "description": "V2 API endpoint"
        },
        # Endpoint 4: Marketplace API endpoint
        {
            "url": "https://marketplace.gohighlevel.com/api/v1/snapshots/create",
            "payload": {
                "snapshotId": snapshot_id,
                "name": location_name,
                "businessName": location_name,
                "companyId": company_id
            },
            "description": "Marketplace API endpoint"
        },
        # Endpoint 5: Direct snapshot import endpoint
        {
            "url": "https://services.leadconnectorhq.com/snapshots/import",
            "payload": {
                "snapshotId": snapshot_id,
                "name": location_name,
                "businessName": location_name,
                "companyId": company_id
            },
            "description": "Direct snapshot import endpoint"
        }
    ]
    
    # Try each token and endpoint combination
    for token_info in tokens:
        logger.info(f"Trying with {token_info['name']}...")
        
        headers = {
            "Authorization": f"Bearer {token_info['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        for endpoint in endpoints:
            logger.info(f"Trying endpoint: {endpoint['description']}")
            
            success, response = make_api_request(
                "POST",
                endpoint["url"],
                headers,
                endpoint["payload"]
            )
            
            if success:
                location_id = None
                
                # Try to extract location ID from various response formats
                if isinstance(response, dict):
                    location_id = response.get("locationId") or response.get("id")
                    
                    # Check nested structures if needed
                    if not location_id and "location" in response:
                        location_data = response["location"]
                        if isinstance(location_data, dict):
                            location_id = location_data.get("id")
                    
                    # Check data field if present
                    if not location_id and "data" in response:
                        data = response["data"]
                        if isinstance(data, dict):
                            location_id = data.get("locationId") or data.get("id")
                
                if location_id:
                    logger.info(f"✅ Successfully created location with ID: {location_id}")
                    return {
                        "success": True,
                        "location_id": location_id,
                        "location_name": location_name,
                        "token_used": token_info["name"],
                        "endpoint_used": endpoint["description"],
                        "response": response
                    }
                else:
                    logger.warning("Received success response but couldn't extract location ID")
            
            # Add a small delay between requests to avoid rate limiting
            import time
            time.sleep(1)
    
    logger.error("All creation attempts failed")
    return {
        "success": False,
        "error": "All creation attempts failed",
        "snapshot_id": snapshot_id,
        "location_name": location_name
    }


def main():
    """Main function to create a new location from a snapshot"""
    print("🚀 GoHighLevel Create from Snapshot")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Specific snapshot ID to use
    snapshot_id = "7oAH6Cmto5ZcWAaEsrrq"
    
    # Target location name
    location_name = f"Solar Snapshot {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n📸 Snapshot ID: {snapshot_id}")
    print(f"🏢 Target Name: {location_name}")
    print("=" * 50)
    
    # Execute the creation process
    result = create_location_from_snapshot(snapshot_id, location_name)
    
    print("\n📊 Creation Results:")
    print("=" * 30)
    print(f"Success: {'✅' if result['success'] else '❌'}")
    
    if result['success']:
        print(f"New Location ID: {result['location_id']}")
        print(f"Location Name: {result['location_name']}")
        print(f"Token Used: {result['token_used']}")
        print(f"Endpoint Used: {result['endpoint_used']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    return result['success']


def create_fastapi_endpoint():
    """Generate code for a FastAPI endpoint to create locations from snapshots"""
    code = '''
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional

from GHL.environment.constant import Constant
from .create_from_snapshot import create_location_from_snapshot

router = APIRouter()

class SnapshotCreateRequest(BaseModel):
    snapshot_id: str
    location_name: str
    company_id: Optional[str] = None

class SnapshotCreateResponse(BaseModel):
    success: bool
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    error: Optional[str] = None

@router.post("/api/ghl/create-from-snapshot", response_model=SnapshotCreateResponse)
async def create_from_snapshot(request: SnapshotCreateRequest):
    """Create a new location from an existing snapshot"""
    try:
        result = create_location_from_snapshot(
            snapshot_id=request.snapshot_id,
            location_name=request.location_name,
            company_id=request.company_id or Constant.Solar_Company_Id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create location from snapshot"))
        
        return SnapshotCreateResponse(
            success=True,
            location_id=result["location_id"],
            location_name=result["location_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
'''
    return code


if __name__ == "__main__":
    main()
