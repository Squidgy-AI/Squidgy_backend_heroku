#!/usr/bin/env python3
"""
Utility to help document and store workflow snapshots for manual recreation
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("workflow_snapshot")

class WorkflowSnapshot:
    """
    Helper class to document and store workflow snapshots
    """
    def __init__(self, workflow_id: str, workflow_name: str):
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.snapshot_date = datetime.now()
        self.triggers = []
        self.conditions = []
        self.actions = []
        self.notes = []
        self.screenshot_paths = []
    
    def add_trigger(self, trigger_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """
        Add a workflow trigger
        """
        self.triggers.append({
            "type": trigger_type,
            "description": description,
            "details": details or {}
        })
        return self
    
    def add_condition(self, condition_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """
        Add a workflow condition
        """
        self.conditions.append({
            "type": condition_type,
            "description": description,
            "details": details or {}
        })
        return self
    
    def add_action(self, action_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """
        Add a workflow action
        """
        self.actions.append({
            "type": action_type,
            "description": description,
            "details": details or {}
        })
        return self
    
    def add_note(self, note: str):
        """
        Add a note about the workflow
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
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert snapshot to dictionary
        """
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "snapshot_date": self.snapshot_date.isoformat(),
            "triggers": self.triggers,
            "conditions": self.conditions,
            "actions": self.actions,
            "notes": self.notes,
            "screenshot_paths": self.screenshot_paths
        }
    
    def save(self, output_dir: str = "workflow_snapshots") -> str:
        """
        Save snapshot to JSON file
        """
        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create filename
        filename = f"{self.workflow_name.replace(' ', '_').lower()}_{self.workflow_id[:8]}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Save to file
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Saved workflow snapshot to {filepath}")
        return filepath

def load_snapshot(filepath: str) -> WorkflowSnapshot:
    """
    Load a workflow snapshot from a file
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    
    snapshot = WorkflowSnapshot(data["workflow_id"], data["workflow_name"])
    
    # Load triggers
    for trigger in data.get("triggers", []):
        snapshot.add_trigger(trigger["type"], trigger["description"], trigger.get("details"))
    
    # Load conditions
    for condition in data.get("conditions", []):
        snapshot.add_condition(condition["type"], condition["description"], condition.get("details"))
    
    # Load actions
    for action in data.get("actions", []):
        snapshot.add_action(action["type"], action["description"], action.get("details"))
    
    # Load notes
    for note in data.get("notes", []):
        snapshot.add_note(note)
    
    # Load screenshots
    for screenshot in data.get("screenshot_paths", []):
        snapshot.add_screenshot(screenshot["path"], screenshot.get("description", ""))
    
    return snapshot

def create_solar_workflow_snapshot():
    """
    Create a sample workflow snapshot for the specific Solar workflow
    """
    # Create a new snapshot
    snapshot = WorkflowSnapshot(
        workflow_id="943eafb8-04c4-4a96-89c5-c2d44f8b9278",
        workflow_name="Solar Workflow"
    )
    
    # Add sample data (replace with actual workflow details)
    snapshot.add_trigger(
        trigger_type="form_submission",
        description="Triggered when a form is submitted",
        details={
            "form_id": "sample_form_id",
            "form_name": "Contact Form"
        }
    )
    
    snapshot.add_condition(
        condition_type="contact_tag",
        description="Check if contact has specific tag",
        details={
            "tag": "solar-lead",
            "operator": "equals"
        }
    )
    
    snapshot.add_action(
        action_type="send_email",
        description="Send welcome email to contact",
        details={
            "template_id": "sample_template_id",
            "template_name": "Solar Welcome Email"
        }
    )
    
    snapshot.add_note("This workflow sends a welcome email to new solar leads when they submit the contact form")
    
    # Save the snapshot
    filepath = snapshot.save()
    
    return {
        "success": True,
        "filepath": filepath,
        "snapshot": snapshot.to_dict()
    }

if __name__ == "__main__":
    print("Workflow Snapshot Helper")
    print("=======================")
    
    # Create a sample snapshot
    result = create_solar_workflow_snapshot()
    
    if result["success"]:
        print(f"\nCreated sample workflow snapshot at: {result['filepath']}")
        print("\nWorkflow Details:")
        print(f"  ID: {result['snapshot']['workflow_id']}")
        print(f"  Name: {result['snapshot']['workflow_name']}")
        print(f"  Triggers: {len(result['snapshot']['triggers'])}")
        print(f"  Conditions: {len(result['snapshot']['conditions'])}")
        print(f"  Actions: {len(result['snapshot']['actions'])}")
        print(f"  Notes: {len(result['snapshot']['notes'])}")
    else:
        print(f"\nError creating sample snapshot: {result.get('error')}")
