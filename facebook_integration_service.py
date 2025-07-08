#!/usr/bin/env python3
"""
🚀 FACEBOOK INTEGRATION SERVICE WITH 2FA HANDLING
===============================================
Handles complete Facebook integration with GHL including 2FA
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import imaplib
import email
from email.mime.text import MIMEText
import httpx
from playwright.async_api import async_playwright
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Request/Response Models
class FacebookIntegrationRequest(BaseModel):
    location_id: str
    user_id: str
    email: str
    password: str
    firm_user_id: str
    enable_2fa_bypass: bool = False  # If possible

class EmailConfig(BaseModel):
    # Email configuration for 2FA code retrieval
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    email_address: str = "your-monitoring-email@gmail.com"  # Email that receives 2FA codes
    email_password: str = "your-app-specific-password"

class FacebookIntegrationService:
    """Service to handle Facebook integration with GHL"""
    
    def __init__(self, email_config: EmailConfig):
        self.email_config = email_config
        self.jwt_token = None
        self.facebook_pages = []
        
    async def integrate_facebook(self, request: FacebookIntegrationRequest) -> Dict:
        """
        Main integration flow:
        1. Login to GHL with browser automation
        2. Handle 2FA if required
        3. Extract JWT token
        4. Get Facebook pages
        5. Store in database
        """
        
        result = {
            "status": "processing",
            "steps": {
                "login": "pending",
                "2fa": "pending",
                "token_extraction": "pending",
                "facebook_pages": "pending",
                "database_storage": "pending"
            },
            "data": {}
        }
        
        try:
            # Step 1: Browser automation login
            print(f"🔐 Starting GHL login for location: {request.location_id}")
            browser_result = await self._browser_login_with_2fa(request)
            
            if browser_result["success"]:
                result["steps"]["login"] = "completed"
                result["steps"]["2fa"] = browser_result.get("2fa_handled", "skipped")
                self.jwt_token = browser_result["jwt_token"]
                result["data"]["jwt_token"] = self.jwt_token[:20] + "..."
                result["steps"]["token_extraction"] = "completed"
                
                # Step 2: Get Facebook pages
                pages_result = await self._get_facebook_pages(request.location_id)
                if pages_result["success"]:
                    result["steps"]["facebook_pages"] = "completed"
                    result["data"]["pages"] = pages_result["pages"]
                    self.facebook_pages = pages_result["pages"]
                    
                    # Step 3: Store in database
                    db_result = await self._store_in_database(request, pages_result["pages"])
                    if db_result["success"]:
                        result["steps"]["database_storage"] = "completed"
                        result["status"] = "success"
                    else:
                        result["status"] = "partial_success"
                        result["error"] = "Database storage failed"
                else:
                    result["status"] = "partial_success"
                    result["error"] = "Failed to get Facebook pages"
            else:
                result["status"] = "failed"
                result["error"] = browser_result.get("error", "Login failed")
                
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            
        return result
    
    async def _browser_login_with_2fa(self, request: FacebookIntegrationRequest) -> Dict:
        """Handle browser login with 2FA support"""
        
        # Check if we're on Heroku
        is_heroku = os.environ.get('DYNO') is not None
        
        async with async_playwright() as p:
            # Configure browser for Heroku vs local
            if is_heroku:
                browser = await p.chromium.launch(
                    headless=True,  # Must be headless on Heroku
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox', 
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process',
                        '--disable-gpu',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ],
                    executable_path='/app/.apt/usr/bin/chromium-browser'
                )
            else:
                browser = await p.chromium.launch(
                    headless=False,  # Show browser for user visibility in local dev
                    args=['--start-maximized', '--incognito']
                )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            page = await context.new_page()
            
            # JWT token capture
            jwt_token = None
            
            def handle_request(request):
                nonlocal jwt_token
                headers = request.headers
                if 'token-id' in headers and headers['token-id'].startswith('eyJ'):
                    jwt_token = headers['token-id']
                    print(f"✅ JWT token captured!")
            
            page.on('request', handle_request)
            
            # Navigate to GHL login
            await page.goto("https://app.gohighlevel.com/login", wait_until='networkidle')
            
            # Fill credentials
            try:
                await page.wait_for_selector('input[type="email"]', timeout=5000)
                await page.fill('input[type="email"]', request.email)
                await page.fill('input[type="password"]', request.password)
                
                # Click login button
                await page.click('button[type="submit"]')
                
                # Wait for navigation or 2FA
                await page.wait_for_timeout(3000)
                
                # Check if 2FA is required
                current_url = page.url
                if "2fa" in current_url or "verify" in current_url:
                    print("📱 2FA detected, handling...")
                    
                    # Handle 2FA
                    two_fa_result = await self._handle_2fa(page, request.email)
                    
                    if not two_fa_result["success"]:
                        await browser.close()
                        return {
                            "success": False,
                            "error": "2FA failed",
                            "2fa_handled": "failed"
                        }
                    
                    await page.wait_for_timeout(3000)
                
                # Wait for dashboard
                await page.wait_for_selector('[data-testid="dashboard"]', timeout=30000)
                
                # Trigger API calls to capture token
                await self._trigger_api_calls(page)
                
                await page.wait_for_timeout(5000)
                
                await browser.close()
                
                if jwt_token:
                    return {
                        "success": True,
                        "jwt_token": jwt_token,
                        "2fa_handled": "completed"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to capture JWT token"
                    }
                    
            except Exception as e:
                await browser.close()
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def _handle_2fa(self, page, user_email: str) -> Dict:
        """Handle 2FA by listening for email code"""
        
        try:
            # Check if it's email or SMS 2FA
            if await page.locator('text="Email"').is_visible():
                # Select email option
                await page.click('text="Email"')
                await page.wait_for_timeout(2000)
            
            # Start email listener
            print("📧 Listening for 2FA code in email...")
            
            # Poll for 2FA code
            max_attempts = 30  # 30 seconds timeout
            for attempt in range(max_attempts):
                code = await self._get_2fa_code_from_email()
                
                if code:
                    print(f"✅ Got 2FA code: {code}")
                    
                    # Enter the code
                    await page.fill('input[type="text"]', code)
                    await page.click('button[type="submit"]')
                    
                    await page.wait_for_timeout(3000)
                    
                    return {"success": True, "code": code}
                
                await asyncio.sleep(1)  # Wait 1 second before next attempt
            
            return {"success": False, "error": "2FA code not received"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_2fa_code_from_email(self) -> Optional[str]:
        """Retrieve 2FA code from email"""
        
        try:
            # Connect to email
            mail = imaplib.IMAP4_SSL(self.email_config.imap_server, self.email_config.imap_port)
            mail.login(self.email_config.email_address, self.email_config.email_password)
            mail.select('inbox')
            
            # Search for recent GHL emails
            search_criteria = '(FROM "noreply@gohighlevel.com" UNSEEN)'
            result, data = mail.search(None, search_criteria)
            
            if result == 'OK':
                email_ids = data[0].split()
                
                for email_id in reversed(email_ids):  # Check newest first
                    result, msg_data = mail.fetch(email_id, '(RFC822)')
                    
                    if result == 'OK':
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Extract body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()
                        
                        # Look for 6-digit code
                        code_match = re.search(r'\b(\d{6})\b', body)
                        if code_match:
                            code = code_match.group(1)
                            
                            # Mark as read
                            mail.store(email_id, '+FLAGS', '\\Seen')
                            mail.close()
                            mail.logout()
                            
                            return code
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"Email error: {e}")
        
        return None
    
    async def _trigger_api_calls(self, page):
        """Trigger API calls to capture JWT token"""
        
        # Navigate to different pages to trigger API calls
        routes = [
            '/dashboard',
            '/conversations',
            '/contacts',
            '/settings'
        ]
        
        current_url = page.url
        base_url = current_url.split('/dashboard')[0]
        
        for route in routes:
            try:
                await page.goto(f"{base_url}{route}", wait_until='networkidle')
                await page.wait_for_timeout(2000)
            except:
                pass
    
    async def _get_facebook_pages(self, location_id: str) -> Dict:
        """Get Facebook pages using JWT token"""
        
        if not self.jwt_token:
            return {"success": False, "error": "No JWT token available"}
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Get Facebook pages
            pages_url = f"https://services.leadconnectorhq.com/social-media-posting/{location_id}/pages"
            
            try:
                response = await client.get(pages_url, headers=headers)
                
                if response.status_code == 200:
                    pages_data = response.json()
                    
                    return {
                        "success": True,
                        "pages": pages_data.get("pages", [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get pages: {response.status_code}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def _store_in_database(self, request: FacebookIntegrationRequest, pages: List[Dict]) -> Dict:
        """Store Facebook integration data in database"""
        
        # This would connect to your Supabase instance
        # For now, returning mock success
        
        data = {
            "firm_user_id": request.firm_user_id,
            "location_id": request.location_id,
            "user_id": request.user_id,
            "fb_pages_data": pages,
            "fb_access_token": self.jwt_token,
            "fb_token_expires_at": (datetime.now() + timedelta(days=1)).isoformat(),
            "ghl_integration_status": "pending"
        }
        
        # TODO: Actual Supabase insert
        print(f"📊 Would store in database: {len(pages)} pages for location {request.location_id}")
        
        return {"success": True, "data": data}
    
    async def connect_facebook_page(self, location_id: str, page_id: str) -> Dict:
        """Connect a specific Facebook page to GHL"""
        
        if not self.jwt_token:
            return {"success": False, "error": "No JWT token available"}
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Connect page endpoint
        connect_url = f"https://services.leadconnectorhq.com/social-media-posting/{location_id}/pages/{page_id}/connect"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(connect_url, headers=headers)
                
                if response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "message": "Page connected successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to connect page: {response.status_code}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }

# FastAPI endpoints
app = FastAPI()

# Email configuration (should be in environment variables)
email_config = EmailConfig(
    email_address="squidgy.2fa.monitor@gmail.com",
    email_password="your-app-specific-password"
)

facebook_service = FacebookIntegrationService(email_config)

@app.post("/api/facebook/integrate")
async def integrate_facebook(request: FacebookIntegrationRequest, background_tasks: BackgroundTasks):
    """Start Facebook integration with browser automation"""
    
    # Run in background
    background_tasks.add_task(
        facebook_service.integrate_facebook,
        request
    )
    
    return {
        "status": "processing",
        "message": "Facebook integration started. Browser automation in progress..."
    }

@app.post("/api/facebook/connect-page")
async def connect_page(location_id: str, page_id: str):
    """Connect a specific Facebook page to GHL"""
    
    result = await facebook_service.connect_facebook_page(location_id, page_id)
    return result

@app.get("/api/facebook/integration-status/{location_id}")
async def get_integration_status(location_id: str):
    """Get current integration status"""
    
    # TODO: Query from database
    return {
        "location_id": location_id,
        "status": "processing",
        "pages": facebook_service.facebook_pages
    }