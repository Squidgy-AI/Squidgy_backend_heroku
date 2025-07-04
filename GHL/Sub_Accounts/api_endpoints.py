import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Import required modules
from GHL.Sub_Accounts.clone_with_documentation import clone_with_workflow_documentation
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

logger = logging.getLogger('ghl_api')

# Create API router
router = APIRouter(prefix="/api/ghl", tags=["GoHighLevel"])

# Define request models
class GHLCloneWithDocumentationRequest(BaseModel):
    source_location_id: str
    new_location_name: str
    new_location_email: str
    custom_values: Optional[Dict[str, str]] = None
    plan_id: Optional[str] = None
    sub_account_type: Optional[str] = "location"
    access_token: Optional[str] = None
    wait_time: Optional[int] = 5
    document_workflows: Optional[bool] = True

class GHLWorkflowDocumentationRequest(BaseModel):
    location_id: str
    workflow_ids: Optional[List[str]] = None  # If None, document all workflows
    access_token: Optional[str] = None

# Define API endpoints
@router.post("/clone-with-documentation")
async def clone_with_documentation(request: GHLCloneWithDocumentationRequest, background_tasks: BackgroundTasks):
    """
    Clone a GoHighLevel location and document workflows that can't be automatically cloned
    """
    try:
        # Create output directory
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "workflow_documentation",
            f"{request.new_location_name.replace(' ', '_').lower()}_{request.source_location_id}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # Use the provided access token or default to agency API key
        access_token = request.access_token or Constant.Agency_Api_Key
        
        # Clone the location with workflow documentation
        result = clone_with_workflow_documentation(
            source_location_id=request.source_location_id,
            new_location_name=request.new_location_name,
            new_location_email=request.new_location_email,
            custom_values=request.custom_values,
            plan_id=request.plan_id,
            sub_account_type=request.sub_account_type,
            access_token=access_token,
            wait_time=request.wait_time,
            document_workflows=request.document_workflows,
            output_dir=output_dir
        )
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Unknown error"),
            "new_location_id": result.get("new_location_id"),
            "workflow_status": result.get("workflow_status"),
            "workflow_notes": result.get("workflow_notes", []),
            "documentation_path": output_dir if request.document_workflows else None
        }
    except Exception as e:
        logger.error(f"Error in clone-with-documentation endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/document-workflows")
async def document_workflows(request: GHLWorkflowDocumentationRequest):
    """
    Document workflows for a GoHighLevel location
    """
    try:
        # Create output directory
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "workflow_documentation",
            f"location_{request.location_id}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # Use the provided access token or determine based on location
        access_token = request.access_token
        if not access_token:
            # Use Solar access token for Solar location
            if request.location_id == "JUTFTny8EXQOSB5NcvAA":  # Solar location ID
                access_token = Constant.Solar_Access_Token
            else:
                access_token = Constant.Agency_Api_Key
        
        # Initialize the workflow documentation helper
        doc_helper = WorkflowDocumentation(access_token)
        
        # Get workflow IDs if not provided
        workflow_ids = request.workflow_ids
        if not workflow_ids:
            workflows = doc_helper.get_workflow_list(request.location_id)
            workflow_ids = [w["id"] for w in workflows]
        
        if not workflow_ids:
            return {
                "success": False,
                "message": "No workflows found to document",
                "documentation_path": None
            }
        
        # Create a recreation guide for all workflows
        result = doc_helper.create_recreation_guide(
            workflow_ids=workflow_ids,
            location_id=request.location_id,
            output_dir=output_dir
        )
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Unknown error"),
            "workflow_count": len(workflow_ids),
            "documentation_path": output_dir,
            "guide_filepath": result.get("guide", {}).get("filepath") if result.get("guide") else None
        }
    except Exception as e:
        logger.error(f"Error in document-workflows endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
