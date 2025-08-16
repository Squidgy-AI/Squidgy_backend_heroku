"""
N8N Workflow Cloning Script

This script creates a new workflow, fetches a template workflow, 
cleans the template data, and updates the new workflow with the template.

Usage:
    python clone_n8n_workflow.py

Requirements:
    - requests library: pip install requests
    - Valid n8n API token
"""

import requests
import json
from typing import Dict, Any, Optional


class N8NWorkflowCloner:
    def __init__(self, base_url: str, api_token: str):
        """
        Initialize the N8N Workflow Cloner.
        
        Args:
            base_url (str): Base URL of n8n instance (e.g., 'https://n8n.theaiteam.uk')
            api_token (str): n8n API authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Content-Type': 'application/json',
            'X-N8N-API-KEY': api_token
        }
    
    def clean_workflow_for_create(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean workflow data for creating a new workflow.
        Removes metadata and properties that n8n doesn't accept for creation.
        
        Args:
            workflow (dict): Original workflow data
            
        Returns:
            dict: Cleaned workflow data
        """
        cleaned = workflow.copy()
        
        # Remove top-level metadata properties
        metadata_keys = [
            'createdAt', 'updatedAt', 'id', 'shared', 'active', 'staticData'
        ]
        
        for key in metadata_keys:
            cleaned.pop(key, None)
        
        # Clean nodes - remove node-level metadata
        if 'nodes' in cleaned:
            for node in cleaned['nodes']:
                node_metadata_keys = [
                    'webhookId', 'disabled', 'notesInFlow', 'notes',
                    'executeOnce', 'alwaysOutputData', 'retryOnFail',
                    'maxTries', 'waitBetweenTries', 'continueOnFail', 'onError'
                ]
                
                for key in node_metadata_keys:
                    node.pop(key, None)
        
        # Clean settings - keep only essential ones
        if 'settings' in cleaned:
            essential_settings = ['executionOrder']
            new_settings = {}
            for key in essential_settings:
                if key in cleaned['settings']:
                    new_settings[key] = cleaned['settings'][key]
            cleaned['settings'] = new_settings
        
        return cleaned
    
    def clean_workflow_for_update(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean workflow data for updating an existing workflow.
        Only keeps the exact fields that n8n accepts for updates.
        
        Args:
            workflow (dict): Original workflow data
            
        Returns:
            dict: Cleaned workflow data with only allowed fields
        """
        # Based on n8n_fixed_workflow_body.json, only keep these exact fields
        cleaned = {}
        
        # Required fields for workflow update
        if 'name' in workflow:
            cleaned['name'] = workflow['name']
        
        if 'nodes' in workflow and isinstance(workflow['nodes'], list):
            cleaned['nodes'] = []
            for node in workflow['nodes']:
                if isinstance(node, dict):
                    # Only keep essential node properties
                    clean_node = {}
                    
                    # Required node fields
                    essential_node_fields = ['parameters', 'name', 'type', 'typeVersion', 'position', 'id']
                    for field in essential_node_fields:
                        if field in node:
                            clean_node[field] = node[field]
                    
                    # Optional node fields that are allowed
                    optional_node_fields = ['credentials', 'webhookId']
                    for field in optional_node_fields:
                        if field in node:
                            clean_node[field] = node[field]
                    
                    cleaned['nodes'].append(clean_node)
        
        if 'connections' in workflow:
            cleaned['connections'] = workflow['connections']
        
        if 'settings' in workflow:
            # Only keep executionOrder in settings
            cleaned['settings'] = {}
            if 'executionOrder' in workflow['settings']:
                cleaned['settings']['executionOrder'] = workflow['settings']['executionOrder']
        
        # Only include staticData if it's null (as shown in the example)
        if 'staticData' in workflow and workflow['staticData'] is None:
            cleaned['staticData'] = None
        
        return cleaned
    
    def create_workflow(self, name: str) -> Optional[str]:
        """
        Create a new empty workflow.
        
        Args:
            name (str): Name for the new workflow
            
        Returns:
            str: New workflow ID if successful, None if failed
        """
        print(f"Creating new workflow: {name}")
        
        # Minimal workflow body for creation
        workflow_body = {
            "name": name,
            "nodes": [
                {
                    "id": "manual-trigger",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [240, 300],
                    "parameters": {}
                }
            ],
            "connections": {},
            "settings": {
                "executionOrder": "v1"
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/workflows",
                headers=self.headers,
                json=workflow_body
            )
            
            if response.status_code in [200, 201]:
                workflow_data = response.json()
                workflow_id = workflow_data.get('id')
                print(f"✅ Workflow created successfully with ID: {workflow_id}")
                return workflow_id
            else:
                print(f"❌ Failed to create workflow: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Error creating workflow: {e}")
            return None
    
    def get_template_workflow(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch template workflow data.
        
        Args:
            template_id (str): ID of the template workflow
            
        Returns:
            dict: Template workflow data if successful, None if failed
        """
        print(f"Fetching template workflow: {template_id}")
        
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/workflows/{template_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                template_data = response.json()
                print(f"✅ Template workflow fetched successfully")
                print(f"Template name: {template_data.get('name', 'Unknown')}")
                print(f"Template nodes: {len(template_data.get('nodes', []))}")
                return template_data
            else:
                print(f"❌ Failed to fetch template: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Error fetching template: {e}")
            return None
    
    def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> bool:
        """
        Update an existing workflow with new data.
        
        Args:
            workflow_id (str): ID of the workflow to update
            workflow_data (dict): New workflow data
            
        Returns:
            bool: True if successful, False if failed
        """
        print(f"Updating workflow: {workflow_id}")
        
        # Clean the workflow data for update
        cleaned_data = self.clean_workflow_for_update(workflow_data)
        
        try:
            response = requests.put(
                f"{self.base_url}/api/v1/workflows/{workflow_id}",
                headers=self.headers,
                json=cleaned_data
            )
            
            if response.status_code == 200:
                print(f"✅ Workflow updated successfully")
                return True
            else:
                print(f"❌ Failed to update workflow: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"❌ Error updating workflow: {e}")
            return False
    
    def clone_workflow(self, template_id: str, new_name: str) -> Optional[str]:
        """
        Complete workflow cloning process.
        
        Args:
            template_id (str): ID of the template workflow to clone
            new_name (str): Name for the new workflow
            
        Returns:
            str: New workflow ID if successful, None if failed
        """
        print(f"\n🚀 Starting workflow cloning process")
        print(f"Template ID: {template_id}")
        print(f"New workflow name: {new_name}")
        print("-" * 50)
        
        # Step 1: Create new workflow
        new_workflow_id = self.create_workflow(new_name)
        if not new_workflow_id:
            return None
        
        # Step 2: Get template workflow
        template_data = self.get_template_workflow(template_id)
        if not template_data:
            return None
        
        # Step 3: Update new workflow name in template data
        template_data['name'] = new_name
        
        # Step 4: Update the new workflow with template data
        success = self.update_workflow(new_workflow_id, template_data)
        if not success:
            return None
        
        print(f"\n🎉 Workflow cloning completed successfully!")
        print(f"New workflow ID: {new_workflow_id}")
        print(f"New workflow URL: {self.base_url}/workflow/{new_workflow_id}")
        
        return new_workflow_id


def main():
    """Main function to run the workflow cloning process."""
    
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Configuration
    N8N_BASE_URL = os.getenv("N8N_BASE_URL")
    API_TOKEN = os.getenv("N8N_API")
    TEMPLATE_WORKFLOW_ID = os.getenv("N8N_TEMPLATE_WORKFLOW_ID")
    NEW_WORKFLOW_NAME = "Farzin | testing creating new agent"
    
    # Validate configuration
    if not API_TOKEN:
        print("❌ N8N_API token not found in .env file")
        return
    
    if not N8N_BASE_URL:
        print("❌ N8N_BASE_URL token not found in .env file")
        return

    if not TEMPLATE_WORKFLOW_ID:
        print("❌ N8N_TEMPLATE_WORKFLOW_ID token not found in .env file")
        return

    # Initialize cloner
    cloner = N8NWorkflowCloner(N8N_BASE_URL, API_TOKEN)
    
    # Clone the workflow
    new_workflow_id = cloner.clone_workflow(TEMPLATE_WORKFLOW_ID, NEW_WORKFLOW_NAME)
    
    if new_workflow_id:
        print(f"\n✅ Success! New workflow created with ID: {new_workflow_id}")
        
        # Save workflow info to file
        workflow_info = {
            "template_id": TEMPLATE_WORKFLOW_ID,
            "new_workflow_id": new_workflow_id,
            "new_workflow_name": NEW_WORKFLOW_NAME,
            "new_workflow_url": f"{N8N_BASE_URL}/workflow/{new_workflow_id}"
        }
        
        with open("cloned_workflow_info.json", "w") as f:
            json.dump(workflow_info, f, indent=2)
        
        print(f"📄 Workflow info saved to: cloned_workflow_info.json")
    else:
        print("\n❌ Workflow cloning failed")


if __name__ == "__main__":
    main()


# Example usage as a module:
"""
from clone_n8n_workflow import N8NWorkflowCloner

# Initialize
cloner = N8NWorkflowCloner("https://n8n.theaiteam.uk", "your-api-token")

# Clone workflow
new_id = cloner.clone_workflow("ijDtq0ljM2atxA0E", "My New Workflow")

if new_id:
    print(f"Cloned workflow ID: {new_id}")
"""
