# main.py
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

# Your existing imports and setup
app = FastAPI()
logger = logging.getLogger(__name__)
active_connections: Dict[str, WebSocket] = {}

# Your existing functions (save_message_to_history, etc.)
async def save_message_to_history(session_id: str, sender: str, message: str):
    """Save a message to the appropriate history table"""
    # Implementation from your original code
    # This function should already exist in your main.py
    pass

# Updated Models with consistent field names
class N8nMainRequest(BaseModel):
    user_id: str
    user_mssg: str  # Keep the typo to match existing n8n workflow
    session_id: str
    agent_name: str  # Changed from agent_names to agent_name
    timestamp_of_call_made: Optional[str] = None

class N8nResponse(BaseModel):
    user_id: str
    agent_name: str  # Changed from agent_names to agent_name
    agent_response: str  # Changed from agent_responses to agent_response
    responses: List[Dict[str, Any]]
    timestamp: str
    status: str

# n8n integration function
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

# Main n8n request endpoint
@app.post("/n8n_main_req")
async def n8n_main_request(request: N8nMainRequest):
    """Handle main request to n8n workflow"""
    try:
        # Add timestamp if not provided
        if not request.timestamp_of_call_made:
            request.timestamp_of_call_made = datetime.now().isoformat()
        
        # Prepare payload for n8n
        n8n_payload = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made
        }
        
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
            "status": n8n_response.get("status", "success")
        }
        
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
        
        # Prepare payload for n8n
        n8n_payload = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made
        }
        
        # Return streaming response
        return StreamingResponse(
            stream_n8n_response(n8n_payload),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error in n8n_main_request_stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint with n8n integration
@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint that routes through n8n"""
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
            
            # Generate a unique request ID if not provided
            request_id = message_data.get("requestId", str(uuid.uuid4()))
            
            # Extract the message content
            user_input = message_data.get("message", "").strip()
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "ack",
                "requestId": request_id,
                "message": "Message received, processing via n8n...",
                "timestamp": int(time.time() * 1000)
            })
            
            # Route through n8n instead of direct processing
            asyncio.create_task(
                process_chat_via_n8n(
                    user_id, 
                    session_id, 
                    user_input, 
                    request_id, 
                    connection_id,
                    websocket
                )
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

# Process chat via n8n
async def process_chat_via_n8n(user_id: str, session_id: str, user_input: str, request_id: str, connection_id: str, websocket: WebSocket):
    """Process chat through n8n workflow"""
    try:
        # Default to ProductManager agent if not specified
        agent_name = "re-engage"  # This maps to ProductManager
        
        # Prepare n8n payload
        n8n_payload = {
            "user_id": user_id,
            "user_mssg": user_input,
            "session_id": session_id,
            "agent_name": agent_name,
            "timestamp_of_call_made": datetime.now().isoformat()
        }
        
        # Call n8n workflow
        n8n_response = await call_n8n_webhook(n8n_payload)
        
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
                "timestamp": int(time.time() * 1000)
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