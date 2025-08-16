"""
N8N Workflow Cloning Script

This script creates a new workflow, fetches a template workflow, 
cleans the template data, and updates the new workflow with the template.

Usage:
    python clone_n8n_workflow.py

Requirements:
    - requests library: pip install requests
    - openai library: pip install openai
    - Valid n8n API token
"""

import json
import requests
import os
from typing import Dict, Any, Optional, List


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
    
    def read_business_description(self, file_path: str = "business_description.txt") -> str:
        """
        Read business description from text file.
        
        Args:
            file_path (str): Path to business description file
            
        Returns:
            str: Business description content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                print(f"✅ Business description loaded from {file_path}")
                return content
        except FileNotFoundError:
            print(f"❌ Business description file not found: {file_path}")
            return ""
        except Exception as e:
            print(f"❌ Error reading business description: {e}")
            return ""
    
    def analyze_business_with_ai(self, business_description: str, available_tools: List[Dict]) -> Dict[str, Any]:
        """
        Use ChatGPT to analyze business description and recommend tool modifications.
        
        Args:
            business_description (str): Business description text
            available_tools (List[Dict]): List of available tools in template workflow
            
        Returns:
            Dict: AI recommendations for tool modifications
        """
        if not business_description:
            print("⚠️ No business description provided, skipping AI analysis")
            return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
        
        # Set up OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OpenAI API key not found in environment variables")
            return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Prepare tool descriptions for AI analysis
        tool_descriptions = []
        for tool in available_tools:
            tool_info = {
                "name": tool.get("name", "Unknown"),
                "type": tool.get("type", "Unknown"),
                "description": self.get_tool_description(tool)
            }
            tool_descriptions.append(tool_info)
        
        # Create AI prompt
        prompt = f"""
        Analyze the following business description and determine which n8n workflow tools are most relevant:

        BUSINESS DESCRIPTION:
        {business_description}

        AVAILABLE TOOLS:
        {json.dumps(tool_descriptions, indent=2)}

        Please provide recommendations in JSON format:
        {{
            "analysis": "Brief analysis of the business type and needs",
            "keep_tools": ["list of tool names that are relevant"],
            "remove_tools": ["list of tool names that should be removed"],
            "add_tools": [
                {{
                    "name": "suggested tool name",
                    "type": "n8n node type",
                    "reason": "why this tool would be beneficial"
                }}
            ]
        }}

        Focus on tools that would be most valuable for this specific business type.
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert n8n workflow consultant who helps businesses optimize their automation tools based on their specific needs."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content.strip()
            print(f"✅ AI analysis completed")
            print(f"AI Response: {ai_response[:200]}...")
            
            # Parse JSON response
            try:
                recommendations = json.loads(ai_response)
                return recommendations
            except json.JSONDecodeError:
                print("❌ Failed to parse AI response as JSON")
                return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
                
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {e}")
            print("⚠️ Proceeding without AI analysis - keeping all original tools")
            return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
    
    def get_tool_description(self, tool: Dict) -> str:
        """
        Extract a meaningful description from a tool node.
        
        Args:
            tool (Dict): Tool node data
            
        Returns:
            str: Tool description
        """
        tool_type = tool.get("type", "")
        tool_name = tool.get("name", "")
        
        # Map common n8n node types to descriptions
        descriptions = {
            "@n8n/n8n-nodes-langchain.toolHttpRequest": "HTTP API request tool",
            "n8n-nodes-base.supabaseTool": "Supabase database operations",
            "n8n-nodes-base.webhook": "Webhook trigger for external requests",
            "@n8n/n8n-nodes-langchain.agent": "AI agent for processing requests",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi": "OpenAI chat model integration",
            "@n8n/n8n-nodes-langchain.memoryBufferWindow": "Conversation memory management",
            "n8n-nodes-base.respondToWebhook": "Webhook response handler",
            "n8n-nodes-base.stickyNote": "Documentation/notes"
        }
        
        description = descriptions.get(tool_type, f"Tool type: {tool_type}")
        
        # Add specific details based on parameters
        if "parameters" in tool and isinstance(tool["parameters"], dict):
            params = tool["parameters"]
            if "url" in params:
                description += f" (URL: {params['url']})"
            elif "toolDescription" in params:
                description += f" ({params['toolDescription']})"
        
        return f"{tool_name}: {description}"
    
    def modify_workflow_tools(self, workflow_data: Dict, recommendations: Dict) -> Dict:
        """
        Modify workflow tools based on AI recommendations.
        
        Args:
            workflow_data (Dict): Original workflow data
            recommendations (Dict): AI recommendations
            
        Returns:
            Dict: Modified workflow data
        """
        if not recommendations or "remove_tools" not in recommendations:
            print("⚠️ No valid recommendations provided, keeping original workflow")
            return workflow_data
        
        modified_workflow = workflow_data.copy()
        
        # Remove unwanted tools
        tools_to_remove = recommendations.get("remove_tools", [])
        if tools_to_remove and "nodes" in modified_workflow:
            original_count = len(modified_workflow["nodes"])
            modified_workflow["nodes"] = [
                node for node in modified_workflow["nodes"]
                if node.get("name", "") not in tools_to_remove
            ]
            removed_count = original_count - len(modified_workflow["nodes"])
            if removed_count > 0:
                print(f"✅ Removed {removed_count} tools: {', '.join(tools_to_remove)}")
        
        # Update connections to remove references to deleted nodes
        if "connections" in modified_workflow and tools_to_remove:
            self.clean_connections(modified_workflow, tools_to_remove)
        
        # Log kept tools
        kept_tools = recommendations.get("keep_tools", [])
        if kept_tools:
            print(f"✅ Keeping {len(kept_tools)} relevant tools")
        
        # Log suggested additions (for manual implementation)
        add_tools = recommendations.get("add_tools", [])
        if add_tools:
            print(f"💡 AI suggests adding {len(add_tools)} additional tools:")
            for tool in add_tools:
                print(f"   - {tool.get('name', 'Unknown')}: {tool.get('reason', 'No reason provided')}")
        
        return modified_workflow
    
    def clean_connections(self, workflow_data: Dict, removed_tools: List[str]):
        """
        Clean workflow connections after removing tools.
        
        Args:
            workflow_data (Dict): Workflow data to clean
            removed_tools (List[str]): List of removed tool names
        """
        if "connections" not in workflow_data:
            return
        
        connections = workflow_data["connections"]
        
        # Remove connections from removed tools
        for tool_name in removed_tools:
            if tool_name in connections:
                del connections[tool_name]
        
        # Remove connections to removed tools
        for source_node, targets in connections.items():
            if isinstance(targets, dict):
                for connection_type, target_list in targets.items():
                    if isinstance(target_list, list):
                        # Filter out connections to removed tools
                        targets[connection_type] = [
                            target for target in target_list
                            if isinstance(target, list) and len(target) > 0
                            and all(
                                conn.get("node", "") not in removed_tools
                                for conn in target
                                if isinstance(conn, dict)
                            )
                        ]
    
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
    
    def clone_workflow(self, template_id: str, new_name: str, business_description_file: str = "business_description.txt") -> Optional[str]:
        """
        Complete workflow cloning process with AI-powered tool customization.
        
        Args:
            template_id (str): ID of the template workflow to clone
            new_name (str): Name for the new workflow
            business_description_file (str): Path to business description file
            
        Returns:
            str: New workflow ID if successful, None if failed
        """
        print(f"\n🚀 Starting AI-powered workflow cloning...")
        print(f"Template ID: {template_id}")
        print(f"New Name: {new_name}")
        print(f"Business Description File: {business_description_file}")
        
        # Step 1: Create new workflow
        new_workflow_id = self.create_workflow(new_name)
        if not new_workflow_id:
            return None
        
        # Step 2: Fetch template workflow
        template_data = self.get_template_workflow(template_id)
        if not template_data:
            return None
        
        # Step 3: Read business description
        business_description = self.read_business_description(business_description_file)
        
        # Step 4: Extract available tools from template
        available_tools = template_data.get('nodes', [])
        print(f"📋 Found {len(available_tools)} tools in template workflow")
        
        # Step 5: Analyze with AI and get tool recommendations
        print(f"\n🤖 Analyzing business needs with AI...")
        ai_recommendations = self.analyze_business_with_ai(business_description, available_tools)
        
        # Step 6: Modify workflow tools based on AI recommendations
        print(f"\n🔧 Customizing workflow based on AI analysis...")
        customized_workflow = self.modify_workflow_tools(template_data, ai_recommendations)
        
        # Step 6.5: Ensure the workflow name is set correctly
        customized_workflow['name'] = new_name
        
        # Step 7: Update the new workflow with customized data
        print(f"\n📤 Updating workflow with AI-customized tools...")
        success = self.update_workflow(new_workflow_id, customized_workflow)
        
        if success:
            # Step 8: Save AI analysis report
            try:
                report_filename = f"ai_analysis_report_{new_workflow_id}.json"
                with open(report_filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        "workflow_id": new_workflow_id,
                        "workflow_name": new_name,
                        "template_id": template_id,
                        "business_description_file": business_description_file,
                        "business_description": business_description,
                        "ai_recommendations": ai_recommendations,
                        "original_tool_count": len(available_tools),
                        "final_tool_count": len(customized_workflow.get('nodes', [])),
                        "timestamp": json.dumps({"$date": {"$numberLong": str(int(__import__('time').time() * 1000))}})
                    }, f, indent=2)
                print(f"✅ AI analysis report saved: {report_filename}")
            except Exception as e:
                print(f"⚠️ Could not save AI analysis report: {e}")
            
            return new_workflow_id
        else:
            print(f"❌ Failed to update workflow with AI customizations")
            return None


