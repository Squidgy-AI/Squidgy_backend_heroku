#!/usr/bin/env python3
"""
Integrated solution for Solar sub-account cloning that combines:
1. Location cloning using the Agency API key
2. Workflow documentation and recreation using the WorkflowSnapshot class

This approach works around the API restrictions on Solar sub-account workflow cloning.
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from GHL.environment.constant import Constant
from GHL.Sub_Accounts.workflow_snapshot_helper import WorkflowSnapshot
from GHL.Sub_Accounts.manual_clone import manual_clone_location

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("integrated_clone.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IntegratedCloneSolution:
    """Integrated solution for Solar sub-account cloning"""
    
    def __init__(self, source_location_id: str):
        """Initialize with source location ID"""
        self.source_location_id = source_location_id
        self.solar_token = Constant.Solar_Access_Token
        self.agency_token = Constant.Agency_Api_Key
        self.snapshots_dir = "workflow_snapshots"
        
        # Create snapshots directory if it doesn't exist
        os.makedirs(self.snapshots_dir, exist_ok=True)
    
    def make_api_request(self, method: str, url: str, headers: Dict, data: Dict = None, 
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
    
    def get_workflows_list(self) -> List[Dict]:
        """Get list of workflows from the source location"""
        headers = {
            "Authorization": f"Bearer {self.solar_token}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        success, response = self.make_api_request(
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
    
    def create_workflow_snapshots(self, workflows: List[Dict]) -> List[str]:
        """Create workflow snapshots for all workflows"""
        snapshot_files = []
        
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
            safe_name = workflow_name.replace(":", "").replace("/", "_").replace("\\", "_").replace("?", "_").replace("*", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_").replace(" ", "_")
            safe_filename = f"{safe_name}_{workflow_id[-8:]}.json"
            
            # Save the snapshot directly with our own implementation
            import os
            import json
            
            filepath = os.path.join(self.snapshots_dir, safe_filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
            
            snapshot_files.append(filepath)
            logger.info(f"Saved workflow snapshot to {filepath}")
        
        return snapshot_files
    
    def clone_location(self, target_name: str) -> Tuple[bool, Optional[str], Dict]:
        """Clone the location using the manual_clone_location function"""
        logger.info(f"Cloning location {self.source_location_id} to {target_name}")
        
        result = manual_clone_location(
            source_location_id=self.source_location_id,
            new_location_name=target_name,
            access_token=self.agency_token
        )
        
        if result.get("success", False) and "new_location_id" in result:
            logger.info(f"Successfully cloned location. New ID: {result['new_location_id']}")
            return True, result["new_location_id"], result
        else:
            logger.error(f"Failed to clone location: {result.get('error', 'Unknown error')}")
            return False, None, result
    
    def execute_full_clone(self, target_name: str) -> Dict:
        """Execute the full cloning process"""
        start_time = datetime.now()
        logger.info(f"Starting full clone process at {start_time}")
        
        result = {
            "success": False,
            "start_time": start_time.isoformat(),
            "source_location_id": self.source_location_id,
            "target_name": target_name,
            "steps": []
        }
        
        # Step 1: Get workflows list
        logger.info("Step 1: Getting workflows list")
        workflows = self.get_workflows_list()
        
        result["steps"].append({
            "step": "get_workflows",
            "success": len(workflows) > 0,
            "count": len(workflows)
        })
        
        if not workflows:
            logger.error("No workflows found. Aborting clone process.")
            result["error"] = "No workflows found"
            result["end_time"] = datetime.now().isoformat()
            return result
        
        # Step 2: Create workflow snapshots
        logger.info("Step 2: Creating workflow snapshots")
        snapshot_files = self.create_workflow_snapshots(workflows)
        
        result["steps"].append({
            "step": "create_snapshots",
            "success": len(snapshot_files) > 0,
            "count": len(snapshot_files),
            "files": snapshot_files
        })
        
        # Step 3: Clone the location
        logger.info("Step 3: Cloning location")
        clone_success, new_location_id, clone_result = self.clone_location(target_name)
        
        result["steps"].append({
            "step": "clone_location",
            "success": clone_success,
            "new_location_id": new_location_id,
            "details": clone_result
        })
        
        if not clone_success:
            logger.error("Location cloning failed. Aborting clone process.")
            result["error"] = "Location cloning failed"
            result["end_time"] = datetime.now().isoformat()
            return result
        
        # Final result
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result.update({
            "success": True,
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "new_location_id": new_location_id,
            "workflow_count": len(workflows),
            "snapshot_count": len(snapshot_files),
            "message": f"Successfully cloned location and documented {len(workflows)} workflows"
        })
        
        logger.info(f"Clone process completed successfully in {duration} seconds")
        return result


def clone_solar_sub_account(source_location_id: str, target_name: str) -> Dict:
    """Convenience function to clone a Solar sub-account"""
    cloner = IntegratedCloneSolution(source_location_id)
    return cloner.execute_full_clone(target_name)


if __name__ == "__main__":
    # Example usage
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar sub-account ID
    target_name = f"Solar Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"🚀 Integrated Solar Sub-Account Cloning")
    print("=" * 50)
    print(f"Source Location: {source_location_id}")
    print(f"Target Name: {target_name}")
    print("=" * 50)
    
    result = clone_solar_sub_account(source_location_id, target_name)
    
    print("\n📊 Clone Results:")
    print("=" * 30)
    print(f"Success: {'✅' if result['success'] else '❌'}")
    
    if result['success']:
        print(f"New Location ID: {result['new_location_id']}")
        print(f"Workflows Documented: {result['workflow_count']}")
        print(f"Duration: {result['duration_seconds']:.2f} seconds")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("\n📝 Step Results:")
    for step in result['steps']:
        print(f"  - {step['step']}: {'✅' if step['success'] else '❌'}")
