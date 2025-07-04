#!/usr/bin/env python3
"""
Utility to create a complete snapshot of a GoHighLevel location
including custom fields, custom values, workflows, tags, and pipelines
"""

import json
import os
import logging
import requests
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# Import with correct path
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("location_snapshot")

class LocationSnapshot:
    """
    Creates a comprehensive snapshot of a GoHighLevel location
    """
    def __init__(self, location_id: str, api_key: Optional[str] = None):
        self.location_id = location_id
        self.api_key = api_key or Constant.Agency_Api_Key
        self.snapshot_date = datetime.now()
        self.location_details = {}
        self.custom_fields = []
        self.custom_values = {}
        self.workflows = []
        self.tags = []
        self.pipelines = []
        self.forms = []
        self.templates = []
        self.notes = []
        self.screenshot_paths = []
    
    def _make_api_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an API request to GoHighLevel
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"https://rest.gohighlevel.com/v1/{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                logger.error(f"Unsupported method: {method}")
                return {"error": f"Unsupported method: {method}"}
            
            logger.info(f"API request to {endpoint} - Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"
                logger.warning(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"API request failed: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def get_location_details(self) -> Dict[str, Any]:
        """
        Get location details
        """
        logger.info(f"Fetching details for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}")
        
        if "error" not in result:
            self.location_details = result
            logger.info(f"Successfully retrieved location details: {result.get('name', 'Unknown')}")
        else:
            logger.warning(f"Failed to get location details: {result['error']}")
        
        return result
    
    def get_custom_fields(self) -> Dict[str, Any]:
        """
        Get custom fields
        """
        logger.info(f"Fetching custom fields for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/customFields")
        
        if "error" not in result:
            self.custom_fields = result.get("customFields", [])
            logger.info(f"Successfully retrieved {len(self.custom_fields)} custom fields")
        else:
            logger.warning(f"Failed to get custom fields: {result['error']}")
        
        return result
    
    def get_custom_values(self) -> Dict[str, Any]:
        """
        Get custom values
        """
        logger.info(f"Fetching custom values for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/customValues")
        
        if "error" not in result:
            self.custom_values = result
            logger.info(f"Successfully retrieved custom values")
        else:
            logger.warning(f"Failed to get custom values: {result['error']}")
        
        return result
    
    def get_workflows(self) -> Dict[str, Any]:
        """
        Try multiple endpoints to get workflows
        """
        logger.info(f"Fetching workflows for location {self.location_id}...")
        
        # Try different endpoints to get workflows
        endpoints = [
            "workflows",
            f"locations/{self.location_id}/workflows",
            f"workflows?locationId={self.location_id}",
            f"v2/locations/{self.location_id}/workflows"
        ]
        
        for endpoint in endpoints:
            logger.info(f"Checking for workflows using endpoint: https://rest.gohighlevel.com/v1/{endpoint}")
            result = self._make_api_request(endpoint)
            
            if "error" not in result:
                self.workflows = result.get("workflows", [])
                logger.info(f"Successfully retrieved {len(self.workflows)} workflows")
                return result
        
        logger.warning("Could not access workflows through any API endpoint")
        return {"error": "Could not access workflows through any API endpoint"}
    
    def get_tags(self) -> Dict[str, Any]:
        """
        Get tags
        """
        logger.info(f"Fetching tags for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/tags")
        
        if "error" not in result:
            self.tags = result.get("tags", [])
            logger.info(f"Successfully retrieved {len(self.tags)} tags")
        else:
            logger.warning(f"Failed to get tags: {result['error']}")
        
        return result
    
    def get_pipelines(self) -> Dict[str, Any]:
        """
        Get pipelines
        """
        logger.info(f"Fetching pipelines for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/pipelines")
        
        if "error" not in result:
            self.pipelines = result.get("pipelines", [])
            logger.info(f"Successfully retrieved {len(self.pipelines)} pipelines")
        else:
            logger.warning(f"Failed to get pipelines: {result['error']}")
        
        return result
    
    def get_forms(self) -> Dict[str, Any]:
        """
        Get forms
        """
        logger.info(f"Fetching forms for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/forms")
        
        if "error" not in result:
            self.forms = result.get("forms", [])
            logger.info(f"Successfully retrieved {len(self.forms)} forms")
        else:
            logger.warning(f"Failed to get forms: {result['error']}")
        
        return result
    
    def get_templates(self) -> Dict[str, Any]:
        """
        Get email templates
        """
        logger.info(f"Fetching email templates for location {self.location_id}...")
        result = self._make_api_request(f"locations/{self.location_id}/templates")
        
        if "error" not in result:
            self.templates = result.get("templates", [])
            logger.info(f"Successfully retrieved {len(self.templates)} email templates")
        else:
            logger.warning(f"Failed to get email templates: {result['error']}")
        
        return result
    
    def add_note(self, note: str):
        """
        Add a note about the location
        """
        self.notes.append(note)
        return self
    
    def add_screenshot(self, screenshot_path: str, description: str = ""):
        """
        Add a screenshot path with optional description
        """
        self.screenshot_paths.append({
            "path": screenshot_path,
            "description": description
        })
        return self
    
    def create_snapshot(self) -> Dict[str, Any]:
        """
        Create a complete snapshot of the location
        """
        logger.info(f"Creating complete snapshot of location {self.location_id}...")
        
        # Get all location data
        self.get_location_details()
        self.get_custom_fields()
        self.get_custom_values()
        self.get_workflows()
        self.get_tags()
        self.get_pipelines()
        self.get_forms()
        self.get_templates()
        
        # Add note about specific workflow
        self.add_note(f"The workflow with ID 943eafb8-04c4-4a96-89c5-c2d44f8b9278 requires manual recreation")
        
        return self.to_dict()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert snapshot to dictionary
        """
        return {
            "location_id": self.location_id,
            "location_name": self.location_details.get("name", "Unknown"),
            "snapshot_date": self.snapshot_date.isoformat(),
            "location_details": self.location_details,
            "custom_fields": self.custom_fields,
            "custom_values": self.custom_values,
            "workflows": self.workflows,
            "tags": self.tags,
            "pipelines": self.pipelines,
            "forms": self.forms,
            "templates": self.templates,
            "notes": self.notes,
            "screenshot_paths": self.screenshot_paths
        }
    
    def save(self, output_dir: str = "location_snapshots") -> str:
        """
        Save snapshot to JSON file
        """
        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create filename
        location_name = self.location_details.get("name", "unknown").replace(" ", "_").lower()
        filename = f"{location_name}_{self.location_id}_snapshot.json"
        filepath = os.path.join(output_dir, filename)
        
        # Save to file
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Saved location snapshot to {filepath}")
        return filepath

def create_location_snapshot(location_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a complete snapshot of a location
    """
    snapshot = LocationSnapshot(location_id, api_key)
    snapshot.create_snapshot()
    filepath = snapshot.save()
    
    return {
        "success": True,
        "location_id": location_id,
        "location_name": snapshot.location_details.get("name", "Unknown"),
        "filepath": filepath,
        "snapshot": snapshot.to_dict()
    }
