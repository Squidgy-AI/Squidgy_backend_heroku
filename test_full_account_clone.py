#!/usr/bin/env python3
"""
Test script for the comprehensive GoHighLevel full account cloner.
Tests the enhanced FullAccountCloner class with multiple cloning strategies.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from GHL.Sub_Accounts.full_account_clone import FullAccountCloner


def test_full_account_clone():
    """Test the comprehensive full account cloning functionality"""
    
    # Solar sub-account ID from memory
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    
    print("🧪 Testing GoHighLevel Full Account Cloner")
    print("==========================================")
    print(f"Source Location ID: {SOLAR_LOCATION_ID}")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Create a test target name
    target_name = f"Test Solar Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Target Name: {target_name}")
    
    try:
        # Initialize the cloner
        print("\n📋 Initializing FullAccountCloner...")
        cloner = FullAccountCloner(source_location_id=SOLAR_LOCATION_ID)
        print(f"✅ Cloner initialized successfully")
        print(f"   - Output directory: {cloner.output_dir}")
        print(f"   - API v2 base: {cloner.api_v2_base}")
        print(f"   - Using Solar token: {cloner.solar_token[:20]}...")
        print(f"   - Using Agency API key: {cloner.agency_api_key[:20]}...")
        
        # Test workflow fetching first
        print("\n🔍 Testing workflow fetching...")
        workflows_result = cloner.get_workflows(SOLAR_LOCATION_ID, use_solar_token=True)
        
        if workflows_result["success"]:
            workflows = workflows_result.get("workflows", [])
            print(f"✅ Successfully fetched {len(workflows)} workflows")
            print(f"   - Endpoint used: {workflows_result.get('endpoint', 'N/A')}")
            
            if workflows:
                print("   - Sample workflows:")
                for i, workflow in enumerate(workflows[:3]):  # Show first 3
                    print(f"     {i+1}. {workflow.get('name', 'Unnamed')} (ID: {workflow.get('id', 'N/A')})")
        else:
            print(f"❌ Failed to fetch workflows: {workflows_result.get('error', 'Unknown error')}")
        
        # Attempt the full clone process
        print(f"\n🚀 Starting full clone process...")
        result = cloner.full_clone(target_name)
        
        # Print detailed results
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE CLONE RESULTS")
        print("="*60)
        
        print(f"Overall Success: {'✅ YES' if result['success'] else '❌ NO'}")
        print(f"Target Location ID: {result.get('target_location_id', 'N/A')}")
        print(f"Workflow Clone Success: {'✅ YES' if result['workflow_clone_success'] else '❌ NO'}")
        print(f"Timestamp: {result['timestamp']}")
        
        print(f"\n📋 Strategies Attempted ({len(result['strategies_attempted'])}):")
        for i, strategy in enumerate(result['strategies_attempted'], 1):
            status = "✅ SUCCESS" if strategy['success'] else "❌ FAILED"
            print(f"  {i}. {strategy['strategy']}: {status}")
            if strategy.get('location_id'):
                print(f"     → Location ID: {strategy['location_id']}")
            if strategy.get('snapshot_file'):
                print(f"     → Snapshot File: {strategy['snapshot_file']}")
        
        # Show fallback documentation if available
        if result.get('fallback_documentation'):
            print(f"\n📋 Fallback Documentation:")
            doc_info = result['fallback_documentation']
            print(f"   - Success: {'✅' if doc_info.get('success') else '❌'}")
            print(f"   - File: {doc_info.get('file', 'N/A')}")
            if doc_info.get('snapshot'):
                snapshot = doc_info['snapshot']
                print(f"   - Snapshot Type: {snapshot.get('snapshot_type', 'N/A')}")
                print(f"   - Timestamp: {snapshot.get('timestamp', 'N/A')}")
        
        # Show API call statistics
        print(f"\n📊 API Call Statistics:")
        print(f"   - Total API calls made: {len(cloner.api_calls_log)}")
        print(f"   - Output directory: {cloner.output_dir}")
        
        # Save detailed test results
        test_results_file = os.path.join(cloner.output_dir, "test_results.json")
        with open(test_results_file, "w") as f:
            json.dump({
                "test_info": {
                    "test_name": "full_account_clone_test",
                    "timestamp": datetime.now().isoformat(),
                    "source_location_id": SOLAR_LOCATION_ID,
                    "target_name": target_name
                },
                "clone_result": result,
                "workflows_test": workflows_result
            }, f, indent=2)
        
        print(f"   - Test results saved: {test_results_file}")
        
        # Final assessment
        print(f"\n🎯 FINAL ASSESSMENT:")
        if result['success']:
            if result['workflow_clone_success']:
                print("🎉 EXCELLENT: Full clone with workflows successful!")
            else:
                print("✅ GOOD: Location cloned, workflows may need manual setup")
        else:
            if result.get('fallback_documentation', {}).get('success'):
                print("📋 ACCEPTABLE: Documentation created for manual recreation")
            else:
                print("❌ NEEDS ATTENTION: Clone failed and no documentation created")
        
        return result
        
    except Exception as e:
        print(f"\n💥 Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_individual_methods():
    """Test individual methods of the FullAccountCloner"""
    
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    
    print("\n🔧 Testing Individual Methods")
    print("=============================")
    
    try:
        cloner = FullAccountCloner(source_location_id=SOLAR_LOCATION_ID)
        
        # Test 1: API request method
        print("\n1. Testing make_api_request method...")
        test_url = f"{cloner.api_v1_base}/locations/{SOLAR_LOCATION_ID}"
        headers = {
            "Authorization": f"Bearer {cloner.agency_api_key}",
            "Content-Type": "application/json"
        }
        
        success, response = cloner.make_api_request("GET", test_url, headers)
        print(f"   API Request Test: {'✅ SUCCESS' if success else '❌ FAILED'}")
        if success:
            print(f"   Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        # Test 2: Direct clone attempt
        print("\n2. Testing direct clone attempt...")
        test_name = f"Direct Test {datetime.now().strftime('%H%M%S')}"
        success, location_id = cloner.attempt_direct_location_clone_v2(test_name)
        print(f"   Direct Clone Test: {'✅ SUCCESS' if success else '❌ FAILED'}")
        if success:
            print(f"   New Location ID: {location_id}")
        
        # Test 3: Workflow fetching
        print("\n3. Testing workflow fetching...")
        workflows_result = cloner.get_workflows(SOLAR_LOCATION_ID)
        print(f"   Workflow Fetch Test: {'✅ SUCCESS' if workflows_result['success'] else '❌ FAILED'}")
        if workflows_result['success']:
            workflows = workflows_result.get('workflows', [])
            print(f"   Found {len(workflows)} workflows")
        
        print("\n✅ Individual method testing completed")
        
    except Exception as e:
        print(f"\n💥 Individual method testing failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 GoHighLevel Full Account Cloner - Comprehensive Test Suite")
    print("=" * 65)
    
    # Run the main test
    main_result = test_full_account_clone()
    
    # Run individual method tests
    test_individual_methods()
    
    print(f"\n🏁 All tests completed at: {datetime.now().isoformat()}")
    
    if main_result.get('success'):
        print("🎉 Main test PASSED - Clone operation successful!")
    else:
        print("⚠️  Main test had issues - Check logs for details")
