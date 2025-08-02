#!/usr/bin/env python3
"""
Complete Business Setup API - Handles the full workflow:
1. Business Information Form → 2. Create Location → 3. Create User → 4. Run Automation (Async)
"""

import os
import asyncio
import uuid
import secrets
import string
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Import our database and Playwright automation
try:
    from database import execute, fetch_one
    from ghl_automation_complete_playwright import HighLevelCompleteAutomationPlaywright
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Import failed: {e}")
    DATABASE_AVAILABLE = False

load_dotenv()

app = FastAPI(title="Business Setup Complete API")

# Models
class BusinessInformationRequest(BaseModel):
    firm_user_id: str
    agent_id: str
    business_name: str
    business_address: str
    city: str
    state: str
    country: str = "United States"
    postal_code: str
    business_logo_url: Optional[str] = None
    snapshot_id: str  # HighLevel snapshot ID for location creation

class BusinessSetupResponse(BaseModel):
    success: bool
    message: str
    business_id: Optional[str] = None
    status: str
    ghl_location_id: Optional[str] = None
    ghl_user_email: Optional[str] = None
    automation_started: bool = False

# Utility Functions
def generate_secure_password(length: int = 12) -> str:
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_user_email(business_name: str, location_id: str) -> str:
    """Generate a unique email for the HighLevel user"""
    # Clean business name (remove spaces, special chars)
    clean_name = ''.join(c.lower() for c in business_name if c.isalnum())[:10]
    return f"{clean_name}+{location_id}@squidgyai.com"

