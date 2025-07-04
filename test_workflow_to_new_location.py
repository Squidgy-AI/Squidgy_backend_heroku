#!/usr/bin/env python3
"""
Test to create a new location and then try to clone a workflow to it.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant


def create_test_location():
    """Create a simple test location"""
    
    headers = {
        "Authorization": f"Bearer {Constant.Agency_Api_Key}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    location_data = {
        "name": f"Workflow Test {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "address": "123 Test St",
        "city": "Test City",
        "state": "CA",
        "country": "US",
        "postalCode": "12345",
        "website": "https://test.com",
        "timezone": "America/Los_Angeles"
    }
    
    try:
        print(f"🏗️  Creating test location: {location_data['name']}")
        
        response = requests.post(
            "https://rest.gohighlevel.com/v1/locations/",
            headers=headers,
            json=location_data,
            timeout=30
        )
        
        print(f"   Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            location_id = result.get("location", {}).get("id") or result.get("id")
            
            if location_id:
                print(f"✅ Location created successfully: {location_id}")
                return location_id
            else:
                print(f"❌ No location ID in response: {result}")
                return None
        else:
            print(f"❌ Failed to create location: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Error creating location: {str(e)}")
        return None


def clone_workflow_to_location(workflow_id: str, target_location_id: str):
    """Try to clone a specific workflow to the target location"""
    
    headers = {
        "Authorization": f"Bearer {Constant.Solar_Access_Token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # First get the workflow details
    print(f"🔍 Getting workflow details for {workflow_id}...")
    
    workflow_response = requests.get(
        f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
        headers=headers,
        timeout=30
    )
    
    if workflow_response.status_code != 200:
        print(f"❌ Failed to get workflow details: {workflow_response.status_code}")
        return False
    
    workflow_data = workflow_response.json()
    workflow_name = workflow_data.get("name", "Unknown Workflow")
    print(f"✅ Found workflow: {workflow_name}")
    
    # Now try to clone it
    print(f"🚀 Attempting to clone workflow to location {target_location_id}...")
    
    # Try different cloning approaches
    clone_attempts = [
        {
            "method": "POST",
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/duplicate",
            "payload": {
                "locationId": target_location_id,
                "name": f"CLONED - {workflow_name}"
            }
        },
        {
            "method": "POST", 
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_name}",
                "locationId": target_location_id,
                "status": "draft",
                "sourceWorkflowId": workflow_id
            }
        },
        {
            "method": "POST",
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/copy",
            "payload": {
                "targetLocationId": target_location_id,
                "name": f"CLONED - {workflow_name}"
            }
        }
    ]
    
    for i, attempt in enumerate(clone_attempts, 1):
        print(f"\n   Attempt {i}: {attempt['method']} {attempt['url']}")
        print(f"   Payload: {json.dumps(attempt['payload'], indent=2)}")
        
        try:
            response = requests.request(
                attempt['method'],
                attempt['url'],
                headers=headers,
                json=attempt['payload'],
                timeout=30
            )
            
            print(f"   Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"   ✅ SUCCESS! Response: {json.dumps(result, indent=2)[:200]}...")
                return True
            else:
                print(f"   ❌ Failed: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    return False


def verify_workflow_in_location(location_id: str, workflow_name: str):
    """Check if the workflow exists in the target location"""
    
    headers = {
        "Authorization": f"Bearer {Constant.Agency_Api_Key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔍 Checking workflows in location {location_id}...")
        
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/workflows/?locationId={location_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            workflows = response.json()
            
            # Handle different response formats
            if isinstance(workflows, list):
                workflow_list = workflows
            elif isinstance(workflows, dict) and "workflows" in workflows:
                workflow_list = workflows["workflows"]
            else:
                workflow_list = []
            
            print(f"✅ Found {len(workflow_list)} workflows in location")
            
            # Look for our cloned workflow
            for workflow in workflow_list:
                if workflow_name.lower() in workflow.get("name", "").lower():
                    print(f"🎯 Found cloned workflow: {workflow.get('name')} (ID: {workflow.get('id')})")
                    return True
            
            print(f"❌ Cloned workflow not found")
            return False
        else:
            print(f"❌ Failed to get workflows: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error checking workflows: {str(e)}")
        return False


def main():
    """Main test function"""
    
    print("🚀 Workflow Clone to New Location Test")
    print("=" * 50)
    
    # Configuration
    SOURCE_WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"  # "Set Last Communication Type"
    
    print(f"Source Workflow ID: {SOURCE_WORKFLOW_ID}")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    
    # Step 1: Create test location
    print(f"\n📍 Step 1: Creating test location...")
    target_location_id = create_test_location()
    
    if not target_location_id:
        print("❌ Failed to create test location. Aborting.")
        return False
    
    # Step 2: Clone workflow
    print(f"\n🔄 Step 2: Cloning workflow...")
    clone_success = clone_workflow_to_location(SOURCE_WORKFLOW_ID, target_location_id)
    
    # Step 3: Verify workflow
    print(f"\n✅ Step 3: Verifying workflow...")
    if clone_success:
        verify_success = verify_workflow_in_location(target_location_id, "CLONED - Set Last Communication Type")
    else:
        verify_success = False
    
    # Summary
    print(f"\n📊 FINAL RESULTS")
    print("=" * 30)
    print(f"Test Location Created: ✅ {target_location_id}")
    print(f"Workflow Clone Success: {'✅ YES' if clone_success else '❌ NO'}")
    print(f"Workflow Verified: {'✅ YES' if verify_success else '❌ NO'}")
    
    overall_success = clone_success and verify_success
    print(f"\n🏁 Overall Result: {'🎉 SUCCESS' if overall_success else '⚠️ PARTIAL/FAILED'}")
    
    return overall_success


if __name__ == "__main__":
    main()
