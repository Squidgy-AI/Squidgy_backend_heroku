#!/usr/bin/env python3
"""
Combined approach for Solar sub-account cloning:
1. Create a new location using manual_clone_location
2. Attempt to import the specific snapshot
3. Document workflows as a fallback
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant
from GHL.Sub_Accounts.manual_clone import manual_clone_location, get_location_details
from GHL.Sub_Accounts.workflow_snapshot_helper import WorkflowSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("clone_with_snapshot.log"),
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


def get_workflows_list(location_id: str, access_token: str) -> List[Dict]:
    """Get list of workflows from the source location"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    success, response = make_api_request(
        "GET",
        "https://rest.gohighlevel.com/v1/workflows",
        headers
    )
    
    if success:
        # Handle different response structures
        workflows = []
        if isinstance(response, list):
            workflows = response
        elif isinstance(response, dict):
            if "workflows" in response:
                workflows = response["workflows"]
            elif "data" in response:
                workflows = response["data"]
            else:
                # If it's a dict but not the expected structure, treat as single workflow
                workflows = [response]
        
        logger.info(f"Found {len(workflows)} workflows")
        return workflows
    else:
        logger.error("Failed to get workflows list")
        return []


def create_workflow_snapshots(workflows: List[Dict], snapshots_dir: str) -> List[str]:
    """Create workflow snapshots for all workflows"""
    snapshot_files = []
    
    # Create snapshots directory if it doesn't exist
    os.makedirs(snapshots_dir, exist_ok=True)
    
    for workflow in workflows:
        workflow_id = workflow.get("id")
        workflow_name = workflow.get("name", "Unknown Workflow")
        
        logger.info(f"Creating snapshot for workflow: {workflow_name} (ID: {workflow_id})")
        
        # Create a new snapshot
        snapshot = WorkflowSnapshot(workflow_id, workflow_name)
        
        # Add basic workflow details
        snapshot.add_note(f"Workflow Status: {workflow.get('status', 'Unknown')}")
        snapshot.add_note(f"Created: {workflow.get('createdAt', 'Unknown')}")
        snapshot.add_note(f"Updated: {workflow.get('updatedAt', 'Unknown')}")
        
        # Extract triggers, conditions, and actions if available
        if "triggers" in workflow:
            for trigger in workflow["triggers"]:
                snapshot.add_trigger(
                    trigger.get("type", "Unknown"),
                    trigger.get("description", "No description"),
                    trigger
                )
        
        if "conditions" in workflow:
            for condition in workflow["conditions"]:
                snapshot.add_condition(
                    condition.get("type", "Unknown"),
                    condition.get("description", "No description"),
                    condition
                )
        
        if "actions" in workflow:
            for action in workflow["actions"]:
                snapshot.add_action(
                    action.get("type", "Unknown"),
                    action.get("description", "No description"),
                    action
                )
        
        # Add a note about API restrictions
        snapshot.add_note("This workflow was documented via the WorkflowSnapshot system due to GoHighLevel API restrictions on Solar sub-account workflow cloning.")
        
        # Generate a safe filename
        safe_name = workflow_name.replace(":", "").replace("/", "_").replace("\\", "_").replace("?", "_").replace("*", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_").replace(" ", "_")
        safe_filename = f"{safe_name}_{workflow_id[-8:]}.json"
        
        # Save the snapshot directly with our own implementation
        filepath = os.path.join(snapshots_dir, safe_filename)
        
        with open(filepath, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        
        snapshot_files.append(filepath)
        logger.info(f"Saved workflow snapshot to {filepath}")
    
    return snapshot_files


def attempt_import_snapshot(snapshot_id: str, target_location_id: str, company_id: str = None):
    """Attempt to import a specific snapshot to a target location"""
    
    # Try both Solar token and Agency API key
    tokens = [
        {"name": "Solar Access Token", "token": Constant.Solar_Access_Token},
        {"name": "Agency API Key", "token": Constant.Agency_Api_Key}
    ]
    
    # Get Solar company ID if not provided
    if company_id is None:
        company_id = Constant.Solar_Company_Id
    
    for token_info in tokens:
        logger.info(f"Trying to import snapshot with {token_info['name']}...")
        
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
            },
            # Endpoint 5: Alternative endpoint with companyId
            {
                "url": f"https://services.leadconnectorhq.com/snapshots/{snapshot_id}/import",
                "payload": {
                    "companyId": company_id,
                    "locationId": target_location_id
                },
                "description": "Using snapshot ID in URL with companyId"
            },
            # Endpoint 6: GHL UI endpoint
            {
                "url": "https://marketplace.gohighlevel.com/api/v1/snapshots/import",
                "payload": {
                    "snapshotId": snapshot_id,
                    "locationId": target_location_id
                },
                "description": "Using marketplace API endpoint"
            }
        ]
        
        for endpoint in endpoints:
            logger.info(f"Trying endpoint: {endpoint['description']}")
            
            success, response = make_api_request(
                "POST",
                endpoint["url"],
                headers,
                endpoint["payload"]
            )
            
            if success:
                logger.info(f"Success! Response: {json.dumps(response)[:100]}...")
                return {
                    "success": True,
                    "response": response,
                    "token_used": token_info["name"],
                    "endpoint_used": endpoint["description"]
                }
            else:
                logger.info(f"Failed: {json.dumps(response)[:100]}...")
    
    return {
        "success": False,
        "error": "All import attempts failed"
    }


