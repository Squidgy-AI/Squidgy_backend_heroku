#!/usr/bin/env python3
"""
Test to list all workflows from Solar sub-account to understand the correct API structure.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant


def test_workflow_endpoints():
    """Test different endpoints to list workflows"""
    
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    SOLAR_TOKEN = Constant.Solar_Access_Token
    AGENCY_API_KEY = Constant.Agency_Api_Key
    
    print("🔍 Testing Workflow Listing Endpoints")
    print("=" * 50)
    print(f"Solar Location ID: {SOLAR_LOCATION_ID}")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    
    # Test different token types and endpoints
    test_cases = [
        {
            "name": "Solar Token - v1 workflows",
            "token": SOLAR_TOKEN,
            "url": "https://rest.gohighlevel.com/v1/workflows",
            "params": None
        },
        {
            "name": "Solar Token - v1 workflows with locationId",
            "token": SOLAR_TOKEN,
            "url": "https://rest.gohighlevel.com/v1/workflows",
            "params": {"locationId": SOLAR_LOCATION_ID}
        },
        {
            "name": "Agency Token - v1 workflows",
            "token": AGENCY_API_KEY,
            "url": "https://rest.gohighlevel.com/v1/workflows",
            "params": None
        },
        {
            "name": "Agency Token - v1 workflows with locationId",
            "token": AGENCY_API_KEY,
            "url": "https://rest.gohighlevel.com/v1/workflows",
            "params": {"locationId": SOLAR_LOCATION_ID}
        },
        {
            "name": "Solar Token - v2 workflows",
            "token": SOLAR_TOKEN,
            "url": "https://services.leadconnectorhq.com/workflows",
            "params": None
        },
        {
            "name": "Solar Token - v2 workflows with locationId",
            "token": SOLAR_TOKEN,
            "url": "https://services.leadconnectorhq.com/workflows",
            "params": {"locationId": SOLAR_LOCATION_ID}
        }
    ]
    
    successful_workflows = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        if test_case['params']:
            print(f"   Params: {test_case['params']}")
        
        headers = {
            "Authorization": f"Bearer {test_case['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        try:
            response = requests.get(
                test_case['url'],
                headers=headers,
                params=test_case['params'],
                timeout=30
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response structures
                workflows = []
                if isinstance(data, list):
                    workflows = data
                elif isinstance(data, dict):
                    if "workflows" in data:
                        workflows = data["workflows"]
                    elif "data" in data:
                        workflows = data["data"]
                
                print(f"   ✅ SUCCESS! Found {len(workflows)} workflows")
                
                if workflows:
                    successful_workflows = workflows
                    print(f"   Sample workflows:")
                    for j, workflow in enumerate(workflows[:3], 1):
                        print(f"      {j}. {workflow.get('name', 'Unknown')} (ID: {workflow.get('id', 'Unknown')})")
                        print(f"         Status: {workflow.get('status', 'Unknown')}")
                        print(f"         Location: {workflow.get('locationId', 'Unknown')}")
                
            else:
                print(f"   ❌ Failed: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    # If we found workflows, try to get details of one specific workflow
    if successful_workflows:
        print(f"\n🎯 Testing Individual Workflow Details")
        print("=" * 40)
        
        target_workflow = successful_workflows[0]  # Use first workflow
        workflow_id = target_workflow.get('id')
        workflow_name = target_workflow.get('name', 'Unknown')
        
        print(f"Target Workflow: {workflow_name} (ID: {workflow_id})")
        
        # Test different endpoints for getting individual workflow details
        detail_endpoints = [
            f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
            f"https://services.leadconnectorhq.com/workflows/{workflow_id}",
            f"https://rest.gohighlevel.com/v1/locations/{SOLAR_LOCATION_ID}/workflows/{workflow_id}"
        ]
        
        for endpoint in detail_endpoints:
            print(f"\n   Testing: {endpoint}")
            
            headers = {
                "Authorization": f"Bearer {SOLAR_TOKEN}",
                "Content-Type": "application/json",
                "Version": "2021-07-28"
            }
            
            try:
                response = requests.get(endpoint, headers=headers, timeout=30)
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    workflow_details = response.json()
                    print(f"   ✅ SUCCESS! Got workflow details")
                    print(f"   Name: {workflow_details.get('name', 'Unknown')}")
                    print(f"   Status: {workflow_details.get('status', 'Unknown')}")
                    print(f"   Location: {workflow_details.get('locationId', 'Unknown')}")
                    
                    # Try to clone this workflow
                    print(f"\n🚀 Attempting to clone this workflow...")
                    clone_success = attempt_clone_workflow(workflow_id, workflow_details, SOLAR_TOKEN)
                    
                    if clone_success:
                        print(f"🎉 WORKFLOW CLONE SUCCESS!")
                        return True
                    else:
                        print(f"❌ Workflow clone failed")
                    
                    break
                else:
                    print(f"   ❌ Failed: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"   💥 Error: {str(e)}")
    
    print(f"\n📊 SUMMARY")
    print("=" * 20)
    print(f"Workflows Found: {'✅ YES' if successful_workflows else '❌ NO'}")
    print(f"Total Workflows: {len(successful_workflows) if successful_workflows else 0}")
    
    return len(successful_workflows) > 0


def attempt_clone_workflow(workflow_id: str, workflow_data: dict, token: str):
    """Try to clone the workflow using different methods"""
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # Try to clone to the same location first (duplicate within same location)
    target_location_id = "JUTFTny8EXQOSB5NcvAA"  # Same as source for testing
    
    clone_attempts = [
        {
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/duplicate",
            "payload": {
                "locationId": target_location_id,
                "name": f"TEST CLONE - {workflow_data.get('name', 'Workflow')}"
            }
        },
        {
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"TEST CLONE - {workflow_data.get('name', 'Workflow')}",
                "locationId": target_location_id,
                "status": "draft"
            }
        },
        {
            "url": f"https://services.leadconnectorhq.com/workflows/{workflow_id}/duplicate",
            "payload": {
                "targetLocationId": target_location_id,
                "name": f"TEST CLONE - {workflow_data.get('name', 'Workflow')}"
            }
        }
    ]
    
    for i, attempt in enumerate(clone_attempts, 1):
        print(f"   Clone Attempt {i}: {attempt['url']}")
        print(f"   Payload: {json.dumps(attempt['payload'], indent=2)}")
        
        try:
            response = requests.post(
                attempt['url'],
                headers=headers,
                json=attempt['payload'],
                timeout=30
            )
            
            print(f"   Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"   ✅ SUCCESS! {json.dumps(result, indent=2)[:150]}...")
                return True
            else:
                print(f"   ❌ Failed: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    return False


if __name__ == "__main__":
    print("🚀 Workflow Endpoint Discovery Test")
    print("=" * 60)
    
    success = test_workflow_endpoints()
    
    print(f"\n🏁 Test completed: {'🎉 SUCCESS' if success else '⚠️ INVESTIGATION NEEDED'}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
