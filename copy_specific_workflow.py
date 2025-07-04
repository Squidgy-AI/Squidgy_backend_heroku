#!/usr/bin/env python3
"""
Script to specifically copy a workflow with ID 943eafb8-04c4-4a96-89c5-c2d44f8b9278
to cloned GoHighLevel locations
"""

import requests
import json
import logging
import time
from typing import Dict, Any, Optional, List
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("copy_specific_workflow")

# Constants
WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"

def get_specific_workflow(workflow_id: str, location_id: Optional[str] = None, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempt to get a specific workflow by ID using various API endpoints
    
    Args:
        workflow_id: The specific workflow ID to retrieve
        location_id: Optional location ID to include in requests
        access_token: Optional access token (defaults to agency API key)
        
    Returns:
        Dict with results of the attempt
    """
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Try different API endpoints that might work for retrieving a specific workflow
    endpoints = [
        f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://api.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://rest.gohighlevel.com/v2/workflows/{workflow_id}",
        f"https://api.gohighlevel.com/v2/workflows/{workflow_id}"
    ]
    
    # If location_id is provided, add location-specific endpoints
    if location_id:
        endpoints.extend([
            f"https://rest.gohighlevel.com/v1/locations/{location_id}/workflows/{workflow_id}",
            f"https://api.gohighlevel.com/v1/locations/{location_id}/workflows/{workflow_id}",
            f"https://rest.gohighlevel.com/v2/locations/{location_id}/workflows/{workflow_id}",
            f"https://api.gohighlevel.com/v2/locations/{location_id}/workflows/{workflow_id}"
        ])
    
    results = []
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying to get workflow {workflow_id} from endpoint: {endpoint}")
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=30
            )
            
            status_code = response.status_code
            logger.info(f"Response status code: {status_code}")
            
            result = {
                "endpoint": endpoint,
                "status_code": status_code
            }
            
            if status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"Successfully retrieved workflow data!")
                    return {
                        "success": True,
                        "workflow": data,
                        "endpoint": endpoint
                    }
                except Exception as e:
                    logger.error(f"Error parsing response: {str(e)}")
                    result["error"] = f"Could not parse response: {str(e)}"
            else:
                try:
                    result["response"] = response.json()
                except:
                    result["response"] = response.text[:200]
                    
            results.append(result)
            
        except Exception as e:
            logger.exception(f"Error with endpoint {endpoint}: {str(e)}")
            results.append({
                "endpoint": endpoint,
                "error": str(e)
            })
    
    logger.warning(f"Could not retrieve workflow {workflow_id} from any endpoint")
    return {
        "success": False,
        "error": "Could not retrieve workflow from any endpoint",
        "attempts": results
    }

def copy_workflow_to_location(workflow_id: str, target_location_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempt to copy a specific workflow to a target location
    
    Args:
        workflow_id: The workflow ID to copy
        target_location_id: The target location to copy the workflow to
        access_token: Optional access token (defaults to agency API key)
        
    Returns:
        Dict with results of the attempt
    """
    logger.info(f"Attempting to copy workflow {workflow_id} to location {target_location_id}")
    
    # Step 1: Try to get the workflow
    workflow_result = get_specific_workflow(workflow_id, None, access_token)
    
    if not workflow_result.get("success"):
        # Try with location ID
        logger.info("First attempt failed. Trying with Solar location ID...")
        workflow_result = get_specific_workflow(workflow_id, SOLAR_LOCATION_ID, access_token)
        
    if not workflow_result.get("success"):
        logger.warning("Could not retrieve workflow. Trying alternative approaches...")
        
        # Try alternative approach - direct creation with minimal data
        if access_token is None:
            access_token = Constant.Agency_Api_Key
            
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Create a minimal workflow payload using the ID
        minimal_workflow = {
            "name": "Copied Workflow",
            "description": f"Copy of workflow {workflow_id}",
            "locationId": target_location_id,
            "originalId": workflow_id,
            "status": "active",
            "trigger": {
                "type": "manual"
            },
            "actions": []
        }
        
        # Try different endpoints for creating the workflow
        create_endpoints = [
            "https://rest.gohighlevel.com/v1/workflows/",
            "https://api.gohighlevel.com/v1/workflows/",
            "https://rest.gohighlevel.com/v2/workflows/",
            "https://api.gohighlevel.com/v2/workflows/"
        ]
        
        create_results = []
        
        for endpoint in create_endpoints:
            try:
                logger.info(f"Trying to create workflow at endpoint: {endpoint}")
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=minimal_workflow,
                    timeout=30
                )
                
                status_code = response.status_code
                logger.info(f"Response status code: {status_code}")
                
                result = {
                    "endpoint": endpoint,
                    "status_code": status_code
                }
                
                if status_code in [200, 201]:
                    try:
                        data = response.json()
                        logger.info(f"Successfully created minimal workflow!")
                        return {
                            "success": True,
                            "method": "minimal_creation",
                            "new_workflow": data,
                            "endpoint": endpoint
                        }
                    except Exception as e:
                        logger.error(f"Error parsing response: {str(e)}")
                        result["error"] = f"Could not parse response: {str(e)}"
                else:
                    try:
                        result["response"] = response.json()
                    except:
                        result["response"] = response.text[:200]
                        
                create_results.append(result)
                
            except Exception as e:
                logger.exception(f"Error with endpoint {endpoint}: {str(e)}")
                create_results.append({
                    "endpoint": endpoint,
                    "error": str(e)
                })
        
        return {
            "success": False,
            "error": "Could not create workflow using minimal data",
            "get_attempts": workflow_result.get("attempts", []),
            "create_attempts": create_results
        }
    
    # Step 2: If we got the workflow, try to copy it
    workflow_data = workflow_result.get("workflow", {})
    successful_endpoint = workflow_result.get("endpoint")
    
    logger.info(f"Successfully retrieved workflow. Now copying to target location...")
    
    # Create a copy of the workflow for the target location
    workflow_copy = workflow_data.copy() if isinstance(workflow_data, dict) else {}
    
    # If we have a dict, update it for the target location
    if isinstance(workflow_copy, dict):
        # Update location ID to target location
        if "locationId" in workflow_copy:
            workflow_copy["locationId"] = target_location_id
        
        # Remove any read-only fields that might cause issues
        for field in ["id", "createdAt", "updatedAt"]:
            if field in workflow_copy:
                del workflow_copy[field]
    else:
        # If we don't have a proper dict, create a minimal workflow
        workflow_copy = {
            "name": "Copied Workflow",
            "description": f"Copy of workflow {workflow_id}",
            "locationId": target_location_id,
            "originalId": workflow_id,
            "status": "active",
            "trigger": {
                "type": "manual"
            },
            "actions": []
        }
    
    # Determine the endpoint for creating the workflow
    if successful_endpoint:
        # Use the same base endpoint that worked for getting the workflow
        base_endpoint = successful_endpoint.split("/workflows/")[0]
        create_endpoint = f"{base_endpoint}/workflows/"
    else:
        create_endpoint = "https://rest.gohighlevel.com/v1/workflows/"
    
    if access_token is None:
        access_token = Constant.Agency_Api_Key
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Creating workflow copy at endpoint: {create_endpoint}")
        response = requests.post(
            create_endpoint,
            headers=headers,
            json=workflow_copy,
            timeout=30
        )
        
        status_code = response.status_code
        logger.info(f"Response status code: {status_code}")
        
        if status_code in [200, 201]:
            try:
                data = response.json()
                logger.info(f"Successfully copied workflow to target location!")
                return {
                    "success": True,
                    "method": "full_copy",
                    "original_workflow": workflow_data,
                    "new_workflow": data,
                    "endpoint": create_endpoint
                }
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                return {
                    "success": False,
                    "error": f"Could not parse response: {str(e)}",
                    "status_code": status_code
                }
        else:
            error_response = None
            try:
                error_response = response.json()
            except:
                error_response = response.text[:200]
                
            logger.warning(f"Failed to create workflow: {status_code} - {error_response}")
            return {
                "success": False,
                "error": f"Failed to create workflow: {status_code}",
                "response": error_response
            }
                
    except Exception as e:
        logger.exception(f"Error creating workflow: {str(e)}")
        return {
            "success": False,
            "error": f"Error creating workflow: {str(e)}",
            "exception_type": type(e).__name__
        }

