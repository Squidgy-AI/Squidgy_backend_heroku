#!/usr/bin/env python3
"""
Test script to explore the GoHighLevel snapshots API as a potential workaround
for Solar sub-account workflow cloning limitations.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant


def get_snapshots_list():
    """Get list of snapshots using the discovered endpoint"""
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Solar location ID and company ID
    solar_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar location ID
    solar_company_id = Constant.Solar_Company_Id  # Solar company ID
    
    for token_info in tokens:
        print(f"\n🔍 Trying to get snapshots with {token_info['name']}...")
        
        headers = {
            "Authorization": f"Bearer {token_info['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Try different API endpoints and parameters
        endpoints = [
            # Endpoint 1: With companyId as query parameter using Solar_Company_Id
            {
                "url": f"https://services.leadconnectorhq.com/snapshots?companyId={solar_company_id}",
                "description": "Using Solar_Company_Id as companyId parameter"
            },
            # Endpoint 2: With locationId as query parameter
            {
                "url": f"https://services.leadconnectorhq.com/snapshots?locationId={solar_location_id}",
                "description": "Using locationId as query parameter"
            },
            # Endpoint 3: Alternative v2 endpoint with Solar_Company_Id
            {
                "url": f"https://api.gohighlevel.com/v2/snapshots?companyId={solar_company_id}",
                "description": "Using v2 API endpoint with Solar_Company_Id"
            },
            # Endpoint 4: With both companyId and locationId
            {
                "url": f"https://services.leadconnectorhq.com/snapshots?companyId={solar_company_id}&locationId={solar_location_id}",
                "description": "Using both companyId and locationId parameters"
            },
            # Endpoint 5: Original endpoint
            {
                "url": "https://services.leadconnectorhq.com/snapshots/",
                "description": "Original endpoint"
            }
        ]
        
        for endpoint in endpoints:
            try:
                print(f"   🔍 Trying endpoint: {endpoint['description']}")
                response = requests.get(
                    endpoint['url'],
                    headers=headers,
                    timeout=30
                )
                
                print(f"      Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"      ✅ Success! Found data: {json.dumps(data)[:200]}...")
                    return data, token_info['name'], endpoint['description']
                else:
                    print(f"      ❌ Failed: {response.text[:150]}...")
                    
            except Exception as e:
                print(f"      💥 Error: {str(e)}")
    
    return None, None, None


def create_snapshot(location_id):
    """Attempt to create a snapshot of a location"""
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Get Solar company ID
    solar_company_id = Constant.Solar_Company_Id
    
    snapshot_name = f"Test Snapshot {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    for token_info in tokens:
        print(f"\n📸 Trying to create snapshot with {token_info['name']}...")
        
        headers = {
            "Authorization": f"Bearer {token_info['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Try different payloads and endpoints
        endpoints = [
            # Endpoint 1: Standard endpoint with Solar_Company_Id
            {
                "url": "https://services.leadconnectorhq.com/snapshots",
                "payload": {
                    "name": snapshot_name,
                    "companyId": solar_company_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using Solar_Company_Id in payload"
            },
            # Endpoint 2: Standard endpoint with locationId
            {
                "url": "https://services.leadconnectorhq.com/snapshots",
                "payload": {
                    "name": snapshot_name,
                    "locationId": location_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using locationId in payload"
            },
            # Endpoint 3: Using both companyId and locationId
            {
                "url": "https://services.leadconnectorhq.com/snapshots",
                "payload": {
                    "name": snapshot_name,
                    "companyId": solar_company_id,
                    "locationId": location_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using both Solar_Company_Id and locationId in payload"
            },
            # Endpoint 4: V2 API endpoint with Solar_Company_Id
            {
                "url": "https://api.gohighlevel.com/v2/snapshots",
                "payload": {
                    "name": snapshot_name,
                    "companyId": solar_company_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using v2 API endpoint with Solar_Company_Id"
            },
            # Endpoint 5: Using create endpoint with Solar_Company_Id
            {
                "url": "https://services.leadconnectorhq.com/snapshots/create",
                "payload": {
                    "name": snapshot_name,
                    "companyId": solar_company_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using explicit create endpoint with Solar_Company_Id"
            }
        ]
        
        for endpoint in endpoints:
            try:
                print(f"   🔍 Trying endpoint: {endpoint['description']}")
                response = requests.post(
                    endpoint['url'],
                    headers=headers,
                    json=endpoint['payload'],
                    timeout=30
                )
                
                print(f"      Response Status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"      ✅ Success! Created snapshot: {json.dumps(data)[:200]}...")
                    return data, token_info['name'], endpoint['description']
                else:
                    print(f"      ❌ Failed: {response.text[:150]}...")
                    
            except Exception as e:
                print(f"      💥 Error: {str(e)}")
    
    return None, None, None


def import_snapshot(snapshot_id, target_location_id):
    """Attempt to import a snapshot to a target location"""
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Get Solar company ID
    solar_company_id = Constant.Solar_Company_Id
    
    for token_info in tokens:
        print(f"\n📥 Trying to import snapshot with {token_info['name']}...")
        
        headers = {
            "Authorization": f"Bearer {token_info['token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Try different payloads and endpoints
        endpoints = [
            # Endpoint 1: Standard import endpoint
            {
                "url": "https://services.leadconnectorhq.com/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "locationId": target_location_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Standard import endpoint"
            },
            # Endpoint 2: Using companyId instead of locationId
            {
                "url": "https://services.leadconnectorhq.com/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "companyId": target_location_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using companyId instead of locationId"
            },
            # Endpoint 3: V2 API endpoint
            {
                "url": "https://api.gohighlevel.com/v2/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "locationId": target_location_id,
                    "includeWorkflows": True,
                    "includeAutomations": True,
                    "includeFunnels": True,
                    "includeWebsites": True,
                    "includeEmailTemplates": True,
                    "includeSmsTemplates": True,
                    "includeCustomValues": True,
                    "includeCustomFields": True,
                    "includeTags": True
                },
                "description": "Using v2 API endpoint"
            }
        ]
        
        for endpoint in endpoints:
            try:
                print(f"   🔍 Trying endpoint: {endpoint['description']}")
                response = requests.post(
                    endpoint['url'],
                    headers=headers,
                    json=endpoint['payload'],
                    timeout=30
                )
                
                print(f"      Response Status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"      ✅ Success! Imported snapshot: {json.dumps(data)[:200]}...")
                    return data, token_info['name'], endpoint['description']
                else:
                    print(f"      ❌ Failed: {response.text[:150]}...")
                    
            except Exception as e:
                print(f"      💥 Error: {str(e)}")
    
    return None, None, None


def main():
    """Main test function"""
    
    print("🚀 GoHighLevel Snapshots API Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Get list of snapshots
    print(f"\n📋 Step 1: Getting snapshots list...")
    snapshots_data, token_used, endpoint_used = get_snapshots_list()
    
    if not snapshots_data:
        print("❌ Failed to get snapshots. Trying to create one instead.")
        
        # Solar location ID and company ID from constant
        solar_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar location ID
        solar_company_id = Constant.Solar_Company_Id  # Solar company ID
        
        # Step 2: Create a new snapshot
        print(f"\n📸 Step 2: Creating new snapshot of Solar location...")
        snapshot_data, token_used, endpoint_used = create_snapshot(solar_location_id)
        
        if not snapshot_data:
            print("❌ Failed to create snapshot. Aborting test.")
            return False
        
        snapshot_id = snapshot_data.get("id")
    else:
        # Use the first snapshot from the list
        if isinstance(snapshots_data, list) and snapshots_data:
            snapshot_id = snapshots_data[0].get("id")
        elif isinstance(snapshots_data, dict) and "snapshots" in snapshots_data and snapshots_data["snapshots"]:
            snapshot_id = snapshots_data["snapshots"][0].get("id")
        else:
            print("❌ No snapshots found in response. Creating new one.")
            solar_location_id = "JUTFTny8EXQOSB5NcvAA"  # Replace with your actual Solar location ID
            snapshot_data, token_used, endpoint_used = create_snapshot(solar_location_id)
            
            if not snapshot_data:
                print("❌ Failed to create snapshot. Aborting test.")
                return False
            
            snapshot_id = snapshot_data.get("id")
    
    print(f"🎯 Using snapshot ID: {snapshot_id}")
    print(f"🔑 Token used: {token_used}")
    print(f"🔌 Endpoint used: {endpoint_used}")
    
    # Step 3: Create a new target location
    from test_workflow_clone_final import create_new_location
    print(f"\n🏗️  Step 3: Creating target location...")
    target_location_id = create_new_location()
    
    if not target_location_id:
        print("❌ Failed to create target location. Aborting test.")
        return False
    
    # Step 4: Import snapshot to target location
    print(f"\n📥 Step 4: Importing snapshot to target location...")
    import_result, token_used, endpoint_used = import_snapshot(snapshot_id, target_location_id)
    
    # Final Results
    print(f"\n📊 FINAL RESULTS")
    print("=" * 30)
    print(f"Snapshot ID: {snapshot_id}")
    print(f"Target Location: {target_location_id}")
    print(f"Import Attempted: {'✅ YES' if import_result else '❌ NO'}")
    
    if import_result:
        print(f"Token Used: {token_used}")
        print(f"Endpoint Used: {endpoint_used}")
    else:
        print("❌ No working token/endpoint combination found")
    
    overall_success = import_result is not None
    print(f"\n🏁 Overall Result: {'🎉 SUCCESS - Snapshot imported successfully!' if overall_success else '⚠️ FAILED - Check logs for details'}")
    
    return overall_success


if __name__ == "__main__":
    main()
