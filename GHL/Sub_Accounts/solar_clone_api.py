#!/usr/bin/env python3
"""
FastAPI endpoints for Solar sub-account cloning
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel

# Add the project root to the Python path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from GHL.environment.constant import Constant
from GHL.Sub_Accounts.manual_clone import manual_clone_location, get_location_details
from GHL.Sub_Accounts.workflow_snapshot_helper import WorkflowSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("solar_clone_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter()


# Pydantic models for request/response
class SolarCloneRequest(BaseModel):
    source_location_id: str
    target_name: str
    snapshot_id: Optional[str] = None  # Optional snapshot ID to try importing
    document_workflows: bool = True    # Whether to document workflows


class SolarCloneResponse(BaseModel):
    success: bool
    new_location_id: Optional[str] = None
    new_location_name: Optional[str] = None
    snapshot_import_attempted: bool = False
    snapshot_import_success: bool = False
    workflows_documented: int = 0
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class WorkflowListRequest(BaseModel):
    location_id: str


class WorkflowListResponse(BaseModel):
    success: bool
    workflows: List[Dict[str, Any]] = []
    count: int = 0
    error: Optional[str] = None


@router.post("/api/ghl/solar-clone", response_model=SolarCloneResponse)
async def clone_solar_sub_account(request: SolarCloneRequest):
    """Clone a Solar sub-account with optional snapshot import"""
    try:
        logger.info(f"Received clone request for source location {request.source_location_id}")
        
        # Step 1: Clone the location using manual_clone_location
        clone_result = manual_clone_location(
            source_location_id=request.source_location_id,
            new_location_name=request.target_name,
            access_token=Constant.Agency_Api_Key
        )
        
        if not clone_result.get("success", False) or "new_location_id" not in clone_result:
            logger.error(f"Location cloning failed: {clone_result.get('error', 'Unknown error')}")
            return SolarCloneResponse(
                success=False,
                error=f"Location cloning failed: {clone_result.get('error', 'Unknown error')}",
                details=clone_result
            )
        
        new_location_id = clone_result["new_location_id"]
        logger.info(f"Successfully cloned location. New ID: {new_location_id}")
        
        # Initialize response with successful location creation
        response = SolarCloneResponse(
            success=True,
            new_location_id=new_location_id,
            new_location_name=request.target_name
        )
        
        # Step 2: Try to import snapshot if provided
        if request.snapshot_id:
            logger.info(f"Attempting to import snapshot {request.snapshot_id}")
            response.snapshot_import_attempted = True
            
            # Import logic would go here, but we know it's likely to fail based on testing
            # This is included as a placeholder for future API changes
            
            # For now, we'll just log that it was attempted but not supported
            logger.warning("Snapshot import attempted but not supported by GHL API")
        
        # Step 3: Document workflows if requested
        if request.document_workflows:
            workflows = get_workflows(request.source_location_id)
            response.workflows_documented = len(workflows)
            
            if workflows:
                # Create workflow snapshots
                snapshots_dir = os.path.join("workflow_snapshots", f"clone_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                os.makedirs(snapshots_dir, exist_ok=True)
                
                for workflow in workflows:
                    document_workflow(workflow, snapshots_dir)
                
                logger.info(f"Documented {len(workflows)} workflows to {snapshots_dir}")
            else:
                logger.warning("No workflows found to document")
        
        return response
        
    except Exception as e:
        logger.error(f"Exception in clone_solar_sub_account: {str(e)}")
        return SolarCloneResponse(
            success=False,
            error=str(e)
        )


@router.post("/api/ghl/solar-workflows", response_model=WorkflowListResponse)
async def list_solar_workflows(request: WorkflowListRequest):
    """List workflows for a Solar sub-account"""
    try:
        workflows = get_workflows(request.location_id)
        
        return WorkflowListResponse(
            success=True,
            workflows=workflows,
            count=len(workflows)
        )
        
    except Exception as e:
        logger.error(f"Exception in list_solar_workflows: {str(e)}")
        return WorkflowListResponse(
            success=False,
            error=str(e)
        )


def get_workflows(location_id: str) -> List[Dict]:
    """Get list of workflows from the source location"""
    import requests
    
    headers = {
        "Authorization": f"Bearer {Constant.Solar_Access_Token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(
            "https://rest.gohighlevel.com/v1/workflows",
            headers=headers
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
            
            logger.info(f"Found {len(workflows)} workflows")
            return workflows
        else:
            logger.error(f"Failed to get workflows: {response.status_code} - {response.text[:200]}")
            return []
            
    except Exception as e:
        logger.error(f"Exception getting workflows: {str(e)}")
        return []


def document_workflow(workflow: Dict, snapshots_dir: str) -> str:
    """Document a workflow as a snapshot file"""
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
    
    logger.info(f"Saved workflow snapshot to {filepath}")
    return filepath
