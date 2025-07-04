#!/usr/bin/env python3
"""
Pydantic models for Solar sub-account cloning
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class SolarCloneRequest(BaseModel):
    """
    Request model for Solar sub-account cloning with snapshot support
    """
    source_location_id: str
    target_name: str
    snapshot_id: Optional[str] = None  # Optional snapshot ID to try importing
    document_workflows: bool = True    # Whether to document workflows


class SolarCloneResponse(BaseModel):
    """
    Response model for Solar sub-account cloning
    """
    success: bool
    new_location_id: Optional[str] = None
    new_location_name: Optional[str] = None
    snapshot_import_attempted: bool = False
    snapshot_import_success: bool = False
    workflows_documented: int = 0
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class WorkflowListRequest(BaseModel):
    """
    Request model for listing workflows
    """
    location_id: str


class WorkflowListResponse(BaseModel):
    """
    Response model for workflow listing
    """
    success: bool
    workflows: List[Dict[str, Any]] = []
    count: int = 0
    error: Optional[str] = None
