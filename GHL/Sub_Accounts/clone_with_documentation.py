import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Import required modules
from GHL.Sub_Accounts.clone_sub_acc import clone_sub_account
from GHL.Sub_Accounts.workflow_documentation import WorkflowDocumentation
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('clone_with_documentation')

def clone_with_workflow_documentation(
    source_location_id: str,
    new_location_name: str,
    new_location_email: str,
    custom_values: Optional[Dict[str, str]] = None,
    plan_id: Optional[str] = None,
    sub_account_type: str = "location",
    access_token: Optional[str] = None,
    wait_time: int = 5,
    document_workflows: bool = True,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clone a GoHighLevel location and document workflows that can't be automatically cloned
    
    Args:
        source_location_id: The ID of the source location to clone
        new_location_name: Name for the new location
        new_location_email: Email for the new location
        custom_values: Optional dictionary of custom values to set
        plan_id: Optional plan ID for the new location
        sub_account_type: Type of sub-account (default: "location")
        access_token: Optional access token (will use Agency_Api_Key if not provided)
        wait_time: Time to wait between API calls in seconds
        document_workflows: Whether to document workflows (default: True)
        output_dir: Directory to save workflow documentation
        
    Returns:
        Dictionary with clone results and workflow documentation
    """
    logger.info(f"Cloning location {source_location_id} with workflow documentation...")
    
    # Use the agency API key if no access token is provided
    if not access_token:
        access_token = Constant.Agency_Api_Key
    
    # Clone the location
    clone_result = clone_sub_account(
        source_location_id=source_location_id,
        new_location_name=new_location_name,
        new_location_email=new_location_email,
        custom_values=custom_values,
        plan_id=plan_id,
        sub_account_type=sub_account_type,
        access_token=access_token,
        wait_time=wait_time
    )
    
    # Check if cloning was successful
    if not clone_result.get("success", False):
        logger.error(f"Failed to clone location: {clone_result.get('message', 'Unknown error')}")
        return clone_result
    
    # Get the new location ID
    new_location_id = clone_result.get("new_location_id")
    logger.info(f"Successfully cloned location. New location ID: {new_location_id}")
    
    # Document workflows if requested
    workflow_documentation = None
    if document_workflows:
        logger.info("Documenting workflows that can't be automatically cloned...")
        
        # Create output directory if not provided
        if not output_dir:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "workflow_documentation",
                f"{new_location_name.replace(' ', '_').lower()}_{new_location_id}"
            )
            os.makedirs(output_dir, exist_ok=True)
        
        # Use the source location's access token if available
        source_token = None
        if source_location_id == "JUTFTny8EXQOSB5NcvAA":  # Solar location ID
            source_token = Constant.Solar_Access_Token
        else:
            source_token = access_token
        
        # Create workflow documentation
        try:
            # Initialize the workflow documentation helper
            doc_helper = WorkflowDocumentation(source_token)
            
            # Get all workflows for the source location
            workflows = doc_helper.get_workflow_list(source_location_id)
            workflow_ids = [w["id"] for w in workflows]
            
            # Create a recreation guide for all workflows
            if workflow_ids:
                workflow_documentation = doc_helper.create_recreation_guide(
                    workflow_ids=workflow_ids,
                    location_id=source_location_id,
                    output_dir=output_dir
                )
                
                logger.info(f"Created documentation for {len(workflow_ids)} workflows")
                
                # Add workflow documentation to clone result
                clone_result["workflow_documentation"] = workflow_documentation
                clone_result["workflow_status"] = "manual_recreation_required"
                clone_result["workflow_notes"] = [
                    "Workflows require manual recreation due to GoHighLevel API limitations",
                    f"Workflow documentation has been saved to {output_dir}"
                ]
            else:
                logger.info("No workflows found to document")
                clone_result["workflow_status"] = "no_workflows_found"
        except Exception as e:
            logger.error(f"Error documenting workflows: {str(e)}")
            clone_result["workflow_status"] = "documentation_error"
            clone_result["workflow_error"] = str(e)
    
    return clone_result
