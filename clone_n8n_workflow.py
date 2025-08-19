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
                    'webhookId', 'disabled', 'notesInFlow',
                    'executeOnce', 'alwaysOutputData', 'retryOnFail',
                    'maxTries', 'waitBetweenTries', 'continueOnFail', 'onError'
                ]
                # Keep 'notes' field for AI analysis injection
                
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
                    optional_node_fields = ['credentials', 'webhookId', 'notes']
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
        
        # Filter and prepare only actual tools for AI analysis (nodes with "tool" in their name)
        tool_descriptions = []
        actual_tools = []
        

        for node in available_tools:
            node_name = node.get("name", "").lower()
            node_type = node.get("type", "")
            
            # Only include nodes that are AI agent-usable tools (API calls, external integrations, functional tools)
            if ("tool" in node_name or 
                "tool" in node_type.lower() or
                node_type in ["@n8n/n8n-nodes-langchain.toolHttpRequest", 
                             "n8n-nodes-base.supabaseTool",
                             "@n8n/n8n-nodes-langchain.toolCalculator",
                             "@n8n/n8n-nodes-langchain.toolCode",
                             "@n8n/n8n-nodes-langchain.toolWebScraper",
                             "@n8n/n8n-nodes-langchain.toolWorkflowTool",
                             "n8n-nodes-base.httpRequest",
                             "n8n-nodes-base.googleSheets",
                             "n8n-nodes-base.airtable",
                             "n8n-nodes-base.slack",
                             "n8n-nodes-base.gmail"]):
                
                actual_tools.append(node)
                
                # Extract actual description from node parameters
                parameters = node.get("parameters", {})
                actual_description = (
                    parameters.get("toolDescription", "") or
                    parameters.get("description", "") or
                    self.get_tool_description(node_type)
                )
                
                tool_info = {
                    "name": node.get("name", "Unknown"),
                    "type": node_type,
                    "description": actual_description
                }
                tool_descriptions.append(tool_info)
        
        print(f"📋 Found {len(actual_tools)} AI agent-usable tools out of {len(available_tools)} total nodes")
        
        # Log all nodes found in workflow with their descriptions
        print(f"📋 Found {len(actual_tools)} total nodes in workflow:")
        for i, node in enumerate(actual_tools, 1):
            node_name = node.get("name", "Unknown")
            node_type = node.get("type", "")
            
            # Extract actual description from node parameters
            parameters = node.get("parameters", {})
            node_description = (
                parameters.get("toolDescription", "") or
                parameters.get("description", "") or
                self.get_tool_description(node_type)
            )
            
            print(f"   {i}. {node_name} ({node_type})")
            print(f"      Description: {node_description}")
        

        # Create AI prompt
        prompt = f"""
        Analyze the business information and determine which AI agent tools should be kept, removed, or added for optimal user assistance or customer services:

        BUSINESS CONTEXT:
        {business_description}

        CURRENT AI AGENT TOOLS:
        {json.dumps(tool_descriptions, indent=2)}

        IMPORTANT: These tools will be used by an AI CUSTOMER SERVICE AGENT to help this business's customers. The agent needs tools to provide helpful, accurate, and timely assistance.

        CRITICAL ANALYSIS REQUIREMENTS:
        1. Think from a CUSTOMER SERVICE perspective - what do customers typically ask about?
        2. Consider tools that help the AI agent provide better customer support
        3. Keep tools that enable the agent to give accurate, up-to-date information
        4. Remove tools only if they provide NO value for customer interactions
        5. Consider common customer scenarios: questions about products, services, orders, store hours, etc.

        TOOL EVALUATION CRITERIA FOR CUSTOMER SERVICE:
        - Can this tool help the AI agent answer customer questions more accurately?
        - Does this tool provide real-time or current information customers need?
        - Can this tool help with common customer service scenarios?
        - Does this tool enable the agent to provide personalized assistance?

        EXAMPLES OF CUSTOMER SERVICE VALUE:
        ✅ "Current time/date tool helps agent provide accurate business hours and delivery estimates"
        ✅ "Website analysis helps agent understand company services to better assist customers"
        ✅ "Database tools help agent check customer orders, account status, or inventory"
        ✅ "Screenshot tools help agent see what customers see for better troubleshooting"

        EXAMPLES OF POOR REASONING TO AVOID:
        ❌ "Customers don't need screenshots" (ignores that AGENT needs tools to help customers)
        ❌ "Time is not relevant" (ignores business hours, delivery times, appointment scheduling)
        ❌ "Website analysis is for internal use" (ignores that agent needs to understand business to help customers)
        ✅ "Order tracking API for e-commerce business to check customer order status"
        ✅ "Inventory check tool for retail business to provide real-time stock information"
        ✅ "Appointment booking API for service business to schedule customer appointments"

        Provide recommendations in JSON format:
        {{
            "business_analysis": {{
                "company_name": "extracted company name",
                "industry_type": "specific industry classification",
                "target_audience": "identified customer base",
                "key_services": ["list of main services/products"],
                "user_interaction_needs": ["what THIS company's users specifically ask for"],
                "agent_response_requirements": ["what tools agents need for THIS business's user queries"]
            }},
            "tool_modifications": {{
                "keep_tools": [
                    {{
                        "name": "tool name",
                        "reason": "SPECIFIC reason why THIS business's customers need this tool",
                        "use_cases": ["ACTUAL scenarios where THIS company's users would benefit"],
                        "customization": "how to configure specifically for THIS business"
                    }}
                ],
                "remove_tools": [
                    {{
                        "name": "tool name",
                        "reason": "SPECIFIC reason why THIS business's customers don't need this tool"
                    }}
                ],
                "add_tools": [
                    {{
                        "name": "specific tool name",
                        "type": "exact n8n node type",
                        "purpose": "SPECIFIC user requests for THIS business this tool handles",
                        "api_endpoint": "if applicable, the API endpoint or service",
                        "user_scenarios": ["SPECIFIC questions THIS company's customers would ask"],
                        "parameters": {{
                            "key_settings": "configuration specific to THIS business"
                        }},
                        "response_enhancement": "how this improves responses for THIS company's users"
                    }}
                ]
            }},
            "agent_capabilities": {{
                "enhanced_responses": ["new user queries specific to THIS business"],
                "business_specific_features": ["tools providing THIS company's information"],
                "integration_opportunities": ["external services THIS business's customers use"]
            }}
        }}

        REMEMBER: Every recommendation must be justified by actual customer needs for THIS specific business, not generic use cases.
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert AI agent tool consultant who makes business-specific recommendations. You must provide concrete, contextual reasoning for every tool decision. Avoid generic explanations like 'helps with user queries' or 'provides visual representation'. Instead, focus on specific customer scenarios and actual business needs. Be critical - most generic tools should be removed unless they serve a clear, specific purpose for that exact business type."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            print(f"✅ AI analysis completed")
            print(f"AI Response: {ai_response[:200]}...")
            
            # Parse JSON response
            try:
                recommendations = json.loads(ai_response)
                
                # Add AI analysis notes to the recommendations for later injection
                recommendations["ai_analysis_notes"] = {
                    "analysis_summary": ai_response[:500] + "..." if len(ai_response) > 500 else ai_response,
                    "timestamp": f"AI Analysis - {json.dumps({'date': 'auto-generated'})}"
                }
                
                return recommendations
            except json.JSONDecodeError:
                print("❌ Failed to parse AI response as JSON")
                return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
                
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {e}")
            print("⚠️ Proceeding without AI analysis - keeping all original tools")
            return {"keep_tools": available_tools, "remove_tools": [], "add_tools": []}
    
    def inject_ai_analysis_notes(self, workflow_data: Dict, ai_recommendations: Dict):
        """
        Inject AI analysis notes into workflow nodes.
        
        Args:
            workflow_data (Dict): Workflow data to modify
            ai_recommendations (Dict): AI analysis recommendations
        """
        if "nodes" not in workflow_data or "ai_analysis_notes" not in ai_recommendations:
            return
        
        analysis_summary = ai_recommendations["ai_analysis_notes"]["analysis_summary"]
        timestamp = ai_recommendations["ai_analysis_notes"]["timestamp"]
        
        # Find tool nodes and add AI analysis notes
        for node in workflow_data["nodes"]:
            node_name = node.get("name", "")
            node_type = node.get("type", "")
            
            # Only add notes to AI agent-usable tool nodes
            if ("tool" in node_name.lower() or 
                "tool" in node_type.lower() or
                node_type in ["@n8n/n8n-nodes-langchain.toolHttpRequest", 
                             "n8n-nodes-base.supabaseTool",
                             "@n8n/n8n-nodes-langchain.toolCalculator",
                             "@n8n/n8n-nodes-langchain.toolCode",
                             "@n8n/n8n-nodes-langchain.toolWebScraper",
                             "@n8n/n8n-nodes-langchain.toolWorkflowTool",
                             "n8n-nodes-base.httpRequest",
                             "n8n-nodes-base.googleSheets",
                             "n8n-nodes-base.airtable",
                             "n8n-nodes-base.slack",
                             "n8n-nodes-base.gmail"]):
                
                # Find specific analysis for this node
                node_analysis = ""
                # Check both direct structure and nested structure
                tool_mods = ai_recommendations.get("tool_modifications", {})
                keep_tools = tool_mods.get("keep_tools", ai_recommendations.get("keep_tools", []))
                remove_tools = tool_mods.get("remove_tools", ai_recommendations.get("remove_tools", []))
                
                # Check if this node is in keep_tools
                for keep_tool in keep_tools:
                    if isinstance(keep_tool, dict) and keep_tool.get("name", "") == node_name:
                        # Try both 'reason' and 'reasoning' field names
                        reason = keep_tool.get('reason', keep_tool.get('reasoning', 'No reasoning provided'))
                        node_analysis = f"✅ KEEP: {reason}"
                        break
                    elif isinstance(keep_tool, str) and keep_tool == node_name:
                        node_analysis = "✅ KEEP: Recommended by AI analysis"
                        break
                
                # Check if this node is in remove_tools
                for remove_tool in remove_tools:
                    if isinstance(remove_tool, dict) and remove_tool.get("name", "") == node_name:
                        # Try both 'reason' and 'reasoning' field names
                        reason = remove_tool.get('reason', remove_tool.get('reasoning', 'No reasoning provided'))
                        node_analysis = f"❌ REMOVE: {reason}"
                        break
                    elif isinstance(remove_tool, str) and remove_tool == node_name:
                        node_analysis = "❌ REMOVE: Flagged for removal by AI analysis"
                        break
                
                # If no specific analysis found, add general note
                if not node_analysis:
                    node_analysis = "🔍 ANALYZED: Included in AI business analysis"
                
                # Add the analysis note to the node
                existing_notes = node.get("notes", "")
                ai_note = f"\n\n--- AI ANALYSIS ---\n{node_analysis}\n{timestamp}"
                
                if existing_notes:
                    node["notes"] = existing_notes + ai_note
                else:
                    node["notes"] = ai_note.strip()
                
                print(f"📝 Added AI analysis note to '{node_name}': {node_analysis[:50]}...")
    
    def get_tool_description(self, tool) -> str:
        """
        Extract a meaningful description from a tool node or node type.
        
        Args:
            tool: Tool node data (Dict) or node type string
            
        Returns:
            str: Tool description
        """
        # Handle both string (node_type) and dict (tool object) inputs
        if isinstance(tool, str):
            tool_type = tool
            tool_name = ""
        else:
            tool_type = tool.get("type", "")
            tool_name = tool.get("name", "")
        
        # Map n8n node types to descriptions - focus on AI agent-usable tools
        descriptions = {
            # AI Agent Tools - tools that agents can use to respond to users
            "@n8n/n8n-nodes-langchain.toolHttpRequest": "HTTP API request tool - enables agents to call external APIs for user queries",
            "n8n-nodes-base.supabaseTool": "Supabase database tool - allows agents to query/update business data for users",
            "@n8n/n8n-nodes-langchain.toolCalculator": "Calculator tool - enables agents to perform calculations for users",
            "@n8n/n8n-nodes-langchain.toolCode": "Code execution tool - allows agents to run code and process data for users",
            "@n8n/n8n-nodes-langchain.toolWebScraper": "Web scraping tool - enables agents to fetch live web data for users",
            "@n8n/n8n-nodes-langchain.toolWorkflowTool": "Workflow execution tool - allows agents to trigger other workflows",
            "n8n-nodes-base.httpRequest": "HTTP request tool - enables agents to integrate with external services",
            "n8n-nodes-base.googleSheets": "Google Sheets tool - allows agents to read/write spreadsheet data",
            "n8n-nodes-base.airtable": "Airtable tool - enables agents to access database records",
            "n8n-nodes-base.slack": "Slack integration tool - allows agents to send messages/notifications",
            "n8n-nodes-base.gmail": "Gmail tool - enables agents to send emails on behalf of users",
            # Non-agent tools for reference
            "n8n-nodes-base.webhook": "Webhook trigger (workflow component, not agent tool)",
            "@n8n/n8n-nodes-langchain.agent": "AI agent (the agent itself, not a tool)",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi": "OpenAI chat model (agent brain, not a tool)",
            "@n8n/n8n-nodes-langchain.memoryBufferWindow": "Memory management (agent component, not a tool)",
            "n8n-nodes-base.respondToWebhook": "Webhook response (workflow component, not agent tool)",
            "n8n-nodes-base.stickyNote": "Documentation (workflow note, not agent tool)"
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
        Modify workflow tools based on detailed AI recommendations from business analysis.
        
        Args:
            workflow_data (Dict): Original workflow data
            recommendations (Dict): Detailed AI recommendations with business analysis
            
        Returns:
            Dict: Modified workflow data with precise customizations
        """
        if not recommendations:
            print("⚠️ No recommendations provided, keeping original workflow")
            return workflow_data
        
        modified_workflow = workflow_data.copy()
        
        # Extract tool modifications from nested structure
        tool_mods = recommendations.get("tool_modifications", {})
        if not tool_mods:
            # Fallback to old format
            tool_mods = recommendations
        
        # Process business analysis
        business_analysis = recommendations.get("business_analysis", {})
        if business_analysis:
            company_name = business_analysis.get("company_name", "Unknown")
            industry = business_analysis.get("industry_type", "Unknown")
            print(f"🏢 Customizing workflow for: {company_name} ({industry})")
        
        # Remove tools that don't fit the business model
        tools_to_remove = []
        remove_tools_data = tool_mods.get("remove_tools", [])
        
        for remove_item in remove_tools_data:
            if isinstance(remove_item, dict):
                tool_name = remove_item.get("name", "")
                reason = remove_item.get("reason", "Not specified")
                tools_to_remove.append(tool_name)
                print(f"❌ Removing '{tool_name}': {reason}")
            elif isinstance(remove_item, str):
                tools_to_remove.append(remove_item)
        
        if tools_to_remove and "nodes" in modified_workflow:
            original_count = len(modified_workflow["nodes"])
            modified_workflow["nodes"] = [
                node for node in modified_workflow["nodes"]
                if node.get("name", "") not in tools_to_remove
            ]
            removed_count = original_count - len(modified_workflow["nodes"])
            if removed_count > 0:
                print(f"✅ Removed {removed_count} tools based on business analysis")
        
        # Update connections to remove references to deleted nodes
        if "connections" in modified_workflow and tools_to_remove:
            self.clean_connections(modified_workflow, tools_to_remove)
        
        # Process kept tools with customizations
        keep_tools_data = tool_mods.get("keep_tools", [])
        for keep_item in keep_tools_data:
            if isinstance(keep_item, dict):
                tool_name = keep_item.get("name", "")
                customization = keep_item.get("customization", "")
                if customization:
                    print(f"🔧 Customizing '{tool_name}': {customization}")
        
        # Actually add new tools to the workflow
        add_tools = tool_mods.get("add_tools", [])
        if add_tools:
            print(f"🔧 Adding {len(add_tools)} AI-recommended tools to workflow:")
            for tool in add_tools:
                name = tool.get('name', 'Unknown')
                tool_type = tool.get('type', '@n8n/n8n-nodes-langchain.toolHttpRequest')
                purpose = tool.get('purpose', 'No purpose specified')
                api_endpoint = tool.get('api_endpoint', '')
                parameters = tool.get('parameters', {})
                
                print(f"   + Adding {name}: {purpose}")
                
                # Create new tool node with proper positioning and AI reasoning
                existing_nodes = modified_workflow.get("nodes", [])
                new_tool_node = self.create_tool_node(name, tool_type, api_endpoint, parameters, existing_nodes, tool)
                
                # Add to workflow nodes
                if "nodes" in modified_workflow:
                    modified_workflow["nodes"].append(new_tool_node)
                    print(f"     ✅ Added {name} to workflow")
                else:
                    modified_workflow["nodes"] = [new_tool_node]
                
                # Connect new tool to AI agent
                self.connect_tool_to_agent(modified_workflow, new_tool_node["name"])
        
        # Log workflow enhancements
        enhancements = recommendations.get("workflow_enhancements", {})
        if enhancements:
            optimizations = enhancements.get("optimization_areas", [])
            if optimizations:
                print(f"⚡ Optimization opportunities: {', '.join(optimizations)}")
        
        return modified_workflow
    
    def create_tool_node(self, name: str, tool_type: str, api_endpoint: str = "", parameters: Dict = None, existing_nodes: List = None, ai_reasoning: Dict = None) -> Dict:
        """
        Create a new tool node for the workflow.
        
        Args:
            name (str): Name of the tool
            tool_type (str): N8N node type
            api_endpoint (str): API endpoint if applicable
            parameters (Dict): Additional parameters
            existing_nodes (list): Existing nodes to calculate positioning
            ai_reasoning (Dict): AI analysis reasoning for this tool
            
        Returns:
            Dict: New tool node configuration
        """
        import uuid
        
        if parameters is None:
            parameters = {}
        
        if existing_nodes is None:
            existing_nodes = []
        
        # Generate unique ID
        node_id = str(uuid.uuid4())
        
        # Calculate position based on existing tool nodes
        tool_positions = []
        for node in existing_nodes:
            node_name = node.get("name", "").lower()
            node_type = node.get("type", "")
            # Find existing tools (same logic as filtering)
            if ("tool" in node_name or 
                "tool" in node_type.lower() or
                node_type in ["@n8n/n8n-nodes-langchain.toolHttpRequest", 
                             "n8n-nodes-base.supabaseTool",
                             "@n8n/n8n-nodes-langchain.toolCalculator",
                             "@n8n/n8n-nodes-langchain.toolCode",
                             "@n8n/n8n-nodes-langchain.toolWebScraper",
                             "@n8n/n8n-nodes-langchain.toolWorkflowTool",
                             "n8n-nodes-base.httpRequest",
                             "n8n-nodes-base.googleSheets",
                             "n8n-nodes-base.airtable",
                             "n8n-nodes-base.slack",
                             "n8n-nodes-base.gmail"]):
                position = node.get("position", [0, 0])
                if len(position) >= 2:
                    tool_positions.append(position)
        
        # Position new tool in same row as existing tools, 300 units to the right
        if tool_positions:
            # Find the rightmost tool position
            max_x = max(pos[0] for pos in tool_positions)
            # Use the Y position of the first tool for consistent row alignment
            base_y = tool_positions[0][1]
            position_x = max_x + 300
            position_y = base_y
        else:
            # Default position if no existing tools found
            position_x = 500
            position_y = 400
        
        # Create detailed notes from AI reasoning
        notes = self.create_tool_notes(name, ai_reasoning, parameters)
        
        # Base tool node structure
        tool_node = {
            "id": node_id,
            "name": name,
            "type": tool_type,
            "typeVersion": 1,
            "position": [position_x, position_y],
            "parameters": {}
        }
        
        # Add notes if they exist (n8n uses 'notes' field)
        if notes and notes.strip():
            tool_node["notes"] = notes
            print(f"     📝 Added notes to {name} (length: {len(notes)})")
        
        # Configure based on tool type
        if tool_type == "@n8n/n8n-nodes-langchain.toolHttpRequest":
            key_settings = parameters.get("key_settings", {})
            if isinstance(key_settings, dict):
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Tool for {name.lower()} operations",
                    "method": "GET",
                    "url": api_endpoint if api_endpoint else "https://api.example.com/endpoint",
                    "options": {},
                    **key_settings
                }
            else:
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Tool for {name.lower()} operations",
                    "method": "GET",
                    "url": api_endpoint if api_endpoint else "https://api.example.com/endpoint",
                    "options": {}
                }
        elif "supabase" in tool_type.lower():
            key_settings = parameters.get("key_settings", {})
            if isinstance(key_settings, dict):
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Database tool for {name.lower()}",
                    **key_settings
                }
            else:
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Database tool for {name.lower()}"
                }
        else:
            # Generic tool configuration
            key_settings = parameters.get("key_settings", {})
            if isinstance(key_settings, dict):
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Tool for {name.lower()}",
                    **key_settings
                }
            else:
                tool_node["parameters"] = {
                    "name": name,
                    "description": f"Tool for {name.lower()}"
                }
        
        return tool_node
    
    def create_tool_notes(self, name: str, ai_reasoning: Dict = None, parameters: Dict = None) -> str:
        """
        Create detailed notes for the tool node explaining the business reasoning and implementation ideas.
        
        Args:
            name (str): Tool name
            ai_reasoning (Dict): AI analysis data for this tool
            parameters (Dict): Tool parameters
            
        Returns:
            str: Formatted notes for the node
        """
        notes_sections = []
        
        # Debug logging
        print(f"🔍 Creating notes for tool: {name}")
        print(f"   AI reasoning keys: {list(ai_reasoning.keys()) if ai_reasoning else 'None'}")
        print(f"   Parameters keys: {list(parameters.keys()) if parameters else 'None'}")
        
        # Business Purpose Section
        if ai_reasoning:
            purpose = ai_reasoning.get("purpose", "")
            user_scenarios = ai_reasoning.get("user_scenarios", [])
            response_enhancement = ai_reasoning.get("response_enhancement", "")
            
            if purpose:
                notes_sections.append(f"🎯 **Business Purpose:**\n{purpose}")
            
            if user_scenarios:
                scenarios_text = "\n".join([f"• {scenario}" for scenario in user_scenarios])
                notes_sections.append(f"👥 **Customer Scenarios:**\n{scenarios_text}")
            
            if response_enhancement:
                notes_sections.append(f"⚡ **Response Enhancement:**\n{response_enhancement}")
        
        # Technical Implementation Section
        if parameters:
            api_endpoint = parameters.get("api_endpoint", "")
            key_settings = parameters.get("key_settings", "")
            
            if api_endpoint:
                notes_sections.append(f"🔗 **API Endpoint:**\n{api_endpoint}")
            
            if key_settings and isinstance(key_settings, str):
                notes_sections.append(f"⚙️ **Configuration:**\n{key_settings}")
        
        # N8N Best Practices Section
        best_practices = [
            "• Configure proper error handling for API failures",
            "• Set appropriate timeout values for external calls", 
            "• Use environment variables for sensitive data",
            "• Test with sample data before production use",
            "• Monitor API rate limits and usage"
        ]
        notes_sections.append(f"📋 **Implementation Notes:**\n" + "\n".join(best_practices))
        
        # AI Analysis Timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes_sections.append(f"🤖 **AI Analysis Generated:** {timestamp}")
        
        final_notes = "\n\n".join(notes_sections)
        print(f"   Generated notes length: {len(final_notes)}")
        print(f"   Notes preview: {final_notes[:100]}...")
        
        return final_notes
    
    def connect_tool_to_agent(self, workflow_data: Dict, tool_name: str):
        """
        Connect a new tool to the AI agent in the workflow connections.
        
        Args:
            workflow_data (Dict): Workflow data containing connections
            tool_name (str): Name of the tool to connect
        """
        if "connections" not in workflow_data:
            workflow_data["connections"] = {}
        
        # Find the AI agent node
        agent_node_name = None
        for node in workflow_data.get("nodes", []):
            if node.get("type") == "@n8n/n8n-nodes-langchain.agent":
                agent_node_name = node.get("name")
                break
        
        if agent_node_name:
            # Add tool to agent's connections
            if agent_node_name not in workflow_data["connections"]:
                workflow_data["connections"][agent_node_name] = {}
            
            if "ai_tool" not in workflow_data["connections"][agent_node_name]:
                workflow_data["connections"][agent_node_name]["ai_tool"] = []
            
            # Add connection to the new tool
            workflow_data["connections"][agent_node_name]["ai_tool"].append([
                {
                    "node": tool_name,
                    "type": "ai_tool",
                    "index": 0
                }
            ])
            
            print(f"     🔗 Connected {tool_name} to AI agent")
        else:
            print(f"     ⚠️ Could not find AI agent to connect {tool_name}")
    
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
        
        # Debug: Check actual node structure to find notes field
        print(f"\n🔍 DEBUG: Examining node structure for notes field...")
        for i, node in enumerate(template_data.get('nodes', [])[:2]):  # Check first 2 nodes
            print(f"Node {i+1} fields: {list(node.keys())}")
            if any(field for field in node.keys() if 'note' in field.lower()):
                print(f"Found note-related field: {[field for field in node.keys() if 'note' in field.lower()]}")
            # Show full node structure for first node
            if i == 0:
                print(f"Full node structure: {json.dumps(node, indent=2)[:500]}...")
        
        # Step 3: Read business description
        business_description = self.read_business_description(business_description_file)
        
        # Step 4: Extract available tools from template
        all_nodes = template_data.get('nodes', [])
        print(f"📋 Found {len(all_nodes)} total nodes in template workflow")
        
        # Step 5: Analyze with AI and get tool recommendations
        print(f"\n🤖 Analyzing business needs with AI...")
        ai_recommendations = self.analyze_business_with_ai(business_description, all_nodes)
        
        # Step 6: Modify workflow tools based on AI recommendations
        print(f"\n🔧 Customizing workflow based on AI analysis...")
        customized_workflow = self.modify_workflow_tools(template_data, ai_recommendations)
        
        # Step 6.5: Inject AI analysis notes into workflow nodes
        print(f"\n📝 Adding AI analysis notes to workflow nodes...")
        self.inject_ai_analysis_notes(customized_workflow, ai_recommendations)
        
        # Step 6.6: Ensure the workflow name is set correctly
        customized_workflow['name'] = new_name
        
        # Step 7: Update the new workflow with customized data
        print(f"\n📤 Updating workflow with AI-customized tools...")
        success = self.update_workflow(new_workflow_id, customized_workflow)
        
        if success:
            # Step 8: Save AI analysis report
            try:
                report_filename = f"ai_analysis_report_{new_workflow_id}.json"
                
                # Ensure we have valid data to save
                if not ai_recommendations:
                    ai_recommendations = {"error": "AI analysis failed or returned empty response"}
                
                report_data = {
                    "workflow_id": new_workflow_id,
                    "workflow_name": new_name,
                    "template_id": template_id,
                    "business_description_file": business_description_file,
                    "business_description": business_description,
                    "ai_recommendations": ai_recommendations,
                    "original_node_count": len(all_nodes),
                    "final_node_count": len(customized_workflow.get('nodes', [])),
                    "timestamp": __import__('time').time(),
                    "analysis_status": "completed" if ai_recommendations and "error" not in ai_recommendations else "failed"
                }
                
                with open(report_filename, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2)
                print(f"✅ AI analysis report saved: {report_filename}")
            except Exception as e:
                print(f"⚠️ Could not save AI analysis report: {e}")
                # Create minimal report even if there's an error
                try:
                    with open(f"ai_analysis_report_{new_workflow_id}.json", 'w') as f:
                        json.dump({"error": str(e), "workflow_id": new_workflow_id}, f, indent=2)
                except:
                    pass
            
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
    NEW_WORKFLOW_NAME = "FK_Squidgy_Testing_Creating_New_Agent_Workflow"
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
