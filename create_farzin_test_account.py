#!/usr/bin/env python3
"""
Script to create a new GoHighLevel subaccount named 'Farzin Test' from the Solar account
"""

import logging
from GHL.Sub_Accounts.manual_clone import manual_clone_location
from GHL.environment.constant import Constant

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("create_farzin_test")

# Solar sub-account ID
SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"

def create_farzin_test_account():
    """Create a new 'Farzin Test' subaccount from the Solar account"""
    
    logger.info("Creating 'Farzin Test' subaccount from Solar account...")
    
    result = manual_clone_location(
        source_location_id=SOLAR_LOCATION_ID,
        new_location_name="Farzin Test",
        new_location_email="farzin.test@theai.team",
        custom_values={
            "account_type": "Test Account",
            "created_date": "2025-07-03",
            "created_by": "Cascade AI"
        }
    )
    
    if result.get("success"):
        new_location_id = result.get("new_location_id")
        logger.info(f"Successfully created 'Farzin Test' subaccount with ID: {new_location_id}")
        
        # Print API key for the new location
        api_key = result.get("new_location", {}).get("apiKey")
        if api_key:
            logger.info(f"API Key for new location: {api_key}")
        
        # Check workflow status
        workflow_status = result.get("workflow_status", {})
        workflow_note = workflow_status.get("note", "No workflow information available")
        logger.info(f"Workflow status: {workflow_note}")
        
        return {
            "success": True,
            "new_location_id": new_location_id,
            "api_key": api_key,
            "workflow_status": workflow_note
        }
    else:
        error = result.get("error", "Unknown error")
        logger.error(f"Failed to create 'Farzin Test' subaccount: {error}")
        return {
            "success": False,
            "error": error
        }

if __name__ == "__main__":
    print("Creating 'Farzin Test' subaccount from Solar account...")
    print("This may take a moment...\n")
    
    # Configure logging to also print to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)
    
    result = create_farzin_test_account()
    
    if result.get("success"):
        print("\nSuccess! New subaccount details:")
        print(f"Location ID: {result.get('new_location_id')}")
        print(f"API Key: {result.get('api_key')}")
        print(f"Workflow Status: {result.get('workflow_status')}")
    else:
        print(f"\nError: {result.get('error')}")
        
    print("\nCheck the GoHighLevel dashboard to see your new 'Farzin Test' subaccount.")
