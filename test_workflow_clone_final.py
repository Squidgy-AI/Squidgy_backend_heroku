#!/usr/bin/env python3
"""
Final test to clone workflows based on the working endpoints we discovered.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant


def get_workflows_list():
    """Get list of workflows using the working endpoint"""
    
    headers = {
        "Authorization": f"Bearer {Constant.Solar_Access_Token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    try:
        print("🔍 Getting workflows list...")
        response = requests.get(
            "https://rest.gohighlevel.com/v1/workflows",
            headers=headers,
            timeout=30
        )
        
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
                else:
                    # If it's a dict but not the expected structure, treat as single workflow
                    workflows = [data]
            
            print(f"✅ Found {len(workflows)} workflows")
            if workflows:
                print(f"   Sample: {workflows[0].get('name', 'Unknown')} (ID: {workflows[0].get('id', 'Unknown')})")
            return workflows
        else:
            print(f"❌ Failed to get workflows: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"💥 Error getting workflows: {str(e)}")
        return []


def create_new_location():
    """Create a new test location to clone workflow to"""
    
    headers = {
        "Authorization": f"Bearer {Constant.Agency_Api_Key}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    test_name = f"Workflow Clone Test {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    location_data = {
        "name": test_name,
        "businessName": test_name,  # Required field
        "address": "123 Test St",
        "city": "Test City", 
        "state": "CA",
        "country": "US",
        "postalCode": "12345",
        "website": "https://test.com",
        "timezone": "America/Los_Angeles"
    }
    
    try:
        print(f"🏗️  Creating new location: {location_data['name']}")
        
        response = requests.post(
            "https://rest.gohighlevel.com/v1/locations/",
            headers=headers,
            json=location_data,
            timeout=30
        )
        
        print(f"   Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            
            # Handle different response structures
            location_id = None
            if "location" in result and "id" in result["location"]:
                location_id = result["location"]["id"]
            elif "id" in result:
                location_id = result["id"]
            
            if location_id:
                print(f"✅ Location created: {location_id}")
                return location_id
            else:
                print(f"❌ No location ID found in response: {result}")
                return None
        else:
            print(f"❌ Failed to create location: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Error creating location: {str(e)}")
        return None


def attempt_workflow_clone_comprehensive(source_workflow, target_location_id):
    """Try comprehensive workflow cloning approaches"""
    
    workflow_id = source_workflow.get('id')
    workflow_name = source_workflow.get('name', 'Unknown')
    
    print(f"🚀 Attempting to clone: {workflow_name} (ID: {workflow_id})")
    print(f"   Target Location: {target_location_id}")
    
    # Use Solar token for workflow operations
    headers = {
        "Authorization": f"Bearer {Constant.Solar_Access_Token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    # Comprehensive list of clone attempts
    clone_attempts = [
        # Method 1: Direct duplicate endpoint
        {
            "name": "Direct Duplicate",
            "method": "POST",
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/duplicate",
            "payload": {
                "locationId": target_location_id,
                "name": f"CLONED - {workflow_name}"
            }
        },
        
        # Method 2: Create new workflow with source reference
        {
            "name": "Create with Source Reference",
            "method": "POST",
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_name}",
                "locationId": target_location_id,
                "status": "draft",
                "sourceWorkflowId": workflow_id
            }
        },
        
        # Method 3: Copy endpoint
        {
            "name": "Copy Endpoint",
            "method": "POST",
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/copy",
            "payload": {
                "targetLocationId": target_location_id,
                "name": f"CLONED - {workflow_name}"
            }
        },
        
        # Method 4: Clone endpoint
        {
            "name": "Clone Endpoint",
            "method": "POST",
            "url": f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/clone",
            "payload": {
                "locationId": target_location_id,
                "name": f"CLONED - {workflow_name}"
            }
        },
        
        # Method 5: Template-based creation
        {
            "name": "Template Creation",
            "method": "POST",
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_name}",
                "locationId": target_location_id,
                "templateId": workflow_id,
                "status": "draft"
            }
        },
        
        # Method 6: Full workflow data recreation
        {
            "name": "Full Recreation",
            "method": "POST",
            "url": "https://rest.gohighlevel.com/v1/workflows/",
            "payload": {
                "name": f"CLONED - {workflow_name}",
                "locationId": target_location_id,
                "status": source_workflow.get('status', 'draft'),
                "version": source_workflow.get('version', 1)
            }
        }
    ]
    
    for i, attempt in enumerate(clone_attempts, 1):
        print(f"\n   🔄 Method {i}: {attempt['name']}")
        print(f"      URL: {attempt['url']}")
        print(f"      Payload: {json.dumps(attempt['payload'], indent=6)}")
        
        try:
            response = requests.request(
                attempt['method'],
                attempt['url'],
                headers=headers,
                json=attempt['payload'],
                timeout=30
            )
            
            print(f"      Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"      ✅ SUCCESS! Response: {json.dumps(result, indent=6)[:200]}...")
                
                # Extract the new workflow ID if available
                new_workflow_id = None
                if "workflow" in result and "id" in result["workflow"]:
                    new_workflow_id = result["workflow"]["id"]
                elif "id" in result:
                    new_workflow_id = result["id"]
                
                if new_workflow_id:
                    print(f"      🎯 New Workflow ID: {new_workflow_id}")
                
                return True, new_workflow_id
            else:
                print(f"      ❌ Failed: {response.text[:150]}...")
                
        except Exception as e:
            print(f"      💥 Error: {str(e)}")
    
    return False, None


def verify_workflow_in_target_location(target_location_id, cloned_workflow_name):
    """Verify if the cloned workflow exists in the target location"""
    
    # Use Agency API key to check the new location
    headers = {
        "Authorization": f"Bearer {Constant.Agency_Api_Key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔍 Verifying workflows in target location {target_location_id}...")
        
        # Try to get workflows for the specific location
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/workflows/?locationId={target_location_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            workflows = response.json()
            print(f"✅ Found {len(workflows)} workflows in target location")
            
            # Look for our cloned workflow
            for workflow in workflows:
                if cloned_workflow_name.lower() in workflow.get('name', '').lower():
                    print(f"🎯 Found cloned workflow: {workflow.get('name')} (ID: {workflow.get('id')})")
                    return True
            
            print(f"❌ Cloned workflow '{cloned_workflow_name}' not found")
            if workflows:
                print(f"   Available workflows:")
                for workflow in workflows[:3]:
                    print(f"   - {workflow.get('name', 'Unknown')} (ID: {workflow.get('id', 'Unknown')})")
            
            return False
        else:
            print(f"❌ Failed to get workflows from target location: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"💥 Error verifying workflows: {str(e)}")
        return False


def main():
    """Main test function"""
    
    print("🚀 Final Workflow Clone Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Get workflows from Solar account
    print(f"\n📋 Step 1: Getting Solar workflows...")
    workflows = get_workflows_list()
    
    if not workflows:
        print("❌ No workflows found. Aborting test.")
        return False
    
    # Use the first workflow for testing
    target_workflow = workflows[0]
    print(f"🎯 Target workflow: {target_workflow.get('name')} (ID: {target_workflow.get('id')})")
    
    # Step 2: Create new location
    print(f"\n🏗️  Step 2: Creating target location...")
    target_location_id = create_new_location()
    
    if not target_location_id:
        print("❌ Failed to create target location. Aborting test.")
        return False
    
    # Step 3: Attempt workflow clone
    print(f"\n🔄 Step 3: Attempting workflow clone...")
    clone_success, new_workflow_id = attempt_workflow_clone_comprehensive(target_workflow, target_location_id)
    
    # Step 4: Verify clone
    verification_success = False
    if clone_success:
        print(f"\n✅ Step 4: Verifying clone...")
        cloned_name = f"CLONED - {target_workflow.get('name')}"
        verification_success = verify_workflow_in_target_location(target_location_id, cloned_name)
    
    # Final Results
    print(f"\n📊 FINAL RESULTS")
    print("=" * 30)
    print(f"Source Workflow: {target_workflow.get('name')} (ID: {target_workflow.get('id')})")
    print(f"Target Location: {target_location_id}")
    print(f"Clone Attempted: {'✅ YES' if clone_success else '❌ NO'}")
    print(f"Clone Verified: {'✅ YES' if verification_success else '❌ NO'}")
    
    if new_workflow_id:
        print(f"New Workflow ID: {new_workflow_id}")
    
    overall_success = clone_success and verification_success
    print(f"\n🏁 Overall Result: {'🎉 SUCCESS - Workflow cloned successfully!' if overall_success else '⚠️ PARTIAL/FAILED - Check logs for details'}")
    
    return overall_success


if __name__ == "__main__":
    main()