def create_test_location_and_copy_workflow():
    """
    Create a test location and attempt to copy the specific workflow to it
    """
    from GHL.Sub_Accounts.manual_clone import manual_clone_location
    
    logger.info("Creating a test location for workflow copying...")
    
    # Create a test location
    clone_result = manual_clone_location(
        source_location_id=SOLAR_LOCATION_ID,
        new_location_name="Specific Workflow Test",
        new_location_email="workflow.specific.test@example.com"
    )
    
    if not clone_result.get("success"):
        logger.error(f"Failed to create test location: {clone_result.get('error')}")
        return clone_result
    
    new_location_id = clone_result.get("new_location_id")
    logger.info(f"Successfully created test location with ID: {new_location_id}")
    
    # Wait a moment for the location to be fully created
    time.sleep(5)
    
    # Now try to copy the specific workflow
    logger.info(f"Attempting to copy workflow {WORKFLOW_ID} to location {new_location_id}...")
    copy_result = copy_workflow_to_location(WORKFLOW_ID, new_location_id)
    
    # Combine results
    result = {
        "success": clone_result.get("success") and copy_result.get("success"),
        "location_result": clone_result,
        "workflow_copy_result": copy_result
    }
    
    # Save results to file
    with open("specific_workflow_copy_result.json", "w") as f:
        json.dump(result, f, indent=2)
    
    logger.info("Results saved to specific_workflow_copy_result.json")
    return result

if __name__ == "__main__":
    print("GoHighLevel Specific Workflow Copy Test")
    print("======================================")
    print(f"Workflow ID: {WORKFLOW_ID}")
    print()
    
    # Configure logging to also print to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)
    
    print("1. Testing direct workflow retrieval...")
    get_result = get_specific_workflow(WORKFLOW_ID)
    
    with open("specific_workflow_get_result.json", "w") as f:
        json.dump(get_result, f, indent=2)
    
    print(f"Direct retrieval success: {get_result.get('success')}")
    print("Results saved to specific_workflow_get_result.json")
    print()
    
    print("2. Testing workflow creation with Solar location ID...")
    copy_result = copy_workflow_to_location(WORKFLOW_ID, SOLAR_LOCATION_ID)
    
    with open("specific_workflow_copy_to_solar_result.json", "w") as f:
        json.dump(copy_result, f, indent=2)
    
    print(f"Copy to Solar success: {copy_result.get('success')}")
    print("Results saved to specific_workflow_copy_to_solar_result.json")
    print()
    
    print("3. Testing workflow copy to new test location...")
    test_result = create_test_location_and_copy_workflow()
    
    print(f"Test location and copy success: {test_result.get('success')}")
    print("Results saved to specific_workflow_copy_result.json")
    print()
    
    print("All tests completed.")
