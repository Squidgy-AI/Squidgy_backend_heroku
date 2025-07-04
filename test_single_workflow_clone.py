#!/usr/bin/env python3
"""
Test script to attempt cloning a single workflow from Solar sub-account to a new location.
This will help us understand if individual workflow cloning is possible via API.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant
from GHL.Sub_Accounts.manual_clone import manual_clone_location, get_location_details


def test_single_workflow_clone():
    """Test cloning a single workflow from Solar to a new location"""
    
    # Solar sub-account details
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    SOLAR_TOKEN = Constant.Solar_Access_Token
    AGENCY_API_KEY = Constant.Agency_Api_Key
    
    # Target workflow ID (from our test results)
    TARGET_WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"  # "Set Last Communication Type"
    
    print("🔄 Testing Single Workflow Clone")
    print("================================")
    print(f"Source Location: {SOLAR_LOCATION_ID}")
    print(f"Target Workflow: {TARGET_WORKFLOW_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Create a test location first
    print("\n📍 Step 1: Creating test location...")
    test_location_name = f"Workflow Test {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        clone_result = manual_clone_location(
            source_location_id=SOLAR_LOCATION_ID,
            new_location_name=test_location_name,
            access_token=AGENCY_API_KEY
        )
        
        if not clone_result.get("success"):
            print(f"❌ Failed to create test location: {clone_result.get('error')}")
            return
        
        new_location_id = clone_result.get("new_location_id")
        print(f"✅ Test location created: {new_location_id}")
        print(f"   Name: {test_location_name}")
        
    except Exception as e:
        print(f"💥 Error creating test location: {str(e)}")
        return
    
    # Step 2: Get workflow details from source
    print(f"\n🔍 Step 2: Fetching workflow details...")
    workflow_details = get_workflow_details(TARGET_WORKFLOW_ID, SOLAR_TOKEN)
    
    if not workflow_details.get("success"):
        print(f"❌ Failed to get workflow details: {workflow_details.get('error')}")
        return
    
    workflow_data = workflow_details.get("workflow_data", {})
    print(f"✅ Workflow details retrieved:")
    print(f"   Name: {workflow_data.get('name', 'Unknown')}")
    print(f"   Status: {workflow_data.get('status', 'Unknown')}")
    print(f"   Location ID: {workflow_data.get('locationId', 'Unknown')}")
    
    # Step 3: Attempt to clone the workflow
    print(f"\n🚀 Step 3: Attempting workflow clone...")
    clone_success = attempt_workflow_clone(
        source_workflow_id=TARGET_WORKFLOW_ID,
        target_location_id=new_location_id,
        workflow_data=workflow_data,
        solar_token=SOLAR_TOKEN
    )
    
    if clone_success:
        print("🎉 SUCCESS: Workflow cloned successfully!")
    else:
        print("❌ FAILED: Workflow clone unsuccessful")
    
    # Step 4: Verify if workflow exists in target location
    print(f"\n🔍 Step 4: Verifying workflow in target location...")
    target_workflows = get_location_workflows(new_location_id, AGENCY_API_KEY)
    
    if target_workflows.get("success"):
        workflows = target_workflows.get("workflows", [])
        print(f"✅ Found {len(workflows)} workflows in target location")
        
        # Look for our cloned workflow
        cloned_workflow = None
        for workflow in workflows:
            if workflow.get("name") == workflow_data.get("name"):
                cloned_workflow = workflow
                break
        
        if cloned_workflow:
            print(f"🎯 SUCCESS: Found cloned workflow!")
            print(f"   ID: {cloned_workflow.get('id')}")
            print(f"   Name: {cloned_workflow.get('name')}")
            print(f"   Status: {cloned_workflow.get('status')}")
        else:
            print("❌ Cloned workflow not found in target location")
    else:
        print(f"❌ Failed to get workflows from target location: {target_workflows.get('error')}")
    
    # Step 5: Summary
    print(f"\n📊 SUMMARY")
    print("=" * 40)
    print(f"Test Location ID: {new_location_id}")
    print(f"Workflow Clone Success: {'✅ YES' if clone_success else '❌ NO'}")
    print(f"Workflow Verified: {'✅ YES' if 'cloned_workflow' in locals() and cloned_workflow else '❌ NO'}")
    
    return {
        "success": clone_success,
        "test_location_id": new_location_id,
        "workflow_verified": 'cloned_workflow' in locals() and cloned_workflow is not None
    }


def get_workflow_details(workflow_id: str, access_token: str):
    """Get detailed information about a specific workflow"""
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Try multiple endpoints
    endpoints = [
        f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://services.leadconnectorhq.com/workflows/{workflow_id}",
        f"https://rest.gohighlevel.com/v1/locations/{Constant.Solar_Access_Token.split('.')[1]}/workflows/{workflow_id}"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"   Trying endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=30)
            
            if response.status_code == 200:
                workflow_data = response.json()
                print(f"   ✅ Success with endpoint: {endpoint}")
                return {
                    "success": True,
                    "workflow_data": workflow_data,
                    "endpoint": endpoint
                }
            else:
                print(f"   ❌ Failed: {response.status_code} - {response.text[:100]}")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    return {
        "success": False,
        "error": "Failed to get workflow details from any endpoint"
    }


def attempt_workflow_clone(source_workflow_id: str, target_location_id: str, workflow_data: dict, solar_token: str):
    """Attempt to clone a single workflow using various API endpoints"""
    
    headers = {
        "Authorization": f"Bearer {solar_token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # Multiple clone endpoints to try
    clone_endpoints = [
        f"https://services.leadconnectorhq.com/workflows/{source_workflow_id}/clone",
        f"https://services.leadconnectorhq.com/workflows/clone",
        f"https://services.leadconnectorhq.com/locations/{target_location_id}/workflows/clone",
        f"https://rest.gohighlevel.com/v1/workflows/{source_workflow_id}/clone",
        f"https://rest.gohighlevel.com/v1/workflows/clone",
        f"https://services.leadconnectorhq.com/workflows/{source_workflow_id}/copy",
        f"https://services.leadconnectorhq.com/workflows/copy"
    ]
    
    # Multiple payload variants
    payload_variants = [
        {
            "sourceWorkflowId": source_workflow_id,
            "targetLocationId": target_location_id,
            "name": workflow_data.get("name", "Cloned Workflow")
        },
        {
            "workflowId": source_workflow_id,
            "locationId": target_location_id,
            "preserveId": False
        },
        {
            "sourceId": source_workflow_id,
            "targetLocationId": target_location_id,
            "workflowData": workflow_data
        },
        {
            "templateId": source_workflow_id,
            "targetLocation": target_location_id,
            "workflowName": workflow_data.get("name", "Cloned Workflow")
        }
    ]
    
    print(f"   Attempting {len(clone_endpoints)} endpoints with {len(payload_variants)} payload variants...")
    
    for endpoint in clone_endpoints:
        print(f"   🔄 Trying endpoint: {endpoint}")
        
        for i, payload in enumerate(payload_variants, 1):
            try:
                print(f"      Payload variant {i}: {json.dumps(payload, indent=2)[:100]}...")
                
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                print(f"      Response: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    print(f"      ✅ SUCCESS! Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True
                else:
                    print(f"      ❌ Failed: {response.text[:100]}")
                    
            except Exception as e:
                print(f"      💥 Error: {str(e)}")
    
    return False


def get_location_workflows(location_id: str, access_token: str):
    """Get all workflows for a location"""
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/workflows",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            workflows = []
            
            # Handle different response structures
            if isinstance(data, list):
                workflows = data
            elif isinstance(data, dict) and "workflows" in data:
                workflows = data["workflows"]
            
            # Filter for the specific location
            location_workflows = [w for w in workflows if w.get("locationId") == location_id]
            
            return {
                "success": True,
                "workflows": location_workflows
            }
        else:
            return {
                "success": False,
                "error": f"API returned {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    print("🚀 Single Workflow Clone Test")
    print("=" * 50)
    
    result = test_single_workflow_clone()
    
    print(f"\n🏁 Test completed at: {datetime.now().isoformat()}")
    
    if result and result.get("success"):
        print("🎉 Overall result: SUCCESS - Workflow cloning worked!")
    else:
        print("⚠️  Overall result: PARTIAL - Location created but workflow cloning needs investigation")
