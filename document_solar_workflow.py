#!/usr/bin/env python3
"""
Script to document the specific Solar workflow with ID 943eafb8-04c4-4a96-89c5-c2d44f8b9278
Use this to create a detailed snapshot after taking screenshots of the workflow
"""

import json
import os
from GHL.Sub_Accounts.workflow_snapshot_helper import WorkflowSnapshot

# Constants
WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"

def document_solar_workflow():
    """
    Document the specific Solar workflow based on manual inspection
    """
    print("\nDocumenting Solar workflow from manual inspection...")
    
    # Create a new snapshot
    snapshot = WorkflowSnapshot(
        workflow_id=WORKFLOW_ID,
        workflow_name="Solar Lead Processing Workflow"  # Replace with actual name from your inspection
    )
    
    # Add workflow details based on your inspection
    # Replace these examples with the actual workflow configuration you observe
    
    # Example trigger (replace with actual trigger from your inspection)
    snapshot.add_trigger(
        trigger_type="form_submission",  # Replace with actual trigger type
        description="Triggered when a lead submits the solar quote form",  # Replace with actual description
        details={
            # Add any specific details you observe
            "form_name": "Solar Quote Request"
        }
    )
    
    # Example conditions (replace with actual conditions from your inspection)
    snapshot.add_condition(
        condition_type="contact_field",  # Replace with actual condition type
        description="Check if contact has provided their address",  # Replace with actual description
        details={
            # Add any specific details you observe
            "field": "address",
            "operator": "is_not_empty"
        }
    )
    
    # Example actions (replace with actual actions from your inspection)
    snapshot.add_action(
        action_type="send_email",  # Replace with actual action type
        description="Send solar quote confirmation email",  # Replace with actual description
        details={
            # Add any specific details you observe
            "template": "Solar Quote Confirmation",
            "subject": "Your Solar Quote Request"
        }
    )
    
    snapshot.add_action(
        action_type="create_task",  # Replace with actual action type
        description="Create follow-up task for sales team",  # Replace with actual description
        details={
            # Add any specific details you observe
            "task_name": "Follow up with solar lead",
            "due_days": 1
        }
    )
    
    # Add notes about the workflow
    snapshot.add_note("This workflow processes new solar leads when they request a quote")
    snapshot.add_note("It sends a confirmation email and creates a follow-up task for the sales team")
    snapshot.add_note("This workflow must be manually recreated in each new location")
    
    # Add screenshot paths (replace with actual screenshot paths)
    # Create a screenshots directory if it doesn't exist
    os.makedirs("workflow_screenshots", exist_ok=True)
    
    snapshot.add_screenshot(
        screenshot_path="workflow_screenshots/solar_workflow_overview.png",
        description="Overview of the entire workflow"
    )
    
    snapshot.add_screenshot(
        screenshot_path="workflow_screenshots/solar_workflow_trigger.png",
        description="Trigger configuration"
    )
    
    snapshot.add_screenshot(
        screenshot_path="workflow_screenshots/solar_workflow_conditions.png",
        description="Conditions configuration"
    )
    
    snapshot.add_screenshot(
        screenshot_path="workflow_screenshots/solar_workflow_actions.png",
        description="Actions configuration"
    )
    
    # Save the snapshot
    filepath = snapshot.save("solar_workflow_snapshots")
    
    print(f"\nWorkflow snapshot saved to: {filepath}")
    print("\nWorkflow Details:")
    print(f"  ID: {WORKFLOW_ID}")
    print(f"  Name: {snapshot.workflow_name}")
    print(f"  Triggers: {len(snapshot.triggers)}")
    print(f"  Conditions: {len(snapshot.conditions)}")
    print(f"  Actions: {len(snapshot.actions)}")
    print(f"  Notes: {len(snapshot.notes)}")
    print(f"  Screenshots: {len(snapshot.screenshot_paths)}")
    
    return {
        "success": True,
        "filepath": filepath,
        "snapshot": snapshot.to_dict()
    }

def create_workflow_recreation_guide():
    """
    Create a step-by-step guide for recreating the workflow in new locations
    """
    print("\nCreating workflow recreation guide...")
    
    # First document the workflow
    snapshot_result = document_solar_workflow()
    
    if not snapshot_result["success"]:
        print(f"Error documenting workflow: {snapshot_result.get('error')}")
        return snapshot_result
    
    snapshot = snapshot_result["snapshot"]
    
    # Create a guide
    guide = {
        "workflow_id": WORKFLOW_ID,
        "workflow_name": snapshot["workflow_name"],
        "source_location": "Solar",
        "source_location_id": SOLAR_LOCATION_ID,
        "recreation_steps": [
            "1. Log into GoHighLevel dashboard at https://app.gohighlevel.com/",
            "2. Navigate to the target location",
            "3. Go to Workflows section",
            "4. Click '+ Add Workflow' button",
            "5. Enter the workflow name: " + snapshot["workflow_name"],
            "6. Set up the trigger:" + (snapshot["triggers"][0]["description"] if snapshot["triggers"] else "")
        ]
    }
    
    # Add condition steps
    if snapshot["conditions"]:
        guide["recreation_steps"].append("7. Add the following conditions:")
        for i, condition in enumerate(snapshot["conditions"]):
            guide["recreation_steps"].append(f"   {i+1}. {condition['description']}")
    
    # Add action steps
    if snapshot["actions"]:
        next_step = len(guide["recreation_steps"]) + 1
        guide["recreation_steps"].append(f"{next_step}. Add the following actions:")
        for i, action in enumerate(snapshot["actions"]):
            guide["recreation_steps"].append(f"   {i+1}. {action['description']}")
    
    # Add final steps
    guide["recreation_steps"].extend([
        "8. Save the workflow",
        "9. Test the workflow to ensure it functions correctly",
        "10. Refer to the screenshots for detailed configuration"
    ])
    
    # Save the guide
    guide_filepath = os.path.join("solar_workflow_snapshots", "recreation_guide.json")
    os.makedirs(os.path.dirname(guide_filepath), exist_ok=True)
    
    with open(guide_filepath, "w") as f:
        json.dump(guide, f, indent=2)
    
    print(f"\nWorkflow recreation guide saved to: {guide_filepath}")
    print("\nGuide contains:")
    print(f"  Steps: {len(guide['recreation_steps'])}")
    
    return {
        "success": True,
        "filepath": guide_filepath,
        "guide": guide
    }

if __name__ == "__main__":
    print("Solar Workflow Documentation Tool")
    print("===============================")
    print(f"\nWorkflow ID: {WORKFLOW_ID}")
    print(f"Solar Location ID: {SOLAR_LOCATION_ID}")
    
    # Document the workflow
    snapshot_result = document_solar_workflow()
    
    # Create recreation guide
    guide_result = create_workflow_recreation_guide()
    
    print("\nDocumentation complete!")
    print("\nTo use this documentation:")
    print("1. Take screenshots of the workflow in the Solar location")
    print("2. Save screenshots to the 'workflow_screenshots' directory")
    print("3. Update this script with the actual workflow details")
    print("4. Run the script again to generate updated documentation")
    print("5. Use the recreation guide to manually recreate the workflow in new locations")