def clone_with_snapshot(source_location_id: str, target_name: str, snapshot_id: str):
    """Clone a location and attempt to import a specific snapshot"""
    start_time = datetime.now()
    logger.info(f"Starting clone process at {start_time}")
    
    result = {
        "success": False,
        "start_time": start_time.isoformat(),
        "source_location_id": source_location_id,
        "target_name": target_name,
        "snapshot_id": snapshot_id,
        "steps": []
    }
    
    # Step 1: Clone the location using manual_clone_location
    logger.info("Step 1: Cloning location")
    clone_result = manual_clone_location(
        source_location_id=source_location_id,
        new_location_name=target_name,
        access_token=Constant.Agency_Api_Key
    )
    
    result["steps"].append({
        "step": "clone_location",
        "success": clone_result.get("success", False),
        "details": clone_result
    })
    
    if not clone_result.get("success", False) or "new_location_id" not in clone_result:
        logger.error("Location cloning failed. Aborting clone process.")
        result["error"] = "Location cloning failed"
        result["end_time"] = datetime.now().isoformat()
        return result
    
    new_location_id = clone_result["new_location_id"]
    logger.info(f"Successfully cloned location. New ID: {new_location_id}")
    
    # Step 2: Attempt to import the specific snapshot
    logger.info("Step 2: Attempting to import snapshot")
    import_result = attempt_import_snapshot(snapshot_id, new_location_id)
    
    result["steps"].append({
        "step": "import_snapshot",
        "success": import_result.get("success", False),
        "details": import_result
    })
    
    # Step 3: Get workflows and create documentation as fallback
    logger.info("Step 3: Getting workflows list for documentation")
    workflows = get_workflows_list(source_location_id, Constant.Solar_Access_Token)
    
    result["steps"].append({
        "step": "get_workflows",
        "success": len(workflows) > 0,
        "count": len(workflows)
    })
    
    if workflows:
        # Create workflow snapshots
        logger.info("Step 4: Creating workflow snapshots")
        snapshots_dir = os.path.join("workflow_snapshots", f"clone_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        snapshot_files = create_workflow_snapshots(workflows, snapshots_dir)
        
        result["steps"].append({
            "step": "create_snapshots",
            "success": len(snapshot_files) > 0,
            "count": len(snapshot_files),
            "directory": snapshots_dir,
            "files": snapshot_files
        })
    
    # Final result
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    result.update({
        "success": True,  # Consider overall process successful if location was cloned
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "new_location_id": new_location_id,
        "snapshot_import_success": import_result.get("success", False),
        "workflow_count": len(workflows) if workflows else 0,
        "message": f"Successfully cloned location and {'imported snapshot' if import_result.get('success', False) else 'documented workflows'}"
    })
    
    logger.info(f"Clone process completed in {duration} seconds")
    return result


def main():
    """Main function to clone a location and import a specific snapshot"""
    print("🚀 GoHighLevel Clone with Snapshot")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Source location ID (Solar sub-account)
    source_location_id = "JUTFTny8EXQOSB5NcvAA"
    
    # Specific snapshot ID to import
    snapshot_id = "7oAH6Cmto5ZcWAaEsrrq"
    
    # Target location name
    target_name = f"Solar Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n📋 Source Location: {source_location_id}")
    print(f"📸 Snapshot ID: {snapshot_id}")
    print(f"🏢 Target Name: {target_name}")
    print("=" * 50)
    
    # Execute the clone process
    result = clone_with_snapshot(source_location_id, target_name, snapshot_id)
    
    print("\n📊 Clone Results:")
    print("=" * 30)
    print(f"Success: {'✅' if result['success'] else '❌'}")
    
    if result['success']:
        print(f"New Location ID: {result['new_location_id']}")
        print(f"Snapshot Import: {'✅' if result['snapshot_import_success'] else '❌'}")
        print(f"Workflows Documented: {result['workflow_count']}")
        print(f"Duration: {result['duration_seconds']:.2f} seconds")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("\n📝 Step Results:")
    for step in result['steps']:
        print(f"  - {step['step']}: {'✅' if step['success'] else '❌'}")
    
    return result['success']


if __name__ == "__main__":
    main()
