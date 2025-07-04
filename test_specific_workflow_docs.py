#!/usr/bin/env python3
"""
Test script to generate documentation for the specific workflow ID: 943eafb8-04c4-4a96-89c5-c2d44f8b9278
"""

import os
import json
import logging
from GHL.Sub_Accounts.workflow_documentation import WorkflowDocumentation
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_workflow_docs")

# Constants
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
SPECIFIC_WORKFLOW_ID = "943eafb8-04c4-4a96-89c5-c2d44f8b9278"

def test_workflow_documentation():
    """
    Test generating workflow documentation for the specific workflow ID
    """
    print("\nGenerating workflow documentation for the specific workflow ID...")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "workflow_documentation",
        "specific_workflow"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize the workflow documentation helper with Solar access token
    doc_helper = WorkflowDocumentation(Constant.Solar_Access_Token)
    
    # Generate documentation for the specific workflow
    result = doc_helper.create_workflow_documentation(
        workflow_id=SPECIFIC_WORKFLOW_ID,
        location_id=SOLAR_LOCATION_ID,
        output_dir=output_dir
    )
    
    if result["success"]:
        doc = result["documentation"]
        print(f"Documentation generated and saved to {doc.get('filepath', 'unknown')}")
        
        # Print workflow details
        print("\nWorkflow Details:")
        print(f"  Name: {doc.get('workflow_name', 'Unknown')}")
        print(f"  Status: {doc.get('status', 'Unknown')}")
        print(f"  Created: {doc.get('created_at', 'Unknown')}")
        print(f"  Updated: {doc.get('updated_at', 'Unknown')}")
        
        # Print recreation steps
        print("\nRecreation Steps:")
        for step in doc.get("recreation_steps", []):
            print(f"  {step}")
        
        # Print notes
        print("\nNotes:")
        for note in doc.get("notes", []):
            print(f"  {note}")
    else:
        print(f"Error generating documentation: {result.get('message', 'Unknown error')}")
        
    return result

def test_clone_with_workflow_docs():
    """
    Test cloning a location with workflow documentation
    """
    print("\nCloning Solar location with workflow documentation...")
    
    # Import the clone_with_workflow_documentation function
    from GHL.Sub_Accounts.clone_with_documentation import clone_with_workflow_documentation
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "workflow_documentation",
        "clone_test"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Clone the Solar location with workflow documentation
    clone_result = clone_with_workflow_documentation(
        source_location_id=SOLAR_LOCATION_ID,
        new_location_name="Workflow Documentation Test",
        new_location_email="workflow.docs.test@example.com",
        custom_values={
            "company_name": "Solar Test Company",
            "industry": "Solar Energy",
            "clone_date": "2025-07-03"
        },
        access_token=Constant.Agency_Api_Key,
        document_workflows=True,
        output_dir=output_dir
    )
    
    if clone_result.get("success"):
        print(f"Successfully cloned location: {clone_result.get('new_location_id')}")
        
        # Check workflow status
        workflow_status = clone_result.get("workflow_status", "unknown")
        print(f"\nWorkflow Status: {workflow_status}")
        
        # Print workflow notes
        if clone_result.get("workflow_notes"):
            print("\nWorkflow Notes:")
            for note in clone_result.get("workflow_notes", []):
                print(f"  {note}")
        
        # Save the full result to a file for reference
        result_file = os.path.join(output_dir, "clone_result.json")
        with open(result_file, "w") as f:
            json.dump(clone_result, f, indent=2)
        print(f"\nFull result saved to {result_file}")
    else:
        print(f"Error cloning location: {clone_result.get('message', 'Unknown error')}")
        
    return clone_result

if __name__ == "__main__":
    print("GoHighLevel Specific Workflow Documentation Test")
    print("==============================================\n")
    print(f"Solar Location ID: {SOLAR_LOCATION_ID}")
    print(f"Specific Workflow ID: {SPECIFIC_WORKFLOW_ID}")
    
    # Default to running the workflow documentation test
    print("\nRunning workflow documentation test...")
    test_workflow_documentation()
