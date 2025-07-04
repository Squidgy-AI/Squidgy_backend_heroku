#!/usr/bin/env python3
"""
Simple test to clone a single workflow from Solar sub-account to an existing location.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant


def test_workflow_clone_to_existing_location():
    """Test cloning a workflow to an existing location"""
    
    # Configuration
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    TARGET_WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"  # "Set Last Communication Type"
    
    # Use an existing test location (you can replace this with any existing location ID)
    TARGET_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"  # For now, try to clone within same location
    
    SOLAR_TOKEN = Constant.Solar_Access_Token
    AGENCY_API_KEY = Constant.Agency_Api_Key
    
    print("🔄 Simple Workflow Clone Test")
    print("============================")
    print(f"Source Location: {SOLAR_LOCATION_ID}")
    print(f"Target Location: {TARGET_LOCATION_ID}")
    print(f"Workflow ID: {TARGET_WORKFLOW_ID}")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    
    # Step 1: Get workflow details
    print(f"\n🔍 Getting workflow details...")
    workflow_details = get_workflow_details(TARGET_WORKFLOW_ID, SOLAR_TOKEN)
    
    if workflow_details.get("success"):
        workflow_data = workflow_details.get("workflow_data", {})
        print(f"✅ Workflow found: {workflow_data.get('name', 'Unknown')}")
    else:
        print(f"❌ Failed to get workflow: {workflow_details.get('error')}")
        return False
    
    # Step 2: Try to clone the workflow
    print(f"\n🚀 Attempting workflow clone...")
    success = attempt_workflow_clone(
        source_workflow_id=TARGET_WORKFLOW_ID,
        target_location_id=TARGET_LOCATION_ID,
        workflow_data=workflow_data,
        solar_token=SOLAR_TOKEN
    )
    
    print(f"\n📊 RESULT: {'✅ SUCCESS' if success else '❌ FAILED'}")
    return success


def get_workflow_details(workflow_id: str, access_token: str):
    """Get workflow details using correct GoHighLevel API endpoints"""
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # Use the correct API endpoints based on the URL structure you provided
    endpoints = [
        f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://services.leadconnectorhq.com/workflows/{workflow_id}",
        f"https://rest.gohighlevel.com/v1/locations/JUTFTny8EXQOSB5NcvAA/workflows/{workflow_id}"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"   Trying: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=15)
            
            if response.status_code == 200:
                print(f"   ✅ Success!")
                return {
                    "success": True,
                    "workflow_data": response.json()
                }
            else:
                print(f"   ❌ {response.status_code}: {response.text[:50]}...")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    return {"success": False, "error": "No endpoint worked"}


def attempt_workflow_clone(source_workflow_id: str, target_location_id: str, workflow_data: dict, solar_token: str):
    """Try to clone workflow using correct GoHighLevel API endpoints"""
    
    headers = {
        "Authorization": f"Bearer {solar_token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # Use correct API endpoints based on GoHighLevel documentation
    test_cases = [
        {
            "url": f"https://rest.gohighlevel.com/v1/workflows/{source_workflow_id}/duplicate",
            "payload": {
                "locationId": target_location_id,
                "name": f"CLONED - {workflow_data.get('name', 'Workflow')}"
            }
        },
        {
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_data.get('name', 'Workflow')}",
                "locationId": target_location_id,
                "status": "draft",
                "sourceWorkflowId": source_workflow_id
            }
        },
        {
            "url": f"https://services.leadconnectorhq.com/workflows/{source_workflow_id}/duplicate",
            "payload": {
                "targetLocationId": target_location_id,
                "name": f"CLONED - {workflow_data.get('name', 'Workflow')}"
            }
        },
        {
            "url": "https://services.leadconnectorhq.com/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_data.get('name', 'Workflow')}",
                "locationId": target_location_id,
                "templateId": source_workflow_id
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"   Test {i}: {test_case['url']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=2)}")
        
        try:
            response = requests.post(
                test_case['url'],
                headers=headers,
                json=test_case['payload'],
                timeout=15
            )
            
            print(f"   Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print(f"   ✅ SUCCESS! {response.text[:100]}...")
                return True
            else:
                print(f"   ❌ Failed: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
        
        print()  # Empty line for readability
    
    return False


if __name__ == "__main__":
    print("🚀 Starting Simple Workflow Clone Test")
    print("=" * 50)
    
    success = test_workflow_clone_to_existing_location()
    
    print(f"\n🏁 Test completed: {'🎉 SUCCESS' if success else '⚠️ FAILED'}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
