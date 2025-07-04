#!/usr/bin/env python3
"""
Manual cloning of GoHighLevel sub-accounts by retrieving configuration and creating a new one
"""

import requests
import time
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ghl_manual_clone")

def get_location_details(location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed information about a GoHighLevel location
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Fetching details for location {location_id}...")
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/locations/{location_id}",
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            return {
                "success": True,
                "location_details": response.json()
            }
        else:
            logger.error(f"Failed to get location details: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": "Failed to get location details",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        logger.exception(f"Error getting location details: {str(e)}")
        return {
            "success": False,
            "error": f"Error getting location details: {str(e)}",
            "exception_type": type(e).__name__
        }

def get_custom_values(location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get custom values for a GoHighLevel location
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Fetching custom values for location {location_id}...")
        response = requests.get(
            f"https://rest.gohighlevel.com/v1/locations/{location_id}/customValues",
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            return {
                "success": True,
                "custom_values": response.json()
            }
        else:
            logger.warning(f"Failed to get custom values: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": "Failed to get custom values",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        logger.exception(f"Error getting custom values: {str(e)}")
        return {
            "success": False,
            "error": f"Error getting custom values: {str(e)}",
            "exception_type": type(e).__name__
        }

def check_workflows(location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempt to check for workflows in a GoHighLevel location
    
    Note: This function attempts to access workflows through multiple API endpoints,
    but current API limitations may prevent successful retrieval.
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Try different API endpoints for workflows
    endpoints = [
        "https://rest.gohighlevel.com/v1/workflows/",  # Base workflows endpoint
        f"https://rest.gohighlevel.com/v1/locations/{location_id}/workflows",
        f"https://rest.gohighlevel.com/v1/workflows?locationId={location_id}",
        f"https://rest.gohighlevel.com/v2/locations/{location_id}/workflows"
    ]
    
    results = []
    
    for endpoint in endpoints:
        try:
            logger.info(f"Checking for workflows using endpoint: {endpoint}")
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"Response status code: {response.status_code}")
            
            result = {
                "endpoint": endpoint,
                "status_code": response.status_code
            }
            
            if response.status_code == 200:
                try:
                    result["data"] = response.json()
                    logger.info(f"Successfully retrieved workflow data from {endpoint}")
                    return {
                        "success": True,
                        "workflows": result["data"],
                        "endpoint": endpoint
                    }
                except:
                    result["error"] = "Could not parse JSON response"
            else:
                result["error"] = f"Failed with status {response.status_code}"
                if response.text:
                    try:
                        result["response"] = response.json()
                    except:
                        result["response"] = response.text[:200]
            
            results.append(result)
            
        except Exception as e:
            logger.exception(f"Error checking workflows with endpoint {endpoint}: {str(e)}")
            results.append({
                "endpoint": endpoint,
                "error": str(e),
                "exception_type": type(e).__name__
            })
    
    logger.warning("Could not access workflows through any API endpoint")
    return {
        "success": False,
        "error": "Could not access workflows through any API endpoint",
        "attempts": results
    }

def create_location(location_data: Dict[str, Any], access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new GoHighLevel location
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Extract only the necessary fields for creating a new location
    create_payload = {
        "name": location_data.get("name", "") + " (Clone)",
        "email": location_data.get("email", ""),
        "businessName": location_data.get("businessName") or location_data.get("name", "") + " (Clone)",
        "address": location_data.get("address"),
        "phone": location_data.get("phone"),
        "timezone": location_data.get("timezone"),
        "country": location_data.get("country"),
        "website": location_data.get("website")
    }
    
    # Remove None values
    create_payload = {k: v for k, v in create_payload.items() if v is not None}
    
    try:
        logger.info(f"Creating new location with name: {create_payload.get('name')}")
        logger.debug(f"Payload: {json.dumps(create_payload)}")
        
        response = requests.post(
            "https://rest.gohighlevel.com/v1/locations/",
            json=create_payload,
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200 or response.status_code == 201:
            new_location = response.json()
            logger.info(f"Successfully created location with ID: {new_location.get('id')}")
            return {
                "success": True,
                "new_location": new_location
            }
        else:
            logger.error(f"Failed to create location: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": "Failed to create location",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        logger.exception(f"Error creating location: {str(e)}")
        return {
            "success": False,
            "error": f"Error creating location: {str(e)}",
            "exception_type": type(e).__name__
        }

def update_custom_values(location_id: str, custom_values: Dict[str, Any], access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Update custom values for a GoHighLevel location
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Updating custom values for location {location_id}...")
        logger.debug(f"Custom values: {json.dumps(custom_values)}")
        
        response = requests.post(
            f"https://rest.gohighlevel.com/v1/locations/{location_id}/customValues",
            json=custom_values,
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            return {
                "success": True,
                "updated_custom_values": response.json()
            }
        else:
            logger.warning(f"Failed to update custom values: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": "Failed to update custom values",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        logger.exception(f"Error updating custom values: {str(e)}")
        return {
            "success": False,
            "error": f"Error updating custom values: {str(e)}",
            "exception_type": type(e).__name__
        }

def manual_clone_location(source_location_id: str, new_location_name: Optional[str] = None, 
                         new_location_email: Optional[str] = None, custom_values: Optional[Dict[str, str]] = None,
                         access_token: Optional[str] = None, wait_time: int = 5) -> Dict[str, Any]:
    """
    Manually clone a GoHighLevel location by retrieving its configuration and creating a new one
    
    Args:
        source_location_id: ID of the source location to clone
        new_location_name: Name for the new location (optional, will use source name + " (Clone)" if not provided)
        new_location_email: Email for the new location (optional, will use source email if not provided)
        custom_values: Dictionary of custom values to set on the new location
        access_token: GoHighLevel API token (optional, will use Agency_Api_Key if not provided)
        wait_time: Time to wait after creating the location before updating custom values
        
    Returns:
        Dictionary with success status and new location details or error information
        
    Note:
        This function does not currently clone workflows due to API limitations.
        Workflows will need to be manually recreated in the new location.
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
    
    logger.info(f"Starting manual clone of location {source_location_id}")
    
    # Step 1: Get source location details
    source_details_result = get_location_details(source_location_id, access_token)
    if not source_details_result.get("success"):
        logger.error(f"Failed to get source location details: {source_details_result.get('error')}")
        return source_details_result
    
    source_details = source_details_result.get("location_details", {})
    logger.info(f"Successfully retrieved source location details: {source_details.get('name')}")
    
    # Step 2: Get source location custom values
    source_custom_values_result = get_custom_values(source_location_id, access_token)
    source_custom_values = {}
    if source_custom_values_result.get("success"):
        source_custom_values = source_custom_values_result.get("custom_values", {})
        logger.info(f"Successfully retrieved source location custom values")
    else:
        logger.warning(f"Could not retrieve source location custom values: {source_custom_values_result.get('error')}")
    
    # Step 3: Check for workflows (for information purposes only)
    workflow_check_result = check_workflows(source_location_id, access_token)
    has_workflows = workflow_check_result.get("success", False)
    
    # Step 4: Prepare new location data
    new_location_data = dict(source_details)
    if new_location_name:
        new_location_data["name"] = new_location_name
    else:
        new_location_data["name"] = source_details.get("name", "") + " (Clone)"
        
    if new_location_email:
        new_location_data["email"] = new_location_email
    
    # Step 5: Create new location
    create_result = create_location(new_location_data, access_token)
    if not create_result.get("success"):
        logger.error(f"Failed to create new location: {create_result.get('error')}")
        return create_result
    
    new_location = create_result.get("new_location", {})
    new_location_id = new_location.get("id")
    
    if not new_location_id:
        logger.error("No location ID returned from create operation")
        return {
            "success": False,
            "error": "No location ID returned from create operation",
            "response": new_location
        }
    
    logger.info(f"Successfully created new location with ID: {new_location_id}")
    
    # Step 6: Wait for the location to be fully created
    logger.info(f"Waiting {wait_time} seconds for the location to be ready...")
    time.sleep(wait_time)
    
    # Step 7: Update custom values
    result = {
        "success": True,
        "new_location_id": new_location_id,
        "new_location": new_location,
        "custom_values_updated": False
    }
    
    # Step 8: Attempt to clone workflows if they exist
    if has_workflows:
        logger.info("Workflows found in source location. Attempting to clone...")
        workflow_clone_result = attempt_clone_workflows(
            source_location_id=source_location_id,
            target_location_id=new_location_id,
            access_token=access_token
        )
        
        result["workflow_status"] = {
            "checked": True,
            "found": True,
            "clone_attempted": True,
            "clone_result": workflow_clone_result
        }
        
        if workflow_clone_result.get("success"):
            workflows_cloned = workflow_clone_result.get("workflows_cloned", 0)
            if workflows_cloned > 0:
                result["workflow_status"]["note"] = f"Successfully cloned {workflows_cloned} workflows."
            else:
                result["workflow_status"]["note"] = "No workflows were cloned. They may need to be manually recreated."
        else:
            result["workflow_status"]["note"] = "Attempted to clone workflows but encountered issues. Workflows must be manually recreated."
    else:
        result["workflow_status"] = {
            "checked": True,
            "found": False,
            "note": "No workflows found in source location."
        }
        
    # Add specific note about the workflow ID that needs to be manually copied
    result["workflow_status"]["important_workflows"] = [
        {
            "id": "943eafb8-04c4-4a96-89c5-c2d44f8b9278",
            "note": "This specific workflow needs to be manually recreated in the new location. API access is not available for this workflow."
        }
    ]
    
    # Combine source custom values with provided custom values
    final_custom_values = dict(source_custom_values)
    if custom_values:
        final_custom_values.update(custom_values)
    
    if final_custom_values:
        custom_values_result = update_custom_values(new_location_id, final_custom_values, access_token)
        result["custom_values_result"] = custom_values_result
        result["custom_values_updated"] = custom_values_result.get("success", False)
        
        if not custom_values_result.get("success", False):
            logger.warning(f"Failed to update custom values: {custom_values_result.get('error')}")
            result["warnings"] = result.get("warnings", []) + ["Custom values could not be updated"]
    
    logger.info(f"Manual clone completed successfully: {new_location_id}")
    return result

def attempt_clone_workflows(source_location_id: str, target_location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempt to clone workflows from source location to target location.
    
    Note: This is an experimental function as the current API key may not have
    sufficient permissions to access or clone workflows.
    
    Args:
        source_location_id (str): Source location ID to clone workflows from
        target_location_id (str): Target location ID to clone workflows to
        access_token (str, optional): Bearer token for authorization
        
    Returns:
        dict: Response containing workflow cloning results
    """
    logger.info(f"Attempting to clone workflows from {source_location_id} to {target_location_id}")
    
    if access_token is None:
        access_token = Constant.Agency_Api_Key
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Step 1: Try to get source workflows
    source_workflows_result = check_workflows(source_location_id, access_token)
    
    if not source_workflows_result.get("success"):
        logger.warning("Could not access source workflows. Cloning workflows not possible.")
        return {
            "success": False,
            "error": "Could not access source workflows",
            "source_check_result": source_workflows_result,
            "note": "The current API key does not have permissions to access workflows. Workflows must be manually recreated."
        }
    
    source_workflows = source_workflows_result.get("workflows", [])
    successful_endpoint = source_workflows_result.get("endpoint")
    
    if not source_workflows:
        logger.info("No workflows found in source location")
        return {
            "success": True,
            "message": "No workflows found to clone",
            "workflows_cloned": 0
        }
    
    # Step 2: Try to clone each workflow
    cloned_workflows = []
    failed_workflows = []
    
    # Determine if we're dealing with a list or dict structure
    workflows_to_clone = []
    if isinstance(source_workflows, list):
        workflows_to_clone = source_workflows
    elif isinstance(source_workflows, dict) and "workflows" in source_workflows:
        workflows_to_clone = source_workflows["workflows"]
    
    for workflow in workflows_to_clone:
        try:
            # Extract workflow ID and data
            workflow_id = workflow.get("id")
            
            if not workflow_id:
                logger.warning(f"Workflow missing ID: {workflow}")
                failed_workflows.append({
                    "workflow": workflow,
                    "error": "Missing workflow ID"
                })
                continue
            
            # Create a copy of the workflow for the target location
            workflow_copy = workflow.copy()
            
            # Update location ID to target location
            if "locationId" in workflow_copy:
                workflow_copy["locationId"] = target_location_id
            
            # Remove any read-only fields that might cause issues
            for field in ["id", "createdAt", "updatedAt"]:
                if field in workflow_copy:
                    del workflow_copy[field]
            
            # Try to create the workflow in the target location
            logger.info(f"Attempting to create workflow in target location: {workflow.get('name', 'Unnamed')}")
            
            # Use the same endpoint pattern that worked for getting workflows
            create_endpoint = "https://rest.gohighlevel.com/v1/workflows/"
            
            response = requests.post(
                create_endpoint,
                headers=headers,
                json=workflow_copy,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully cloned workflow: {workflow.get('name', 'Unnamed')}")
                cloned_workflows.append({
                    "original_id": workflow_id,
                    "name": workflow.get("name", "Unnamed"),
                    "new_workflow": response.json()
                })
            else:
                logger.warning(f"Failed to clone workflow {workflow_id}: {response.status_code} - {response.text}")
                failed_workflows.append({
                    "workflow_id": workflow_id,
                    "name": workflow.get("name", "Unnamed"),
                    "status_code": response.status_code,
                    "error": response.text
                })
                
        except Exception as e:
            logger.exception(f"Error cloning workflow: {str(e)}")
            failed_workflows.append({
                "workflow_id": workflow.get("id", "Unknown"),
                "name": workflow.get("name", "Unnamed"),
                "error": str(e),
                "exception_type": type(e).__name__
            })
    
    # Return results
    total_workflows = len(workflows_to_clone)
    successful_clones = len(cloned_workflows)
    
    logger.info(f"Workflow cloning complete. {successful_clones}/{total_workflows} workflows cloned successfully")
    
    # Generate workflow documentation for manual recreation
    try:
        from GHL.Sub_Accounts.generate_workflow_docs import generate_workflow_documentation
        docs = generate_workflow_documentation(source_location_id, target_location_id, access_token)
        logger.info("Generated workflow documentation for manual recreation")
    except Exception as e:
        logger.warning(f"Could not generate workflow documentation: {str(e)}")
        docs = {
            "note": "Could not generate workflow documentation. Please manually recreate workflows.",
            "important_workflows": [
                {
                    "id": "943eafb8-04c4-4a96-89c5-c2d44f8b9278",
                    "note": "This specific workflow needs to be manually recreated in the new location."
                }
            ]
        }
    
    return {
        "success": successful_clones > 0,
        "total_workflows": total_workflows,
        "workflows_cloned": successful_clones,
        "cloned_workflows": cloned_workflows,
        "failed_workflows": failed_workflows,
        "note": "Workflow cloning is experimental and may not work with all API keys.",
        "manual_documentation": docs
    }

# Example usage
if __name__ == "__main__":
    print("This module provides functions for manually cloning GoHighLevel locations")
    print("Note: Workflows cannot be automatically cloned due to API limitations")
    print("Please manually recreate workflows in the new location after cloning")
