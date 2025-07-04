#!/usr/bin/env python3
"""
Test script for the integrated Solar sub-account cloning solution.

This script tests the integrated_clone_solution.py module which combines:
1. Location cloning using the Agency API key
2. Workflow documentation and recreation using the WorkflowSnapshot class
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.environment.constant import Constant
from GHL.Sub_Accounts.integrated_clone_solution import IntegratedCloneSolution, clone_solar_sub_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_integrated_clone.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def test_get_workflows():
    """Test getting workflows from the source location"""
    print("\n📋 Testing get_workflows_list()...")
    
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar sub-account ID
    cloner = IntegratedCloneSolution(source_location_id)
    
    workflows = cloner.get_workflows_list()
    
    if workflows:
        print(f"✅ Successfully retrieved {len(workflows)} workflows")
        print(f"First workflow: {workflows[0].get('name', 'Unknown')}")
        return True
    else:
        print("❌ Failed to retrieve workflows")
        return False


def test_create_snapshots():
    """Test creating workflow snapshots"""
    print("\n📸 Testing create_workflow_snapshots()...")
    
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar sub-account ID
    cloner = IntegratedCloneSolution(source_location_id)
    
    # Get workflows first
    workflows = cloner.get_workflows_list()
    
    if not workflows:
        print("❌ No workflows to create snapshots from")
        return False
    
    # Limit to first 2 workflows for testing
    test_workflows = workflows[:2]
    print(f"Creating snapshots for {len(test_workflows)} workflows")
    
    snapshot_files = cloner.create_workflow_snapshots(test_workflows)
    
    if snapshot_files:
        print(f"✅ Successfully created {len(snapshot_files)} workflow snapshots")
        for file in snapshot_files:
            print(f"  - {file}")
        return True
    else:
        print("❌ Failed to create workflow snapshots")
        return False


def test_clone_location():
    """Test cloning a location"""
    print("\n🔄 Testing clone_location()...")
    
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar sub-account ID
    target_name = f"Test Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    cloner = IntegratedCloneSolution(source_location_id)
    
    success, new_location_id, result = cloner.clone_location(target_name)
    
    if success and new_location_id:
        print(f"✅ Successfully cloned location")
        print(f"  - New Location ID: {new_location_id}")
        return True
    else:
        print("❌ Failed to clone location")
        print(f"  - Error: {result.get('error', 'Unknown error')}")
        return False


def test_full_clone():
    """Test the full cloning process"""
    print("\n🚀 Testing full clone process...")
    
    source_location_id = "JUTFTny8EXQOSB5NcvAA"  # Solar sub-account ID
    target_name = f"Full Test Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    result = clone_solar_sub_account(source_location_id, target_name)
    
    print("\n📊 Clone Results:")
    print("=" * 30)
    print(f"Success: {'✅' if result['success'] else '❌'}")
    
    if result['success']:
        print(f"New Location ID: {result['new_location_id']}")
        print(f"Workflows Documented: {result['workflow_count']}")
        print(f"Duration: {result['duration_seconds']:.2f} seconds")
        return True
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return False


def main():
    """Run all tests"""
    print("🧪 Integrated Clone Solution Tests")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests in sequence, stopping if any fail
    tests = [
        ("Get Workflows", test_get_workflows),
        ("Create Snapshots", test_create_snapshots),
        ("Clone Location", test_clone_location),
        ("Full Clone Process", test_full_clone)
    ]
    
    results = {}
    all_passed = True
    
    for name, test_func in tests:
        print(f"\n🔍 Running test: {name}")
        try:
            success = test_func()
            results[name] = success
            if not success:
                all_passed = False
                print(f"❌ Test '{name}' failed")
                # Don't break, continue with other tests
        except Exception as e:
            results[name] = False
            all_passed = False
            print(f"❌ Test '{name}' raised an exception: {str(e)}")
            logger.exception(f"Exception in test '{name}'")
    
    # Print summary
    print("\n📝 Test Summary:")
    print("=" * 30)
    for name, success in results.items():
        print(f"{name}: {'✅' if success else '❌'}")
    
    print("\n🏁 Final Result:")
    print(f"{'✅ All tests passed!' if all_passed else '❌ Some tests failed.'}")
    
    return all_passed


if __name__ == "__main__":
    main()
