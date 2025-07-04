import os
import sys
import json
import logging
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the Constant class
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('workflow_details')

# The specific workflow ID we're interested in
TARGET_WORKFLOW_ID = '943eafb8-04c4-4a96-89c5-c2d44f8b9278'
SOLAR_LOCATION_ID = 'JUTFTny8EXQOSB5NcvAA'

def get_workflow_details(workflow_id, location_id, access_token):
    """
    Get detailed information about a specific workflow
    """
    logger.info(f"Fetching details for workflow {workflow_id}...")
    
    # Try different API endpoints to get workflow details
    endpoints = [
        f"https://rest.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://rest.gohighlevel.com/v1/locations/{location_id}/workflows/{workflow_id}",
        f"https://rest.gohighlevel.com/v1/workflows?locationId={location_id}&id={workflow_id}",
        f"https://api.gohighlevel.com/v1/workflows/{workflow_id}",
        f"https://api.gohighlevel.com/v1/locations/{location_id}/workflows/{workflow_id}"
    ]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    workflow_details = None
    
    # First, get the basic workflow info from the list of workflows
    try:
        list_endpoint = "https://rest.gohighlevel.com/v1/workflows"
        logger.info(f"Fetching list of workflows from: {list_endpoint}")
        response = requests.get(list_endpoint, headers=headers, timeout=30)
        logger.info(f"API request to {list_endpoint} - Status: {response.status_code}")
        
        if response.status_code == 200:
            workflows = response.json().get('workflows', [])
            for workflow in workflows:
                if workflow.get('id') == workflow_id:
                    workflow_details = workflow
                    logger.info(f"Found basic workflow info: {workflow.get('name', 'Unknown')}")
                    break
        else:
            logger.warning(f"API error when fetching workflows list: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error fetching workflows list: {str(e)}")
    
    # Try to get detailed workflow information
    for endpoint in endpoints:
        try:
            logger.info(f"Trying endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=30)
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
            response = requests.get(triggers_endpoint, headers=headers, timeout=30)
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
            response = requests.get(actions_endpoint, headers=headers, timeout=30)
            logger.info(f"API request to {actions_endpoint} - Status: {response.status_code}")
            
            if response.status_code == 200:
                workflow_details['actions'] = response.json()
                logger.info("Successfully retrieved workflow actions")
            else:
                logger.warning(f"API error when fetching actions: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error fetching workflow actions: {str(e)}")
    
    return workflow_details

def save_workflow_details(workflow_details, workflow_id):
    """
    Save workflow details to a JSON file
    """
    if not workflow_details:
        logger.warning("No workflow details to save")
        return
    
    # Create the directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(__file__), "solar_workflow_details")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a filename based on the workflow name
    workflow_name = workflow_details.get("name", "unknown")
    # Replace characters that are not allowed in filenames
    safe_name = "".join([c if c.isalnum() else "_" for c in workflow_name]).lower()
    filename = f"{safe_name}_{workflow_id[:8]}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Save the workflow details
    with open(filepath, "w") as f:
        json.dump(workflow_details, f, indent=2)
    
    logger.info(f"Saved workflow details to {filepath}")
    return filepath

def main():
    print("Solar Workflow Details Tool")
    print("============================")
    print(f"\nFetching details for workflow {TARGET_WORKFLOW_ID}...")
    
    # Get workflow details using the Solar access token
    workflow_details = get_workflow_details(
        workflow_id=TARGET_WORKFLOW_ID,
        location_id=SOLAR_LOCATION_ID,
        access_token=Constant.Solar_Access_Token
    )
    
    if workflow_details:
        # Save the workflow details
        filepath = save_workflow_details(workflow_details, TARGET_WORKFLOW_ID)
        print(f"\nWorkflow details saved to: {filepath}")
        print("\nNext steps:")
        print("1. Use these details to create a detailed recreation guide")
        print("2. Take screenshots of the workflow in the GoHighLevel dashboard")
        print("3. Update the recreation guide with screenshots and additional notes")
    else:
        print("\nFailed to retrieve workflow details. Check the logs for more information.")

if __name__ == "__main__":
    main()
