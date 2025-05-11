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

# Add streaming sessions storage
streaming_sessions: Dict[str, Dict[str, Any]] = {}

# Your existing functions (you'll need to add these from your original file)
async def save_message_to_history(session_id: str, sender: str, message: str):
    """Save a message to the appropriate history table"""
    # Implementation from your original code
    # This function should already exist in your main.py
    pass

# Models
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

class StreamUpdate(BaseModel):
    type: str  # acknowledgment, intermediate, tools_usage, complete, final
    user_id: str
    agent_name: Optional[str] = None
    agent_names: Optional[str] = None
    message: str
    progress: int
    agent_response: Optional[str] = None
    metadata: dict

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

# Main n8n request endpoint with request_id support
@app.post("/n8n_main_req")
async def n8n_main_request(request: N8nMainRequest):
    """Handle main request to n8n workflow"""
    try:
        # Generate request_id for tracking
        request_id = str(uuid.uuid4())
        
        # Add timestamp if not provided
        if not request.timestamp_of_call_made:
            request.timestamp_of_call_made = datetime.now().isoformat()
        
        # Prepare payload for n8n with request_id
        n8n_payload = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made,
            "request_id": request_id  # Add this for tracking
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
            "status": n8n_response.get("status", "success"),
            "request_id": request_id  # Include in response
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

# Async handler for n8n requests
async def process_n8n_request_async(payload: dict, websocket: WebSocket, request_id: str):
    """Process n8n request asynchronously"""
    try:
        # Call n8n webhook
        n8n_response = await call_n8n_webhook(payload)
        
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
                "timestamp": int(time.time() * 1000)
            })
            
            # Save to chat history
            await save_message_to_history(payload["session_id"], "User", payload["user_mssg"])
            await save_message_to_history(payload["session_id"], "AI", agent_response)
            
    except Exception as e:
        logger.error(f"Error in process_n8n_request_async: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing request: {str(e)}",
            "requestId": request_id,
            "timestamp": int(time.time() * 1000)
        })

# WebSocket endpoint with streaming support
@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint that routes through n8n with streaming support"""
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
                "message": "Message received, processing via n8n...",
                "timestamp": int(time.time() * 1000)
            })
            
            # Prepare n8n request with request_id
            n8n_payload = {
                "user_id": user_id,
                "user_mssg": user_input,
                "session_id": session_id,
                "agent_name": "re-engage",  # Default agent
                "timestamp_of_call_made": datetime.now().isoformat(),
                "request_id": request_id
            }
            
            # Call n8n asynchronously
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

# Process chat via n8n (backward compatibility)
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

# Process chat via n8n with streaming
async def process_chat_via_n8n_streaming(user_id: str, session_id: str, user_input: str, request_id: str, connection_id: str, websocket: WebSocket):
    """Process chat through n8n workflow with streaming support"""
    try:
        # Default to ProductManager agent if not specified
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
                response = await client.post(n8n_url, json=n8n_payload)
                
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
                            "timestamp": int(time.time() * 1000)
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

# CORS middleware (add this if not already present)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
