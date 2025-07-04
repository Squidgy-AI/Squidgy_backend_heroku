#!/usr/bin/env python3
"""
Comprehensive GoHighLevel sub-account cloner using API v2 endpoints.
Attempts multiple cloning strategies to achieve full automation without manual steps.
Uses the latest GoHighLevel API v2 documentation and endpoints.
"""

import os
import sys
import requests
import json
import os
import sys
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any, Tuple
import time

# Add the parent directory to the path to import Constant
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from GHL.environment.constant import Constant

# Import existing cloning functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from manual_clone import manual_clone_location, get_custom_values, update_custom_values
from workflow_documentation import WorkflowDocumentation
from workflow_snapshot_helper import WorkflowSnapshot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class FullAccountCloner:
    """
    Comprehensive GoHighLevel sub-account cloner using API v2 endpoints.
    Attempts multiple cloning strategies to achieve full automation without manual steps.
    Uses the latest GoHighLevel API v2 documentation and endpoints.
    """
    
    def __init__(self, source_location_id: str, agency_api_key: str = None, solar_token: str = None):
        self.source_location_id = source_location_id
        self.agency_api_key = agency_api_key or Constant.Agency_Api_Key
        self.solar_token = solar_token or Constant.Solar_Access_Token
        
        # API v2 base URLs (updated based on latest documentation)
        self.api_v2_base = "https://services.leadconnectorhq.com"
        self.api_v1_base = "https://rest.gohighlevel.com/v1"
        self.oauth_base = "https://marketplace.gohighlevel.com"
        
        # Setup logging
        self.setup_logging()
        
        # Track all API calls for debugging
        self.api_calls_log = []
        
        # Rate limiting
        self.last_api_call = 0
        self.min_api_interval = 0.1  # 100ms between API calls
        
    def setup_logging(self):
        """Setup comprehensive logging for the cloning process"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = f"full_clone_output_{timestamp}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Setup file logging
        log_file = os.path.join(self.output_dir, "full_clone.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def rate_limit(self):
        """Implement rate limiting to avoid API throttling"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.min_api_interval:
            time.sleep(self.min_api_interval - time_since_last_call)
        self.last_api_call = time.time()
    
    def make_api_request(self, method: str, url: str, headers: Dict, data: Dict = None, 
                        params: Dict = None, timeout: int = 30) -> Tuple[bool, Dict]:
        """Make API request with comprehensive logging, rate limiting and error handling"""
        try:
            # Apply rate limiting
            self.rate_limit()
            
            # Log the request
            request_log = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "url": url,
                "headers": {k: v for k, v in headers.items() if k.lower() != 'authorization'},
                "data": data,
                "params": params
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, params=params, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Log the response
            response_log = {
                "status_code": response.status_code,
                "response_text": response.text[:1000] if response.text else None,  # Limit response text
                "success": response.status_code < 400
            }
            
            # Combine request and response logs
            api_call_log = {**request_log, **response_log}
            self.api_calls_log.append(api_call_log)
            
            # Save API calls log
            self.save_api_calls_log()
            
            if response.status_code < 400:
                try:
                    return True, response.json()
                except json.JSONDecodeError:
                    return True, {"raw_response": response.text}
            else:
                self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                return False, {"error": response.text, "status_code": response.status_code}
                
        except Exception as e:
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "url": url,
                "error": str(e),
                "success": False
            }
            self.api_calls_log.append(error_log)
            self.save_api_calls_log()
            self.logger.error(f"API request exception: {str(e)}")
            return False, {"error": str(e)}
    
    def attempt_direct_location_clone_v2(self, target_name: str) -> Tuple[bool, Optional[str]]:
        """Attempt direct location cloning using API v2 endpoints with latest documentation"""
        self.logger.info("Attempting direct location clone using API v2...")
        
        # Updated v2 clone endpoints based on latest API documentation
        clone_endpoints = [
            f"{self.api_v2_base}/locations/{self.source_location_id}/clone",
            f"{self.api_v2_base}/locations/clone",
            f"{self.api_v2_base}/agencies/locations/{self.source_location_id}/clone",
            f"{self.api_v2_base}/agencies/locations/clone",
            f"{self.api_v2_base}/locations/{self.source_location_id}/duplicate",
            f"{self.api_v2_base}/locations/duplicate"
        ]
        
        headers = {
            "Authorization": f"Bearer {self.agency_api_key}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Enhanced clone data with more comprehensive options
        clone_data = {
            "sourceLocationId": self.source_location_id,
            "name": target_name,
            "includeWorkflows": True,
            "includeCustomFields": True,
            "includeTags": True,
            "includeContacts": False,  # Usually don't want to clone contacts
            "includeOpportunities": False,
            "includeForms": True,
            "includeCalendars": True,
            "includeCampaigns": True,
            "includePipelines": True,
            "includeTemplates": True,
            "includeIntegrations": True
        }
        
        for endpoint in clone_endpoints:
            self.logger.info(f"Trying clone endpoint: {endpoint}")
            success, response = self.make_api_request("POST", endpoint, headers, clone_data)
            
            if success and "locationId" in response:
                new_location_id = response["locationId"]
                self.logger.info(f"Successfully cloned location via {endpoint}. New ID: {new_location_id}")
                return True, new_location_id
            elif success:
                self.logger.info(f"Clone request accepted at {endpoint}, checking response: {response}")
                # Some endpoints might return different response formats
                if "id" in response:
                    return True, response["id"]
                elif "location" in response and "id" in response["location"]:
                    return True, response["location"]["id"]
                elif "data" in response and "id" in response["data"]:
                    return True, response["data"]["id"]
            
            self.logger.warning(f"Clone attempt failed at {endpoint}: {response}")
        
        return False, None
    
    def attempt_individual_workflow_clone(self, target_location_id: str) -> bool:
        """Attempt to clone workflows individually using API v2 with enhanced methods"""
        self.logger.info("Attempting individual workflow clone...")
        
        # Get all workflows from source location
        workflows = self.get_workflows(self.source_location_id, use_solar_token=True)
        if not workflows:
            self.logger.warning("No workflows found in source location")
            return False
        
        success_count = 0
        total_workflows = len(workflows)
        
        for workflow in workflows:
            workflow_id = workflow["id"]
            workflow_name = workflow.get("name", f"Workflow_{workflow_id}")
            
            self.logger.info(f"Cloning workflow: {workflow_name} ({workflow_id})")
            
            # Get detailed workflow data
            workflow_details = self.get_workflow_details(workflow_id, use_solar_token=True)
            if not workflow_details:
                self.logger.warning(f"Could not get details for workflow {workflow_id}")
                continue
            
            # Enhanced individual workflow clone endpoints
            clone_endpoints = [
                f"{self.api_v2_base}/locations/{target_location_id}/workflows/{workflow_id}/clone",
                f"{self.api_v2_base}/workflows/{workflow_id}/clone",
                f"{self.api_v2_base}/locations/{target_location_id}/workflows/import-single",
                f"{self.api_v2_base}/workflows/clone",
                f"{self.api_v2_base}/locations/{target_location_id}/workflows/{workflow_id}/copy",
                f"{self.api_v2_base}/workflows/{workflow_id}/duplicate",
                f"{self.api_v2_base}/locations/{target_location_id}/workflows/create-from-template"
            ]
            
            headers = {
                "Authorization": f"Bearer {self.solar_token}",
                "Content-Type": "application/json",
                "Version": "2021-07-28"
            }
            
            # Enhanced clone data with multiple formats
            clone_data_variants = [
                {
                    "sourceWorkflowId": workflow_id,
                    "targetLocationId": target_location_id,
                    "workflowData": workflow_details,
                    "preserveId": False
                },
                {
                    "workflowId": workflow_id,
                    "locationId": target_location_id,
                    "includeActions": True,
                    "includeTriggers": True
                },
                {
                    "templateId": workflow_id,
                    "targetLocation": target_location_id,
                    "workflowName": workflow_name
                }
            ]
            
            workflow_cloned = False
            for endpoint in clone_endpoints:
                for clone_data in clone_data_variants:
                    success, response = self.make_api_request("POST", endpoint, headers, clone_data)
                    
                    if success:
                        self.logger.info(f"Successfully cloned workflow {workflow_name} via {endpoint}")
                        success_count += 1
                        workflow_cloned = True
                        break
                
                if workflow_cloned:
                    break
            
            if not workflow_cloned:
                self.logger.warning(f"Failed to clone workflow {workflow_name}")
        
        self.logger.info(f"Individual workflow clone completed: {success_count}/{total_workflows} successful")
        return success_count > 0
    
    def save_api_calls_log(self):
        """Save API calls log to file"""
        log_file = os.path.join(self.output_dir, "api_calls.log")
        with open(log_file, "w") as f:
            json.dump(self.api_calls_log, f, indent=2)
    
    def get_workflows(self, location_id: str, use_solar_token: bool = True) -> Dict[str, Any]:
        """Get workflows for a location using multiple endpoint attempts"""
        headers = {
            "Authorization": f"Bearer {self.solar_token if use_solar_token else self.agency_api_key}",
            "Content-Type": "application/json"
        }
        
        # Try different API endpoints
        endpoints = [
            f"{self.api_v1_base}/workflows",  # v1 base endpoint
            f"{self.api_v1_base}/locations/{location_id}/workflows",  # v1 location-specific
            f"{self.api_v2_base}/workflows/locations/{location_id}",  # v2 endpoint
            f"{self.api_v2_base}/locations/{location_id}/workflows"  # Alternative v2
        ]
        
        for url in endpoints:
            try:
                self.logger.info(f"Fetching workflows using endpoint: {url}")
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    workflows = []
                    
                    # Handle different response structures
                    if isinstance(data, list):
                        workflows = data
                    elif isinstance(data, dict):
                        if "workflows" in data:
                            workflows = data["workflows"]
                        elif "data" in data and isinstance(data["data"], list):
                            workflows = data["data"]
                    
                    # Filter workflows for the specific location if needed
                    if workflows and "locationId" in workflows[0]:
                        workflows = [w for w in workflows if w.get("locationId") == location_id]
                    
                    self.logger.info(f"Found {len(workflows)} workflows using endpoint {url}")
                    
                    return {
                        "success": True,
                        "workflows": workflows,
                        "endpoint": url
                    }
                else:
                    self.logger.warning(f"Failed to get workflows from {url}: {response.status_code} - {response.text}")
            except Exception as e:
                error_msg = f"Error fetching workflows from {url}: {str(e)}"
                self.logger.exception(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "exception_type": type(e).__name__
                }
        
        self.logger.error("Failed to get workflows from any endpoint")
        return {
            "success": False,
            "error": "Failed to get workflows from any endpoint"
        }
    
    def get_workflow_details(self, workflow_id: str, use_solar_token: bool = True) -> Dict[str, Any]:
        """Get detailed information about a specific workflow"""
        headers = {
            "Authorization": f"Bearer {self.solar_token if use_solar_token else self.agency_api_key}",
            "Content-Type": "application/json"
        }
        
        # Try different API endpoints
        endpoints = [
            f"{self.api_v1_base}/workflows/{workflow_id}",  # v1 base endpoint
            f"{self.api_v1_base}/locations/{self.source_location_id}/workflows/{workflow_id}",  # v1 location-specific
            f"{self.api_v2_base}/workflows/{workflow_id}",  # v2 endpoint
            f"{self.api_v2_base}/locations/{self.source_location_id}/workflows/{workflow_id}"  # Alternative v2
        ]
        
        for url in endpoints:
            try:
                self.logger.info(f"Fetching workflow details using endpoint: {url}")
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    workflow_details = response.json()
                    self.logger.info(f"Successfully retrieved workflow details from {url}")
                    
                    # Try to get triggers and actions
                    try:
                        triggers_url = f"{self.api_v1_base}/workflows/{workflow_id}/triggers"
                        triggers_response = requests.get(triggers_url, headers=headers, timeout=30)
                        
                        if triggers_response.status_code == 200:
                            workflow_details["triggers"] = triggers_response.json()
                            self.logger.info("Successfully retrieved workflow triggers")
                    except Exception as e:
                        self.logger.warning(f"Error fetching workflow triggers: {str(e)}")
                    
                    try:
                        actions_url = f"{self.api_v1_base}/workflows/{workflow_id}/actions"
                        actions_response = requests.get(actions_url, headers=headers, timeout=30)
                        
                        if actions_response.status_code == 200:
                            workflow_details["actions"] = actions_response.json()
                            self.logger.info("Successfully retrieved workflow actions")
                    except Exception as e:
                        self.logger.warning(f"Error fetching workflow actions: {str(e)}")
                    
                    return {
                        "success": True,
                        "workflow_details": workflow_details,
                        "endpoint": url
                    }
                else:
                    self.logger.warning(f"Failed to get workflow details from {url}: {response.status_code} - {response.text}")
            except Exception as e:
                error_msg = f"Error fetching workflow details from {url}: {str(e)}"
                self.logger.exception(error_msg)
        
        self.logger.error(f"Failed to get details for workflow {workflow_id} from any endpoint")
        return {
            "success": False,
            "error": f"Failed to get details for workflow {workflow_id} from any endpoint"
        }
    
    def attempt_bulk_workflow_clone(self, target_location_id: str) -> bool:
        """Attempt to clone all workflows in bulk using API v2 with enhanced endpoints"""
        self.logger.info("Attempting bulk workflow clone...")
        
        # First, get all workflows from source location
        workflows_result = self.get_workflows(self.source_location_id, use_solar_token=True)
        if not workflows_result["success"] or not workflows_result.get("workflows"):
            self.logger.warning("No workflows found in source location")
            return False
        
        workflows = workflows_result["workflows"]
        
        # Enhanced bulk workflow clone endpoints
        bulk_endpoints = [
            f"{self.api_v2_base}/locations/{target_location_id}/workflows/bulk-clone",
            f"{self.api_v2_base}/workflows/bulk-clone",
            f"{self.api_v2_base}/locations/{target_location_id}/workflows/import",
            f"{self.api_v2_base}/locations/{target_location_id}/workflows/copy",
            f"{self.api_v2_base}/workflows/copy-bulk",
            f"{self.api_v2_base}/locations/{self.source_location_id}/workflows/export-to/{target_location_id}"
        ]
        
        headers = {
            "Authorization": f"Bearer {self.solar_token}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        
        # Enhanced bulk data with more comprehensive options
        bulk_data = {
            "sourceLocationId": self.source_location_id,
            "targetLocationId": target_location_id,
            "workflowIds": [w["id"] for w in workflows],
            "includeActions": True,
            "includeTriggers": True,
            "includeConditions": True,
            "includeFilters": True,
            "preserveIds": False,
            "updateExisting": True
        }
        
        for endpoint in bulk_endpoints:
            self.logger.info(f"Trying bulk workflow endpoint: {endpoint}")
            success, response = self.make_api_request("POST", endpoint, headers, bulk_data)
            
            if success:
                self.logger.info(f"Bulk workflow clone successful via {endpoint}: {response}")
                return True
            
            self.logger.warning(f"Bulk workflow clone failed at {endpoint}: {response}")
        
        return False
    
    def attempt_fallback_clone(self, target_name: str) -> Tuple[bool, Optional[str]]:
        """Fallback to existing manual clone method"""
        self.logger.info("Attempting fallback clone using existing manual clone method...")
        
        try:
            # Use the existing manual_clone_location function
            result = manual_clone_location(
                source_location_id=self.source_location_id,
                new_location_name=target_name,
                access_token=self.agency_api_key
            )
            
            if result.get("success") and result.get("new_location_id"):
                new_location_id = result["new_location_id"]
                self.logger.info(f"Fallback clone successful. New location ID: {new_location_id}")
                return True, new_location_id
            else:
                self.logger.warning(f"Fallback clone failed: {result}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Fallback clone exception: {str(e)}")
            return False, None
    
    def create_comprehensive_snapshot(self) -> Dict[str, Any]:
        """Create a comprehensive snapshot of the source location for documentation"""
        self.logger.info("Creating comprehensive snapshot of source location...")
        
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "source_location_id": self.source_location_id,
            "snapshot_type": "comprehensive_full_clone"
        }
        
        try:
            # Create workflow documentation
            workflow_doc = WorkflowDocumentation(
                location_id=self.source_location_id,
                access_token=self.solar_token
            )
            
            # Generate comprehensive documentation
            doc_result = workflow_doc.generate_comprehensive_documentation()
            if doc_result.get("success"):
                snapshot["workflow_documentation"] = doc_result
                self.logger.info("Successfully created workflow documentation")
            
            # Create workflow snapshots
            workflow_snapshot = WorkflowSnapshot(
                location_id=self.source_location_id,
                access_token=self.solar_token
            )
            
            snapshot_result = workflow_snapshot.create_comprehensive_snapshot()
            if snapshot_result.get("success"):
                snapshot["workflow_snapshots"] = snapshot_result
                self.logger.info("Successfully created workflow snapshots")
            
            # Save snapshot to file
            snapshot_file = os.path.join(self.output_dir, "comprehensive_snapshot.json")
            with open(snapshot_file, "w") as f:
                json.dump(snapshot, f, indent=2)
            
            self.logger.info(f"Comprehensive snapshot saved to: {snapshot_file}")
            return {"success": True, "snapshot": snapshot, "file": snapshot_file}
            
        except Exception as e:
            self.logger.error(f"Error creating comprehensive snapshot: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def full_clone(self, target_name: str) -> Dict[str, Any]:
        """Attempt comprehensive full clone using multiple strategies"""
        self.logger.info(f"Starting full clone process for target: {target_name}")
        
        clone_result = {
            "timestamp": datetime.now().isoformat(),
            "source_location_id": self.source_location_id,
            "target_name": target_name,
            "strategies_attempted": [],
            "success": False,
            "target_location_id": None,
            "workflow_clone_success": False,
            "fallback_documentation": None
        }
        
        # Strategy 1: Direct API v2 location clone
        self.logger.info("=== Strategy 1: Direct API v2 Location Clone ===")
        success, location_id = self.attempt_direct_location_clone_v2(target_name)
        clone_result["strategies_attempted"].append({
            "strategy": "direct_v2_clone",
            "success": success,
            "location_id": location_id
        })
        
        if success and location_id:
            clone_result["success"] = True
            clone_result["target_location_id"] = location_id
            self.logger.info(f"✅ Direct clone successful! Location ID: {location_id}")
            return clone_result
        
        # Strategy 2: Fallback to existing manual clone
        self.logger.info("=== Strategy 2: Fallback Manual Clone ===")
        success, location_id = self.attempt_fallback_clone(target_name)
        clone_result["strategies_attempted"].append({
            "strategy": "fallback_manual_clone",
            "success": success,
            "location_id": location_id
        })
        
        if success and location_id:
            clone_result["success"] = True
            clone_result["target_location_id"] = location_id
            self.logger.info(f"✅ Fallback clone successful! Location ID: {location_id}")
            
            # Now try to clone workflows to the new location
            self.logger.info("=== Attempting Workflow Clone ===")
            
            # Try bulk workflow clone first
            bulk_success = self.attempt_bulk_workflow_clone(location_id)
            if bulk_success:
                clone_result["workflow_clone_success"] = True
                self.logger.info("✅ Bulk workflow clone successful!")
            else:
                # Try individual workflow clone
                individual_success = self.attempt_individual_workflow_clone(location_id)
                if individual_success:
                    clone_result["workflow_clone_success"] = True
                    self.logger.info("✅ Individual workflow clone partially successful!")
                else:
                    self.logger.warning("❌ Workflow cloning failed")
            
            return clone_result
        
        # Strategy 3: Create comprehensive documentation for manual recreation
        self.logger.info("=== Strategy 3: Comprehensive Documentation ===")
        snapshot_result = self.create_comprehensive_snapshot()
        clone_result["strategies_attempted"].append({
            "strategy": "comprehensive_documentation",
            "success": snapshot_result.get("success", False),
            "snapshot_file": snapshot_result.get("file")
        })
        
        if snapshot_result.get("success"):
            clone_result["fallback_documentation"] = snapshot_result
            self.logger.info("✅ Comprehensive documentation created successfully!")
        
        # Final summary
        self.logger.info("=== Full Clone Process Complete ===")
        if clone_result["success"]:
            self.logger.info(f"🎉 SUCCESS: Location cloned to ID {clone_result['target_location_id']}")
            if clone_result["workflow_clone_success"]:
                self.logger.info("🎉 SUCCESS: Workflows also cloned successfully")
            else:
                self.logger.warning("⚠️  WARNING: Location cloned but workflows may need manual recreation")
        else:
            self.logger.error("❌ FAILED: Could not clone location via API")
            if clone_result["fallback_documentation"]:
                self.logger.info("📋 INFO: Comprehensive documentation created for manual recreation")
        
        return clone_result


def main():
    """Main function to test the full account cloner"""
    # Solar sub-account ID from memory
    SOLAR_LOCATION_ID = "JUTFTny8EXQOSB5NcvAA"
    
    print("🚀 GoHighLevel Full Account Cloner")
    print("===================================")
    print(f"Source Location ID: {SOLAR_LOCATION_ID}")
    
    # Get target name from user
    target_name = input("Enter target location name: ").strip()
    if not target_name:
        target_name = f"Solar Clone {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Using default name: {target_name}")
    
    # Initialize the cloner
    cloner = FullAccountCloner(source_location_id=SOLAR_LOCATION_ID)
    
    # Attempt full clone
    result = cloner.full_clone(target_name)
    
    # Print results
    print("\n" + "="*50)
    print("CLONE RESULTS")
    print("="*50)
    print(f"Success: {result['success']}")
    print(f"Target Location ID: {result.get('target_location_id', 'N/A')}")
    print(f"Workflow Clone Success: {result['workflow_clone_success']}")
    print(f"Strategies Attempted: {len(result['strategies_attempted'])}")
    
    for i, strategy in enumerate(result['strategies_attempted'], 1):
        print(f"  {i}. {strategy['strategy']}: {'✅' if strategy['success'] else '❌'}")
    
    if result.get('fallback_documentation'):
        print(f"\n📋 Documentation created: {result['fallback_documentation']['file']}")
    
    print(f"\n📁 Output directory: {cloner.output_dir}")
    print(f"📊 API calls made: {len(cloner.api_calls_log)}")


if __name__ == "__main__":
    main()
