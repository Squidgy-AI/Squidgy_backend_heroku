# main.py - Complete integration with conversational handler
from typing import Dict, Any, Optional, AsyncGenerator, List
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import logging
import time
import uuid
import asyncio
from datetime import datetime
from enum import Enum
from supabase import create_client, Client
import os

# Initialize FastAPI app
app = FastAPI()
logger = logging.getLogger(__name__)
active_connections: Dict[str, WebSocket] = {}
streaming_sessions: Dict[str, Dict[str, Any]] = {}

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Models
class N8nMainRequest(BaseModel):
    user_id: str
    user_mssg: str
    session_id: str
    agent_name: str
    timestamp_of_call_made: Optional[str] = None

class N8nResponse(BaseModel):
    user_id: str
    agent_name: str
    agent_response: str
    responses: List[Dict[str, Any]]
    timestamp: str
    status: str

class StreamUpdate(BaseModel):
    type: str
    user_id: str
    agent_name: Optional[str] = None
    agent_names: Optional[str] = None
    message: str
    progress: int
    agent_response: Optional[str] = None
    metadata: dict

class ConversationState(Enum):
    INITIAL = "initial"
    COLLECTING_INFO = "collecting_info"
    PROCESSING = "processing"
    COMPLETE = "complete"

# Conversational Handler Class
class ConversationalHandler:
    def __init__(self, supabase_client, n8n_webhook_url: str):
        self.supabase = supabase_client
        self.n8n_url = n8n_webhook_url
        self.conversation_states: Dict[str, Dict[str, Any]] = {}
        
    async def get_conversation_context(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Get conversation context from Supabase"""
        try:
            result = self.supabase.rpc('get_conversation_context', {
                'p_session_id': session_id,
                'p_user_id': user_id
            }).execute()
            
            if result.data:
                return result.data[0]
            return {
                'session_id': session_id,
                'user_id': user_id,
                'website_data': None,
                'client_niche': None,
                'conversation_history': []
            }
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return {}
    
    async def check_agent_requirements(self, agent_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check what information is missing for the agent"""
        missing_info = []
        
        # Define requirements per agent
        agent_requirements = {
            'presaleskb': {
                'website': lambda ctx: ctx.get('website_data') is not None,
                'niche': lambda ctx: ctx.get('client_niche') is not None
            },
            'manager': {
                'website': lambda ctx: ctx.get('website_data') is not None
            },
            're-engage': {
                'website': lambda ctx: ctx.get('website_data') is not None
            }
        }
        
        if agent_name in agent_requirements:
            for req_name, check_func in agent_requirements[agent_name].items():
                if not check_func(context):
                    missing_info.append(req_name)
        
        return {
            'has_all_required': len(missing_info) == 0,
            'missing_info': missing_info
        }
    
    async def analyze_user_intent(self, user_message: str, agent_name: str) -> Dict[str, Any]:
        """Analyze what the user is asking for"""
        message_lower = user_message.lower()
        
        # Check if this is a follow-up response
        if any(keyword in message_lower for keyword in ['http://', 'https://', '.com', '.org', '.net']):
            return {'type': 'website_provided', 'value': user_message.strip()}
        
        # Check if user is providing niche information
        niche_keywords = ['we are', 'our business', 'we specialize', 'our company', 'we do', 'our focus']
        if any(keyword in message_lower for keyword in niche_keywords):
            return {'type': 'niche_provided', 'value': user_message.strip()}
        
        # Check if asking about pricing/quotes (needs website info)
        pricing_keywords = ['price', 'cost', 'quote', 'roi', 'investment', 'budget']
        needs_website = any(keyword in message_lower for keyword in pricing_keywords)
        
        return {
            'type': 'general_query',
            'needs_website': needs_website,
            'original_message': user_message
        }
    
    async def generate_contextual_prompt(self, user_message: str, missing_info: List[str], context: Dict[str, Any]) -> str:
        """Generate a prompt that will make the agent ask for missing info naturally"""
        conversation_history = context.get('conversation_history', [])
        
        # Build conversation context
        history_text = "\n".join([f"{msg['role']}: {msg['message']}" for msg in conversation_history[-5:]])
        
        # Create a prompt that instructs the agent to collect missing info
        prompt = f"""Previous conversation:
{history_text}

User's current message: {user_message}

You need to collect the following information before you can fully answer: {', '.join(missing_info)}

Instructions:
1. First acknowledge the user's question
2. If you can provide partial information, do so
3. Then naturally ask for the missing information
4. Explain why you need this information
5. Be conversational and helpful

Missing information needed:
{chr(10).join([f"- {info}: " + self.get_info_description(info) for info in missing_info])}

Respond naturally while collecting this information."""
        
        return prompt
    
    def get_info_description(self, info_type: str) -> str:
        """Get description for each type of information"""
        descriptions = {
            'website': "Company website URL to understand their business and provide accurate quotes",
            'niche': "Business niche or industry focus to tailor recommendations",
            'property_address': "Property address for location-specific analysis",
            'budget': "Budget range to suggest appropriate solutions",
            'timeline': "Implementation timeline to plan accordingly"
        }
        return descriptions.get(info_type, f"{info_type} information")
    
    async def process_follow_up_info(self, session_id: str, user_id: str, info_type: str, info_value: str):
        """Process and store follow-up information"""
        try:
            if info_type == 'website':
                # Analyze website using Perplexity
                analysis = await self.analyze_website_with_perplexity(info_value)
                
                # Store in website_data table
                self.supabase.table('website_data').upsert({
                    'session_id': session_id,
                    'url': info_value,
                    'analysis': json.dumps(analysis) if analysis else None
                }).execute()
                
                # Extract niche from analysis if available
                if analysis and 'niche' in analysis:
                    self.supabase.table('conversation_context').upsert({
                        'session_id': session_id,
                        'user_id': user_id,
                        'client_niche': analysis['niche']
                    }).execute()
            
            elif info_type == 'niche':
                # Update conversation context
                self.supabase.table('conversation_context').upsert({
                    'session_id': session_id,
                    'user_id': user_id,
                    'client_niche': info_value
                }).execute()
            
            # Update other fields as needed
            else:
                self.supabase.rpc('update_conversation_context', {
                    'p_session_id': session_id,
                    'p_user_id': user_id,
                    'p_field': info_type,
                    'p_value': info_value
                }).execute()
                
        except Exception as e:
            logger.error(f"Error processing follow-up info: {str(e)}")
    
    async def analyze_website_with_perplexity(self, url: str) -> Optional[Dict[str, Any]]:
        """Analyze website using Perplexity API"""
        try:
            headers = {
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""Please analyze the website {url} and provide a summary in exactly this format:
--- *Company name*: [Extract company name]
--- *Website*: {url}
--- *Contact Information*: [Any available contact details]
--- *Description*: [2-3 sentence summary of what the company does]
--- *Tags*: [Main business categories, separated by periods]
--- *Takeaways*: [Key business value propositions]
--- *Niche*: [Specific market focus or specialty]"""
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json={
                        "model": "sonar-reasoning-pro",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    analysis_text = result["choices"][0]["message"]["content"]
                    
                    # Parse the analysis into structured data
                    parsed = self.parse_perplexity_analysis(analysis_text)
                    return parsed
                    
        except Exception as e:
            logger.error(f"Error analyzing website: {str(e)}")
            return None
    
    def parse_perplexity_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse Perplexity analysis into structured format"""
        parsed = {}
        lines = analysis_text.split('\n')
        
        for line in lines:
            if '*Company name*:' in line:
                parsed['company_name'] = line.split(':', 1)[1].strip()
            elif '*Description*:' in line:
                parsed['description'] = line.split(':', 1)[1].strip()
            elif '*Niche*:' in line:
                parsed['niche'] = line.split(':', 1)[1].strip()
            elif '*Tags*:' in line:
                parsed['tags'] = line.split(':', 1)[1].strip()
        
        return parsed
    
    async def handle_message(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main handler for processing messages with conversational flow"""
        user_id = request_data['user_id']
        session_id = request_data['session_id']
        user_message = request_data['user_mssg']
        agent_name = request_data['agent_name']
        
        # Get conversation context
        context = await self.get_conversation_context(session_id, user_id)
        
        # Analyze user intent
        intent = await self.analyze_user_intent(user_message, agent_name)
        
        # Handle follow-up information
        if intent['type'] in ['website_provided', 'niche_provided']:
            info_type = 'website' if intent['type'] == 'website_provided' else 'niche'
            await self.process_follow_up_info(session_id, user_id, info_type, intent['value'])
            
            # Update context after processing
            context = await self.get_conversation_context(session_id, user_id)
        
        # Check agent requirements
        requirements = await self.check_agent_requirements(agent_name, context)
        
        # Prepare n8n payload
        n8n_payload = request_data.copy()
        
        # If missing critical info, modify the prompt to collect it
        if not requirements['has_all_required'] and intent['type'] == 'general_query':
            # Add context to make agent ask for missing info
            contextual_prompt = await self.generate_contextual_prompt(
                user_message, 
                requirements['missing_info'], 
                context
            )
            n8n_payload['user_mssg'] = contextual_prompt
            n8n_payload['_original_message'] = user_message
            n8n_payload['_missing_info'] = requirements['missing_info']
        
        # Return the prepared payload
        return n8n_payload
    
    async def save_to_history(self, session_id: str, user_id: str, user_message: str, agent_response: str):
        """Save messages to chat history"""
        try:
            # Save user message
            self.supabase.table('chat_history').insert({
                'session_id': session_id,
                'user_id': user_id,
                'sender': 'user',
                'message': user_message,
                'timestamp': datetime.now().isoformat()
            }).execute()
            
            # Save agent response
            if agent_response:
                self.supabase.table('chat_history').insert({
                    'session_id': session_id,
                    'user_id': user_id,
                    'sender': 'agent',
                    'message': agent_response,
                    'timestamp': datetime.now().isoformat()
                }).execute()
                
        except Exception as e:
            logger.error(f"Error saving to history: {str(e)}")

# Initialize conversational handler
conversational_handler = ConversationalHandler(
    supabase_client=supabase,
    n8n_webhook_url="https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d"
)

# Your existing save_message_to_history function
async def save_message_to_history(session_id: str, sender: str, message: str):
    """Save a message to the appropriate history table"""
    await conversational_handler.save_to_history(
        session_id=session_id,
        user_id="", # You might need to pass user_id here
        user_message=message if sender == "User" else "",
        agent_response=message if sender == "AI" else ""
    )

# n8n integration function with conversational logic
async def call_n8n_webhook(payload: Dict[str, Any]):
    """Call the n8n webhook and return the response"""
    n8n_url = "https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(n8n_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"N8N HTTP error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"N8N error: {e.response.text}")
        except Exception as e:
            logger.error(f"N8N request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to n8n: {str(e)}")

# Streaming endpoint to receive updates from n8n
@app.post("/api/stream")
async def receive_stream_update(update: StreamUpdate):
    """Endpoint that receives streaming updates from n8n and forwards to WebSocket clients"""
    try:
        connection_id = f"{update.user_id}_{update.metadata.get('session_id', '')}"
        
        # Store the update for HTTP streaming
        session_key = f"{update.user_id}:{update.metadata.get('request_id', '')}"
        if session_key not in streaming_sessions:
            streaming_sessions[session_key] = {
                "updates": [],
                "complete": False
            }
        
        streaming_sessions[session_key]["updates"].append(update.dict())
        
        # Mark as complete if this is the final update
        if update.type in ["complete", "final"]:
            streaming_sessions[session_key]["complete"] = True
        
        # Forward to WebSocket if client is connected
        if connection_id in active_connections:
            websocket = active_connections[connection_id]
            await websocket.send_json({
                "type": update.type,
                "agent": update.agent_name or update.agent_names,
                "message": update.message,
                "progress": update.progress,
                "requestId": update.metadata.get("request_id"),
                "metadata": update.metadata,
                "timestamp": int(time.time() * 1000)
            })
            
            # Send the actual response if this is the complete update
            if update.type == "complete" and update.agent_response:
                await websocket.send_json({
                    "type": "agent_response",
                    "agent": update.agent_name,
                    "message": update.agent_response,
                    "requestId": update.metadata.get("request_id"),
                    "final": True,
                    "timestamp": int(time.time() * 1000)
                })
        
        return {"status": "received", "connection_id": connection_id}
        
    except Exception as e:
        logger.error(f"Error in receive_stream_update: {str(e)}")
        return {"status": "error", "error": str(e)}

# Streaming n8n integration
async def stream_n8n_response(payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Stream response from n8n webhook using SSE"""
    n8n_stream_url = "https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d/stream"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("POST", n8n_stream_url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        yield f"data: {line}\n\n"
        except Exception as e:
            logger.error(f"N8N streaming error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

# Main n8n request endpoint with conversational logic
@app.post("/n8n_main_req")
async def n8n_main_request(request: N8nMainRequest):
    """Handle main request to n8n workflow with conversational logic"""
    try:
        # Generate request_id for tracking
        request_id = str(uuid.uuid4())
        
        # Add timestamp if not provided
        if not request.timestamp_of_call_made:
            request.timestamp_of_call_made = datetime.now().isoformat()
        
        # Prepare request data
        request_data = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made,
            "request_id": request_id
        }
        
        # Process through conversational handler
        n8n_payload = await conversational_handler.handle_message(request_data)
        
        logger.info(f"Sending to n8n: {n8n_payload}")
        
        # Call n8n webhook
        n8n_response = await call_n8n_webhook(n8n_payload)
        
        logger.info(f"Received from n8n: {n8n_response}")
        
        # Format response
        formatted_response = {
            "user_id": n8n_response.get("user_id", request.user_id),
            "agent_name": n8n_response.get("agent_name", request.agent_name),
            "agent_response": n8n_response.get("agent_response", n8n_response.get("agent_responses", "")),
            "responses": n8n_response.get("responses", []),
            "timestamp": n8n_response.get("timestamp", datetime.now().isoformat()),
            "status": n8n_response.get("status", "success"),
            "request_id": request_id,
            "conversation_state": n8n_response.get("conversation_state", "complete"),
            "missing_info": n8n_response.get("missing_info", [])
        }
        
        # Save to history
        await conversational_handler.save_to_history(
            request.session_id,
            request.user_id,
            request_data.get("_original_message", request.user_mssg),
            formatted_response["agent_response"]
        )
        
        return formatted_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in n8n_main_request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Streaming n8n request endpoint
@app.post("/n8n_main_req_stream")
async def n8n_main_request_stream(request: N8nMainRequest):
    """Handle streaming request to n8n workflow"""
    try:
        # Add timestamp if not provided
        if not request.timestamp_of_call_made:
            request.timestamp_of_call_made = datetime.now().isoformat()
        
        # Prepare request data
        request_data = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made
        }
        
        # Process through conversational handler
        n8n_payload = await conversational_handler.handle_message(request_data)
        
        # Return streaming response
        return StreamingResponse(
            stream_n8n_response(n8n_payload),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error in n8n_main_request_stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Async handler for n8n requests with conversational logic
async def process_n8n_request_async(payload: dict, websocket: WebSocket, request_id: str):
    """Process n8n request asynchronously with conversational logic"""
    try:
        # Process through conversational handler
        n8n_payload = await conversational_handler.handle_message(payload)
        
        # Call n8n webhook
        n8n_response = await call_n8n_webhook(n8n_payload)
        
        # Check if we got a direct response (non-streaming)
        if n8n_response.get("status") == "success" and "agent_response" in n8n_response:
            agent_response = n8n_response.get("agent_response", "")
            
            # Send final response
            await websocket.send_json({
                "type": "agent_response",
                "agent": n8n_response.get("agent_name", "Squidgy"),
                "message": agent_response,
                "requestId": request_id,
                "final": True,
                "timestamp": int(time.time() * 1000),
                "conversation_state": n8n_response.get("conversation_state", "complete"),
                "missing_info": n8n_response.get("missing_info", [])
            })
            
            # Save to chat history
            await save_message_to_history(payload["session_id"], "User", payload.get("_original_message", payload["user_mssg"]))
            await save_message_to_history(payload["session_id"], "AI", agent_response)
            
    except Exception as e:
        logger.error(f"Error in process_n8n_request_async: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing request: {str(e)}",
            "requestId": request_id,
            "timestamp": int(time.time() * 1000)
        })

# WebSocket endpoint with streaming support and conversational logic
@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint that routes through n8n with streaming support and conversational logic"""
    connection_id = f"{user_id}_{session_id}"
    logger.info(f"New WebSocket connection: {connection_id}")
    
    # Accept the connection
    await websocket.accept()
    
    # Store connection
    active_connections[connection_id] = websocket
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connection_status",
            "status": "connected",
            "message": "WebSocket connection established",
            "timestamp": int(time.time() * 1000)
        })
        
        # Handle incoming messages
        while True:
            # Wait for a message from the client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Generate a unique request ID
            request_id = message_data.get("requestId", str(uuid.uuid4()))
            
            # Extract the message content
            user_input = message_data.get("message", "").strip()
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "ack",
                "requestId": request_id,
                "message": "Message received, processing...",
                "timestamp": int(time.time() * 1000)
            })
            
            # Prepare n8n request with request_id
            n8n_payload = {
                "user_id": user_id,
                "user_mssg": user_input,
                "session_id": session_id,
                "agent_name": message_data.get("agent", "re-engage"),
                "timestamp_of_call_made": datetime.now().isoformat(),
                "request_id": request_id
            }
            
            # Call n8n asynchronously with conversational logic
            asyncio.create_task(
                process_n8n_request_async(n8n_payload, websocket, request_id)
            )
            
    except WebSocketDisconnect:
        # Clean up on disconnect
        if connection_id in active_connections:
            del active_connections[connection_id]
        logger.info(f"Client disconnected: {connection_id}")
        
    except Exception as e:
        logger.exception(f"WebSocket error: {str(e)}")
        if connection_id in active_connections:
            del active_connections[connection_id]

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_connections": len(active_connections),
        "streaming_sessions": len(streaming_sessions)
    }

# Process chat via n8n with conversational logic
async def process_chat_via_n8n(user_id: str, session_id: str, user_input: str, request_id: str, connection_id: str, websocket: WebSocket):
    """Process chat through n8n workflow with conversational logic"""
    try:
        # Default to re-engage agent if not specified
        agent_name = "re-engage"
        
        # Prepare n8n payload
        n8n_payload = {
            "user_id": user_id,
            "user_mssg": user_input,
            "session_id": session_id,
            "agent_name": agent_name,
            "timestamp_of_call_made": datetime.now().isoformat(),
            "request_id": request_id
        }
        
        # Process through conversational handler
        processed_payload = await conversational_handler.handle_message(n8n_payload)
        
        # Call n8n workflow
        n8n_response = await call_n8n_webhook(processed_payload)
        
        # Process n8n response
        if n8n_response.get("status") == "success":
            # Extract the response message
            agent_response = n8n_response.get("agent_response", n8n_response.get("agent_responses", ""))
            
            # Send final response to websocket
            await websocket.send_json({
                "type": "agent_response",
                "agent": n8n_response.get("agent_name", "Squidgy"),
                "message": agent_response,
                "requestId": request_id,
                "final": True,
                "timestamp": int(time.time() * 1000),
                "conversation_state": n8n_response.get("conversation_state", "complete"),
                "missing_info": n8n_response.get("missing_info", [])
            })
            
            # Save to chat history
            await save_message_to_history(session_id, "User", user_input)
            await save_message_to_history(session_id, "AI", agent_response)
            
        else:
            # Handle error from n8n
            error_message = n8n_response.get("error", "Unknown error occurred")
            await websocket.send_json({
                "type": "error",
                "message": error_message,
                "requestId": request_id,
                "timestamp": int(time.time() * 1000)
            })
            
    except Exception as e:
        logger.error(f"Error in process_chat_via_n8n: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing request: {str(e)}",
            "requestId": request_id,
            "timestamp": int(time.time() * 1000)
        })

# Process chat via n8n with streaming and conversational logic
async def process_chat_via_n8n_streaming(user_id: str, session_id: str, user_input: str, request_id: str, connection_id: str, websocket: WebSocket):
    """Process chat through n8n workflow with streaming support and conversational logic"""
    try:
        # Default to re-engage agent if not specified
        agent_name = "re-engage"
        
        # Prepare n8n payload
        n8n_payload = {
            "user_id": user_id,
            "user_mssg": user_input,
            "session_id": session_id,
            "agent_name": agent_name,
            "timestamp_of_call_made": datetime.now().isoformat(),
            "request_id": request_id
        }
        
        # Process through conversational handler
        processed_payload = await conversational_handler.handle_message(n8n_payload)
        
        # Create a session for this request
        session_key = f"{user_id}:{request_id}"
        streaming_sessions[session_key] = {
            "updates": [],
            "complete": False
        }
        
        # Call n8n webhook with streaming support
        n8n_url = "https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Make the call to n8n (this will trigger the workflow)
                response = await client.post(n8n_url, json=processed_payload)
                
                # If we get an immediate response, send it
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "success":
                        agent_response = result.get("agent_response", result.get("agent_responses", ""))
                        
                        await websocket.send_json({
                            "type": "agent_response",
                            "agent": result.get("agent_name", "Squidgy"),
                            "message": agent_response,
                            "requestId": request_id,
                            "final": True,
                            "timestamp": int(time.time() * 1000),
                            "conversation_state": result.get("conversation_state", "complete"),
                            "missing_info": result.get("missing_info", [])
                        })
                        
                        # Save to chat history
                        await save_message_to_history(session_id, "User", user_input)
                        await save_message_to_history(session_id, "AI", agent_response)
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)
                    
            except Exception as e:
                logger.error(f"Error calling n8n: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing request: {str(e)}",
                    "requestId": request_id,
                    "timestamp": int(time.time() * 1000)
                })
                
    except Exception as e:
        logger.error(f"Error in process_chat_via_n8n_streaming: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing request: {str(e)}",
            "requestId": request_id,
            "timestamp": int(time.time() * 1000)
        })
    finally:
        # Clean up streaming session
        session_key = f"{user_id}:{request_id}"
        if session_key in streaming_sessions:
            del streaming_sessions[session_key]

# CORS middleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)