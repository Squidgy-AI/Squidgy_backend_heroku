import os
import sys
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('workflow_documentation')

class WorkflowDocumentation:
    def __init__(self, access_token: str):
        """
        Initialize the workflow documentation helper
        
        Args:
            access_token: The access token for the GoHighLevel API
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_workflow_list(self, location_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of all workflows for a location
        
        Args:
            location_id: The ID of the location
            
        Returns:
            A list of workflow objects
        """
        logger.info(f"Fetching workflows for location {location_id}...")
        
        try:
            response = requests.get(
                "https://rest.gohighlevel.com/v1/workflows",
                headers=self.headers,
                timeout=30
            )
            
            logger.info(f"API request to workflows - Status: {response.status_code}")
            
            if response.status_code == 200:
                workflows = response.json().get('workflows', [])
                # Filter workflows for the specific location
                location_workflows = [w for w in workflows if w.get('locationId') == location_id]
                logger.info(f"Found {len(location_workflows)} workflows for location {location_id}")
                return location_workflows
            else:
                logger.warning(f"API error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error fetching workflows: {str(e)}")
            return []
    
    def get_workflow_details(self, workflow_id: str, location_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific workflow
        
        Args:
            workflow_id: The ID of the workflow
            location_id: The ID of the location
            
        Returns:
            A dictionary containing workflow details or None if not found
        """
        logger.info(f"Fetching details for workflow {workflow_id}...")
        
        # Try different API endpoints to get workflow details
        endpoints = [
            f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
            f"https://rest.gohighlevel.com/v1/locations/{location_id}/workflows/{workflow_id}",
            f"https://rest.gohighlevel.com/v1/workflows?locationId={location_id}&id={workflow_id}"
        ]
        
        workflow_details = None
        
        # First, get the basic workflow info from the list of workflows
        workflows = self.get_workflow_list(location_id)
        for workflow in workflows:
            if workflow.get('id') == workflow_id:
                workflow_details = workflow
                logger.info(f"Found basic workflow info: {workflow.get('name', 'Unknown')}")
                break
        
        # Try to get detailed workflow information
        if not workflow_details:
            for endpoint in endpoints:
                try:
                    logger.info(f"Trying endpoint: {endpoint}")
                    response = requests.get(endpoint, headers=self.headers, timeout=30)
                    logger.info(f"API request to {endpoint} - Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        detailed_info = response.json()
                        if isinstance(detailed_info, dict) and 'id' in detailed_info:
                            workflow_details = detailed_info
                        elif isinstance(detailed_info, dict) and 'workflows' in detailed_info:
                            for wf in detailed_info['workflows']:
                                if wf.get('id') == workflow_id:
                                    workflow_details = wf
                                    break
                        logger.info(f"Successfully retrieved workflow details: {workflow_details.get('name', 'Unknown') if workflow_details else 'No details found'}")
                        break
                    else:
                        logger.warning(f"API error: {response.status_code} - {response.text}")
                except Exception as e:
                    logger.error(f"Error fetching workflow details: {str(e)}")
        
        # If we have basic workflow info, try to get triggers and actions
        if workflow_details:
            try:
                triggers_endpoint = f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/triggers"
                logger.info(f"Fetching workflow triggers from: {triggers_endpoint}")
                response = requests.get(triggers_endpoint, headers=self.headers, timeout=30)
                logger.info(f"API request to {triggers_endpoint} - Status: {response.status_code}")
                
                if response.status_code == 200:
                    workflow_details['triggers'] = response.json()
                    logger.info("Successfully retrieved workflow triggers")
                else:
                    logger.warning(f"API error when fetching triggers: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Error fetching workflow triggers: {str(e)}")
                
            try:
                actions_endpoint = f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}/actions"
                logger.info(f"Fetching workflow actions from: {actions_endpoint}")
                response = requests.get(actions_endpoint, headers=self.headers, timeout=30)
                logger.info(f"API request to {actions_endpoint} - Status: {response.status_code}")
                
                if response.status_code == 200:
                    workflow_details['actions'] = response.json()
                    logger.info("Successfully retrieved workflow actions")
                else:
                    logger.warning(f"API error when fetching actions: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Error fetching workflow actions: {str(e)}")
        
        return workflow_details
    
    def create_workflow_documentation(self, workflow_id: str, location_id: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Create documentation for a workflow
        
        Args:
            workflow_id: The ID of the workflow
            location_id: The ID of the location
            output_dir: Optional directory to save the documentation
            
        Returns:
            A dictionary containing the documentation
        """
        # Get workflow details
        workflow_details = self.get_workflow_details(workflow_id, location_id)
        
        if not workflow_details:
            logger.warning(f"Could not find workflow {workflow_id}")
            return {
                "success": False,
                "message": f"Could not find workflow {workflow_id}",
                "documentation": None
            }
        
        # Create documentation
        documentation = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_details.get("name", "Unknown Workflow"),
            "status": workflow_details.get("status", "unknown"),
            "version": workflow_details.get("version", 0),
            "created_at": workflow_details.get("createdAt", ""),
            "updated_at": workflow_details.get("updatedAt", ""),
            "location_id": location_id,
            "documentation_created": datetime.now().isoformat(),
            "recreation_steps": [
                "1. Log into GoHighLevel dashboard at https://app.gohighlevel.com/",
                "2. Navigate to the target location",
                "3. Go to Automations > Workflows",
                "4. Click '+ New Workflow' to create a new workflow",
                f"5. Name the workflow '{workflow_details.get('name', 'Unknown Workflow')}'",
                "6. Configure the workflow with the triggers and actions detailed below"
            ],
            "triggers": workflow_details.get("triggers", {}),
            "actions": workflow_details.get("actions", {}),
            "notes": [
                f"This workflow documentation was automatically generated for workflow ID {workflow_id}",
                "Due to GoHighLevel API limitations, this workflow must be manually recreated in the target location",
                "Take screenshots of the workflow configuration to assist with manual recreation"
            ],
            "screenshot_paths": []
        }
        
        # Save documentation if output_dir is provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename
            workflow_name = workflow_details.get("name", "unknown_workflow")
            safe_name = "".join([c if c.isalnum() else "_" for c in workflow_name]).lower()
            filename = f"{safe_name}_{workflow_id[:8]}_documentation.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w") as f:
                json.dump(documentation, f, indent=2)
            
            logger.info(f"Saved workflow documentation to {filepath}")
            documentation["filepath"] = filepath
        
        return {
            "success": True,
            "message": f"Successfully created documentation for workflow {workflow_id}",
            "documentation": documentation
        }
    
    def create_recreation_guide(self, workflow_ids: List[str], location_id: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Create a recreation guide for multiple workflows
        
        Args:
            workflow_ids: List of workflow IDs to document
            location_id: The ID of the location
            output_dir: Optional directory to save the guide
            
        Returns:
            A dictionary containing the recreation guide
        """
        logger.info(f"Creating recreation guide for {len(workflow_ids)} workflows in location {location_id}...")
        
        # Get location details
        try:
            response = requests.get(
                f"https://rest.gohighlevel.com/v1/locations/{location_id}",
                headers=self.headers,
                timeout=30
            )
            
            logger.info(f"API request to locations/{location_id} - Status: {response.status_code}")
            
            if response.status_code == 200:
                location_details = response.json()
                location_name = location_details.get("name", "Unknown Location")
                logger.info(f"Successfully retrieved location details: {location_name}")
            else:
                logger.warning(f"API error: {response.status_code} - {response.text}")
                location_name = "Unknown Location"
        except Exception as e:
            logger.error(f"Error fetching location details: {str(e)}")
            location_name = "Unknown Location"
        
        # Create documentation for each workflow
        workflow_docs = []
        for workflow_id in workflow_ids:
            result = self.create_workflow_documentation(workflow_id, location_id)
            if result["success"]:
                workflow_docs.append(result["documentation"])
        
        # Create the recreation guide
        guide = {
            "location_id": location_id,
            "location_name": location_name,
            "creation_date": datetime.now().isoformat(),
            "workflows": workflow_docs,
            "general_steps": [
                "1. Log into GoHighLevel dashboard at https://app.gohighlevel.com/",
                "2. Navigate to the target location",
                "3. Follow the steps for each workflow below"
            ],
            "notes": [
                "Due to GoHighLevel API limitations, these workflows must be manually recreated in the target location",
                "Take screenshots of each workflow configuration to assist with manual recreation"
            ]
        }
        
        # Save guide if output_dir is provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename
            safe_name = "".join([c if c.isalnum() else "_" for c in location_name]).lower()
            filename = f"{safe_name}_{location_id[:8]}_workflow_recreation_guide.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w") as f:
                json.dump(guide, f, indent=2)
            
            logger.info(f"Saved workflow recreation guide to {filepath}")
            guide["filepath"] = filepath
        
        return {
            "success": True,
            "message": f"Successfully created recreation guide for {len(workflow_docs)} workflows",
            "guide": guide
        }
