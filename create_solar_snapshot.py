#!/usr/bin/env python3
"""
Script to create a complete snapshot of the Solar sub-account
including custom fields, custom values, workflows, tags, and pipelines
"""

import json
import os
import sys
import logging
from datetime import datetime

# Add the project root to the path to ensure imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the location snapshot module
from GHL.Sub_Accounts.location_snapshot import create_location_snapshot
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("solar_snapshot")

# Constants
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
OUTPUT_DIR = "solar_location_snapshot"

def create_solar_snapshot():
    """
    Create a complete snapshot of the Solar sub-account
    """
    print("\nCreating complete snapshot of Solar sub-account...")
    print(f"Location ID: {SOLAR_LOCATION_ID}")
    
    # Create the snapshot using the Solar-specific access token
    result = create_location_snapshot(
        location_id=SOLAR_LOCATION_ID,
        api_key=Constant.Solar_Access_Token
    )
    
    if result["success"]:
        print(f"\nSnapshot created successfully!")
        print(f"Location: {result['location_name']}")
        print(f"Saved to: {result['filepath']}")
        
        # Print summary of captured data
        snapshot = result["snapshot"]
        print("\nSnapshot contains:")
        print(f"  Custom Fields: {len(snapshot.get('custom_fields', []))}")
        print(f"  Custom Values: {len(snapshot.get('custom_values', {}))}")
        print(f"  Workflows: {len(snapshot.get('workflows', []))}")
        print(f"  Tags: {len(snapshot.get('tags', []))}")
        print(f"  Pipelines: {len(snapshot.get('pipelines', []))}")
        print(f"  Forms: {len(snapshot.get('forms', []))}")
        print(f"  Email Templates: {len(snapshot.get('templates', []))}")
        
        # Create a recreation guide
        create_recreation_guide(snapshot)
        
        return result
    else:
        print(f"\nError creating snapshot: {result.get('error')}")
        return result

def create_recreation_guide(snapshot):
    """
    Create a guide for recreating the location manually
    """
    print("\nCreating recreation guide...")
    
    # Create directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Create the guide
    guide = {
        "location_id": snapshot["location_id"],
        "location_name": snapshot["location_name"],
        "creation_date": datetime.now().isoformat(),
        "recreation_steps": [
            "1. Log into GoHighLevel dashboard at https://app.gohighlevel.com/",
            "2. Create a new location or navigate to the target location",
            "3. Follow the steps below to recreate the Solar sub-account configuration"
        ],
        "custom_fields": {
            "steps": [
                "1. Navigate to Settings > Custom Fields",
                "2. Create the following custom fields:"
            ],
            "fields": []
        },
        "tags": {
            "steps": [
                "1. Navigate to Settings > Tags",
                "2. Create the following tags:"
            ],
            "tag_list": []
        },
        "pipelines": {
            "steps": [
                "1. Navigate to Settings > Pipelines",
                "2. Create the following pipelines:"
            ],
            "pipeline_list": []
        },
        "workflows": {
            "steps": [
                "1. Navigate to Automations > Workflows",
                "2. Create the following workflows:"
            ],
            "workflow_list": []
        },
        "forms": {
            "steps": [
                "1. Navigate to Marketing > Forms",
                "2. Create the following forms:"
            ],
            "form_list": []
        },
        "templates": {
            "steps": [
                "1. Navigate to Marketing > Email Templates",
                "2. Create the following email templates:"
            ],
            "template_list": []
        }
    }
    
    # Add custom fields
    for field in snapshot.get("custom_fields", []):
        guide["custom_fields"]["fields"].append({
            "name": field.get("name", "Unknown"),
            "type": field.get("type", "Unknown"),
            "description": field.get("description", "")
        })
    
    # Add tags
    for tag in snapshot.get("tags", []):
        guide["tags"]["tag_list"].append({
            "name": tag.get("name", "Unknown"),
            "color": tag.get("color", "")
        })
    
    # Add pipelines
    for pipeline in snapshot.get("pipelines", []):
        pipeline_info = {
            "name": pipeline.get("name", "Unknown"),
            "stages": []
        }
        
        # Add pipeline stages
        for stage in pipeline.get("stages", []):
            pipeline_info["stages"].append({
                "name": stage.get("name", "Unknown"),
                "order": stage.get("order", 0)
            })
        
        guide["pipelines"]["pipeline_list"].append(pipeline_info)
    
    # Add workflows
    for workflow in snapshot.get("workflows", []):
        guide["workflows"]["workflow_list"].append({
            "id": workflow.get("id", "Unknown"),
            "name": workflow.get("name", "Unknown"),
            "description": workflow.get("description", ""),
            "note": "Take screenshots of this workflow in the Solar account for detailed recreation"
        })
    
    # Add special note for the specific workflow
    guide["workflows"]["workflow_list"].append({
        "id": "943eafb8-04c4-4a96-89c5-c2d44f8b9278",
        "name": "Important Solar Workflow",
        "description": "This specific workflow needs to be manually recreated",
        "note": "This workflow requires special attention during recreation"
    })
    
    # Add forms
    for form in snapshot.get("forms", []):
        guide["forms"]["form_list"].append({
            "name": form.get("name", "Unknown"),
            "description": form.get("description", "")
        })
    
    # Add email templates
    for template in snapshot.get("templates", []):
        guide["templates"]["template_list"].append({
            "name": template.get("name", "Unknown"),
            "subject": template.get("subject", "")
        })
    
    # Save the guide
    guide_filepath = os.path.join(OUTPUT_DIR, "recreation_guide.json")
    with open(guide_filepath, "w") as f:
        json.dump(guide, f, indent=2)
    
    print(f"Recreation guide saved to: {guide_filepath}")
    
    return guide_filepath

if __name__ == "__main__":
    print("Solar Sub-Account Snapshot Tool")
    print("=============================")
    
    # Create the snapshot
    result = create_solar_snapshot()
    
    if result["success"]:
        print("\nSnapshot process completed successfully!")
        print("\nTo use this snapshot:")
        print("1. Review the snapshot file for a complete inventory of the Solar sub-account")
        print("2. Use the recreation guide to manually recreate the configuration in new locations")
        print("3. Pay special attention to the workflow with ID 943eafb8-04c4-4a96-89c5-c2d44f8b9278")
    else:
        print("\nSnapshot process failed.")