def main():
    """Main function to run the AI-powered workflow cloning process."""
    
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Configuration
    N8N_BASE_URL = os.getenv("N8N_BASE_URL")
    API_TOKEN = os.getenv("N8N_API")
    TEMPLATE_WORKFLOW_ID = os.getenv("N8N_TEMPLATE_WORKFLOW_ID")
    NEW_WORKFLOW_NAME = "Farzin | testing creating new agent"
    BUSINESS_DESCRIPTION_FILE = "business_description.txt"
    
    # Validate configuration
    if not API_TOKEN:
        print("❌ N8N_API token not found in .env file")
        return
    
    if not N8N_BASE_URL:
        print("❌ N8N_BASE_URL not found in .env file")
        return

    if not TEMPLATE_WORKFLOW_ID:
        print("❌ N8N_TEMPLATE_WORKFLOW_ID not found in .env file")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in .env file")
        return

    # Initialize cloner
    cloner = N8NWorkflowCloner(N8N_BASE_URL, API_TOKEN)
    
    # Clone the workflow with AI customization
    new_workflow_id = cloner.clone_workflow(
        TEMPLATE_WORKFLOW_ID, 
        NEW_WORKFLOW_NAME,
        BUSINESS_DESCRIPTION_FILE
    )
    
    if new_workflow_id:
        print(f"\n✅ Success! AI-customized workflow created with ID: {new_workflow_id}")
        
        # Save workflow info to file
        workflow_info = {
            "template_id": TEMPLATE_WORKFLOW_ID,
            "new_workflow_id": new_workflow_id,
            "new_workflow_name": NEW_WORKFLOW_NAME,
            "new_workflow_url": f"{N8N_BASE_URL}/workflow/{new_workflow_id}",
            "business_description_file": BUSINESS_DESCRIPTION_FILE,
            "ai_powered": True
        }
        
        with open("cloned_workflow_info.json", "w") as f:
            json.dump(workflow_info, f, indent=2)
        
        print(f"📄 Workflow info saved to: cloned_workflow_info.json")
        print(f"🌐 Access your new workflow at: {N8N_BASE_URL}/workflow/{new_workflow_id}")
    else:
        print("\n❌ AI-powered workflow cloning failed")


if __name__ == "__main__":
    main()
