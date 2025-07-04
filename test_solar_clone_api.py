#!/usr/bin/env python3
"""
Test script for the Solar sub-account cloning API
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime

# Add the project root to the Python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_solar_clone_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Base URL for local testing
BASE_URL = "http://localhost:8000"

def test_list_solar_workflows():
    """Test listing workflows for a Solar sub-account"""
    logger.info("Testing list_solar_workflows endpoint")
    
    # Example Solar location ID
    location_id = "JUTFTny8EXQOSB5NcvAA"  # Replace with actual Solar location ID
    
    url = f"{BASE_URL}/api/ghl/solar-workflows"
    payload = {
        "location_id": location_id
    }
    
    try:
        response = requests.post(url, json=payload)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Success: {data.get('success')}")
            logger.info(f"Found {data.get('count')} workflows")
            
            # Print first workflow if available
            if data.get('workflows') and len(data.get('workflows')) > 0:
                first_workflow = data.get('workflows')[0]
                logger.info(f"First workflow: {first_workflow.get('name')} (ID: {first_workflow.get('id')})")
            
            return data
        else:
            logger.error(f"Error: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Exception in test_list_solar_workflows: {str(e)}")
        return None

def test_clone_solar_sub_account():
    """Test cloning a Solar sub-account"""
    logger.info("Testing clone_solar_sub_account endpoint")
    
    # Example Solar location ID
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Replace with actual Solar location ID
    
    # Generate a unique name for the new location
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_name = f"Solar Clone Test {timestamp}"
    
    url = f"{BASE_URL}/api/ghl/solar-clone"
    payload = {
        "source_location_id": source_location_id,
        "target_name": target_name,
        "document_workflows": True
    }
    
    try:
        response = requests.post(url, json=payload)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Success: {data.get('success')}")
            
            if data.get('success'):
                logger.info(f"New location ID: {data.get('new_location_id')}")
                logger.info(f"New location name: {data.get('new_location_name')}")
                logger.info(f"Workflows documented: {data.get('workflows_documented')}")
            else:
                logger.error(f"Error: {data.get('error')}")
            
            return data
        else:
            logger.error(f"Error: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Exception in test_clone_solar_sub_account: {str(e)}")
        return None

def main():
    """Run all tests"""
    logger.info("Starting Solar Clone API tests")
    
    # Test listing workflows
    workflows_result = test_list_solar_workflows()
    
    # Test cloning a sub-account
    clone_result = test_clone_solar_sub_account()
    
    logger.info("Completed Solar Clone API tests")

if __name__ == "__main__":
    main()