async def create_ghl_location(snapshot_id: str, business_info: Dict[str, Any]) -> Dict[str, Any]:
    """Create a HighLevel location using snapshot ID"""
    try:
        # This would be your actual HighLevel API call
        # For now, simulating the response
        
        # In production, this would call:
        # POST https://backend.leadconnectorhq.com/locations
        # with snapshot_id and business information
        
        print(f"[GHL API] Creating location with snapshot: {snapshot_id}")
        print(f"[GHL API] Business: {business_info['business_name']}")
        
        # Simulate location creation (replace with actual API call)
        location_id = f"LOC_{uuid.uuid4().hex[:16].upper()}"
        
        return {
            "success": True,
            "location_id": location_id,
            "location_name": business_info['business_name'],
            "address": business_info['business_address']
        }
        
    except Exception as e:
        print(f"[ERROR] Location creation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def create_ghl_user(location_id: str, email: str, password: str, business_info: Dict[str, Any]) -> Dict[str, Any]:
    """Create a HighLevel user for the location"""
    try:
        # This would be your actual HighLevel API call
        # For now, simulating the response
        
        print(f"[GHL API] Creating user for location: {location_id}")
        print(f"[GHL API] Email: {email}")
        
        # Simulate user creation (replace with actual API call)
        user_id = f"USER_{uuid.uuid4().hex[:16].upper()}"
        
        return {
            "success": True,
            "user_id": user_id,
            "email": email,
            "location_id": location_id
        }
        
    except Exception as e:
        print(f"[ERROR] User creation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def run_playwright_automation_async(business_id: str, email: str, password: str, location_id: str, firm_user_id: str, agent_id: str, ghl_user_id: str = None):
    """Run the Playwright automation in the background (NON-BLOCKING)"""
    try:
        print(f"[AUTOMATION] Starting background automation for business: {business_id}")
        
        # Update status to automation_running
        await execute("""
            UPDATE public.squidgy_business_information 
            SET setup_status = 'automation_running', 
                automation_started_at = CURRENT_TIMESTAMP 
            WHERE id = $1
        """, business_id)
        
        # Run the Playwright automation
        automation = HighLevelCompleteAutomationPlaywright(headless=True)  # Headless for background
        success = await automation.run_automation(email, password, location_id, firm_user_id, agent_id, ghl_user_id)
        
        if success:
            # Update status to completed and save PIT token
            pit_token = automation.pit_token if hasattr(automation, 'pit_token') else None
            
            await execute("""
                UPDATE public.squidgy_business_information 
                SET setup_status = 'completed', 
                    automation_completed_at = CURRENT_TIMESTAMP,
                    pit_token = $2,
                    access_token_expires_at = $3,
                    firebase_token_available = $4
                WHERE id = $1
            """, business_id, pit_token, automation.token_expiry, bool(automation.firebase_token))
            
            print(f"[AUTOMATION] Completed successfully for business: {business_id}")
            print(f"[AUTOMATION] PIT Token: {pit_token}")
            
        else:
            # Update status to failed
            await execute("""
                UPDATE public.squidgy_business_information 
                SET setup_status = 'failed', 
                    automation_completed_at = CURRENT_TIMESTAMP,
                    automation_error = $2
                WHERE id = $1
            """, business_id, "Automation workflow failed")
            
            print(f"[AUTOMATION] Failed for business: {business_id}")
            
    except Exception as e:
        print(f"[ERROR] Automation failed: {e}")
        
        # Update status to failed with error
        await execute("""
            UPDATE public.squidgy_business_information 
            SET setup_status = 'failed', 
                automation_completed_at = CURRENT_TIMESTAMP,
                automation_error = $2
            WHERE id = $1
        """, business_id, str(e))

# API Endpoints
@app.post("/api/business/setup", response_model=BusinessSetupResponse)
async def setup_business_complete(request: BusinessInformationRequest, background_tasks: BackgroundTasks):
    """
    Complete Business Setup Workflow:
    1. Save business information
    2. Create HighLevel location (based on snapshot_id)
    3. Create HighLevel user
    4. Start automation in background (NON-BLOCKING)
    5. Return immediately so user can continue
    """
    
    try:
        if not DATABASE_AVAILABLE:
            raise HTTPException(status_code=500, detail="Database not available")
        
        print(f"🚀 Starting business setup for: {request.business_name}")
        
        # Step 1: Generate credentials
        business_id = str(uuid.uuid4())
        user_password = generate_secure_password()
        
        # Step 2: Create HighLevel location
        print(f"[STEP 1] Creating HighLevel location...")
        location_result = await create_ghl_location(request.snapshot_id, request.dict())
        
        if not location_result["success"]:
            raise HTTPException(status_code=400, detail=f"Location creation failed: {location_result.get('error')}")
        
        location_id = location_result["location_id"]
        user_email = generate_user_email(request.business_name, location_id)
        
        # Step 3: Create HighLevel user
        print(f"[STEP 2] Creating HighLevel user...")
        user_result = await create_ghl_user(location_id, user_email, user_password, request.dict())
        
        if not user_result["success"]:
            raise HTTPException(status_code=400, detail=f"User creation failed: {user_result.get('error')}")
        
        user_id = user_result["user_id"]
        
        # Step 4: Save business information to database
        print(f"[STEP 3] Saving to database...")
        await execute("""
            INSERT INTO public.squidgy_business_information 
            (id, firm_user_id, agent_id, business_name, business_address, city, state, country, postal_code, 
             business_logo_url, snapshot_id, ghl_location_id, ghl_user_email, ghl_user_password, ghl_user_id, setup_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, 'user_created')
        """, business_id, request.firm_user_id, request.agent_id, request.business_name, request.business_address,
             request.city, request.state, request.country, request.postal_code, request.business_logo_url,
             request.snapshot_id, location_id, user_email, user_password, user_id)
        
        # Step 5: Start automation in background (NON-BLOCKING!)
        print(f"[STEP 4] Starting background automation...")
        background_tasks.add_task(
            run_playwright_automation_async,
            business_id, user_email, user_password, location_id, 
            request.firm_user_id, request.agent_id, user_id
        )
        
        # Step 6: Return immediately (don't wait for automation)
        print(f"✅ Business setup initiated successfully!")
        print(f"   Business ID: {business_id}")
        print(f"   Location ID: {location_id}")
        print(f"   User Email: {user_email}")
        print(f"   🔄 Automation running in background...")
        
        return BusinessSetupResponse(
            success=True,
            message=f"Business setup initiated successfully. Automation running in background.",
            business_id=business_id,
            status="user_created",
            ghl_location_id=location_id,
            ghl_user_email=user_email,
            automation_started=True
        )
        
    except Exception as e:
        print(f"💥 Business setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/business/status/{business_id}")
async def get_business_status(business_id: str):
    """Get the current status of business setup and automation"""
    try:
        if not DATABASE_AVAILABLE:
            raise HTTPException(status_code=500, detail="Database not available")
        
        result = await fetch_one("""
            SELECT id, business_name, setup_status, ghl_location_id, ghl_user_email, 
                   pit_token, automation_started_at, automation_completed_at, automation_error,
                   access_token_expires_at, firebase_token_available, created_at
            FROM public.squidgy_business_information 
            WHERE id = $1
        """, business_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Business not found")
        
        return {
            "business_id": result["id"],
            "business_name": result["business_name"],
            "status": result["setup_status"],
            "location_id": result["ghl_location_id"],
            "user_email": result["ghl_user_email"],
            "has_pit_token": bool(result["pit_token"]),
            "automation_started_at": result["automation_started_at"],
            "automation_completed_at": result["automation_completed_at"],
            "automation_error": result["automation_error"],
            "token_expires_at": result["access_token_expires_at"],
            "has_firebase_token": result["firebase_token_available"],
            "created_at": result["created_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/business/list/{firm_user_id}/{agent_id}")
async def list_business_setups(firm_user_id: str, agent_id: str):
    """List all business setups for a firm_user_id and agent_id"""
    try:
        if not DATABASE_AVAILABLE:
            raise HTTPException(status_code=500, detail="Database not available")
        
        results = await execute("""
            SELECT * FROM business_setup_status 
            WHERE firm_user_id = $1 AND agent_id = $2 
            ORDER BY created_at DESC
        """, firm_user_id, agent_id)
        
        return {
            "businesses": results,
            "total": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database_available": DATABASE_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)  # Different port