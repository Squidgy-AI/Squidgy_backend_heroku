import os
import sys
import json
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import required modules
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

logger = logging.getLogger('solar_snapshot')

# Source location ID (Solar sub-account)
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"

def create_solar_snapshot():
    """
    Create a comprehensive snapshot of the Solar sub-account
    including workflow documentation
    """
    print("Creating Solar Sub-Account Snapshot with Workflow Documentation")
    print("=========================================================\n")
    
    # Create timestamp for the snapshot
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "solar_snapshot",
        f"snapshot_{timestamp}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Solar Location ID: {SOLAR_LOCATION_ID}")
    print(f"Output Directory: {output_dir}\n")
    
    # Initialize the workflow documentation helper with Solar access token
    doc_helper = WorkflowDocumentation(Constant.Solar_Access_Token)
    
    # Get all workflows for the Solar location
    print("Fetching workflows...")
    workflows = doc_helper.get_workflow_list(SOLAR_LOCATION_ID)
    
    if workflows:
        print(f"Found {len(workflows)} workflows")
        
        # Save the list of workflows
        workflows_file = os.path.join(output_dir, "workflows_list.json")
        with open(workflows_file, "w") as f:
            json.dump(workflows, f, indent=2)
        print(f"Saved workflows list to {workflows_file}")
        
        # Create a recreation guide for all workflows
        print("\nCreating workflow recreation guide...")
        workflow_ids = [w["id"] for w in workflows]
        
        guide_result = doc_helper.create_recreation_guide(
            workflow_ids=workflow_ids,
            location_id=SOLAR_LOCATION_ID,
            output_dir=output_dir
        )
        
        if guide_result["success"]:
            print(f"Successfully created recreation guide: {guide_result['guide']['filepath']}")
        else:
            print(f"Error creating recreation guide: {guide_result.get('message', 'Unknown error')}")
    else:
        print("No workflows found")
    
    # Create a snapshot summary
    summary = {
        "location_id": SOLAR_LOCATION_ID,
        "snapshot_date": datetime.now().isoformat(),
        "workflow_count": len(workflows) if workflows else 0,
        "snapshot_directory": output_dir,
        "notes": [
            "This snapshot was created using the Solar-specific access token",
            "Due to API limitations, workflows must be manually recreated",
            "Use the recreation guide to manually recreate workflows in the target location"
        ]
    }
    
    # Save the summary
    summary_file = os.path.join(output_dir, "snapshot_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSnapshot summary saved to {summary_file}")
    print("\nSnapshot creation complete!")
    print("\nNext Steps:")
    print("1. Review the workflow recreation guide")
    print("2. Take screenshots of workflows in the GoHighLevel dashboard")
    print("3. Use the guide to manually recreate workflows in the target location")
    
    return {
        "success": True,
        "snapshot_directory": output_dir,
        "workflow_count": len(workflows) if workflows else 0,
        "summary_file": summary_file
    }

if __name__ == "__main__":
    create_solar_snapshot()
