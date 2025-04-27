# n8n_integration.py
import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Base URL for n8n webhook
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')

async def send_to_n8n(
    agent: str,
    message: str,
    session_id: str,
    request_id: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Send a message to n8n workflow
    
    Args:
        agent: The agent type (e.g., 'ProductManager')
        message: The message content
        session_id: The current session/conversation ID
        request_id: Optional request ID for tracking
        additional_data: Any additional data to include
        
    Returns:
        Dict with success status and response data
    """
    if not N8N_WEBHOOK_URL:
        logger.error("N8N_WEBHOOK_URL not configured")
        return {"success": False, "error": "N8N webhook URL not configured"}
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "agent": agent,
                "message": message,
                "sessionId": session_id,
                "timestamp": datetime.now().isoformat(),
                "requestId": request_id
            }
            
            if additional_data:
                payload.update(additional_data)
                
            # Log the request to database
            await log_n8n_request(session_id, agent, message, payload)
            
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Error from n8n: {response.status} - {error_text}")
                    
                    # Log the error response
                    await log_n8n_response(
                        session_id, 
                        agent, 
                        message, 
                        {"status": response.status, "error": error_text},
                        "error"
                    )
                    
                    return {
                        "success": False, 
                        "status": response.status,
                        "error": error_text
                    }
                
                data = await response.json()
                
                # Log the successful response
                await log_n8n_response(
                    session_id, 
                    agent, 
                    message, 
                    data,
                    "success"
                )
                
                return {"success": True, "data": data}
                
    except Exception as e:
        logger.error(f"Error sending to n8n: {str(e)}")
        
        # Log the error
        await log_n8n_response(
            session_id, 
            agent, 
            message, 
            {"error": str(e)},
            "error"
        )
        
        return {"success": False, "error": str(e)}

async def log_n8n_request(
    session_id: str,
    agent: str,
    message: str,
    payload: Dict[str, Any]
):
    """Log an n8n request to the database"""
    try:
        query = """
        INSERT INTO n8n_logs (session_id, agent, message, request_payload, status)
        VALUES ($1, $2, $3, $4, 'pending')
        """
        
        from database import execute
        await execute(query, session_id, agent, message, json.dumps(payload))
    except Exception as e:
        logger.error(f"Error logging n8n request: {e}")

async def log_n8n_response(
    session_id: str,
    agent: str,
    message: str,
    response: Dict[str, Any],
    status: str
):
    """Log an n8n response to the database"""
    try:
        query = """
        UPDATE n8n_logs
        SET response_payload = $1, status = $2
        WHERE session_id = $3 AND agent = $4 AND message = $5
        AND created_at > NOW() - INTERVAL '5 minutes'
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        from database import execute
        await execute(query, json.dumps(response), status, session_id, agent, message)
    except Exception as e:
        logger.error(f"Error logging n8n response: {e}")