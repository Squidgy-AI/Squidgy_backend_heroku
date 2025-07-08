#!/usr/bin/env python3
"""
🔐 ENHANCED 2FA SERVICE FOR MICROSOFT OUTLOOK
==============================================
Handles GHL 2FA with Microsoft Outlook email monitoring
"""

import asyncio
import imaplib
import email
import re
import time
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright, Page

class OutlookEmailConfig:
    """Configuration for Microsoft Outlook email monitoring"""
    
    def __init__(self):
        # Microsoft Outlook IMAP settings
        self.imap_server = "outlook.office365.com"
        self.imap_port = 993
        
        # Your specific email credentials (should be in environment variables)
        self.email_address = "sa+01@squidgy.ai"  # Your actual email
        self.email_password = "your-outlook-password"  # App-specific password
        
        # Email patterns to search for
        self.sender_patterns = [
            "noreply@gohighlevel.com",
            "no-reply@gohighlevel.com", 
            "support@gohighlevel.com"
        ]

class Enhanced2FAService:
    """Enhanced 2FA service with Microsoft Outlook support"""
    
    def __init__(self, email_config: OutlookEmailConfig):
        self.email_config = email_config
        
    async def handle_ghl_2fa_flow(self, page: Page) -> dict:
        """
        Complete GHL 2FA flow:
        1. Detect 2FA page
        2. Select email option
        3. Click send code
        4. Monitor email for OTP
        5. Input OTP in browser
        6. Complete login
        """
        
        try:
            print("🔐 Starting enhanced 2FA flow...")
            
            # Step 1: Wait for 2FA page to load
            await page.wait_for_timeout(3000)
            current_url = page.url
            
            if "2fa" not in current_url.lower() and "verify" not in current_url.lower():
                print("ℹ️ No 2FA required")
                return {"success": True, "2fa_required": False}
            
            print("📱 2FA page detected!")
            
            # Step 2: Select email option if multiple options available
            await self._select_email_2fa_option(page)
            
            # Step 3: Click send code button
            await self._click_send_code_button(page)
            
            # Step 4: Monitor email and input code
            success = await self._monitor_and_input_code(page)
            
            if success:
                print("✅ 2FA completed successfully!")
                return {"success": True, "2fa_required": True, "2fa_completed": True}
            else:
                print("❌ 2FA failed")
                return {"success": False, "error": "2FA code input failed"}
                
        except Exception as e:
            print(f"💥 2FA flow error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _select_email_2fa_option(self, page: Page):
        """Select email option for 2FA"""
        
        print("📧 Looking for email 2FA option...")
        
        # Common selectors for email option
        email_selectors = [
            'text="Email"',
            'text="Send to Email"',
            'text="Email Address"',
            '[data-testid="email-option"]',
            '.email-option',
            'input[value="email"]',
            'button:has-text("Email")',
            'label:has-text("Email")'
        ]
        
        for selector in email_selectors:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                await page.click(selector)
                print(f"✅ Selected email option using: {selector}")
                await page.wait_for_timeout(1000)
                return
            except:
                continue
        
        print("ℹ️ Email option not found or already selected")
    
    async def _click_send_code_button(self, page: Page):
        """Click the send code button"""
        
        print("📤 Looking for send code button...")
        
        # Common selectors for send code button
        send_selectors = [
            'text="Send Code"',
            'text="Send"',
            'text="Send Verification Code"',
            'text="Send OTP"',
            'button:has-text("Send")',
            '[data-testid="send-code"]',
            '.send-code-btn',
            'button[type="submit"]',
            '.btn-primary:has-text("Send")'
        ]
        
        for selector in send_selectors:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                await page.click(selector)
                print(f"✅ Clicked send code button: {selector}")
                await page.wait_for_timeout(2000)
                return
            except:
                continue
        
        print("ℹ️ Send code button not found or already clicked")
    
    async def _monitor_and_input_code(self, page: Page) -> bool:
        """Monitor email for OTP and input it in browser"""
        
        print("👀 Starting email monitoring for OTP...")
        
        # Start monitoring email in background
        max_attempts = 60  # 1 minute polling
        
        for attempt in range(max_attempts):
            print(f"📧 Checking email... (attempt {attempt + 1}/{max_attempts})")
            
            # Get OTP from email
            otp_code = await self._get_otp_from_outlook()
            
            if otp_code:
                print(f"🎯 Got OTP code: {otp_code}")
                
                # Input the code in browser
                success = await self._input_otp_in_browser(page, otp_code)
                
                if success:
                    return True
                else:
                    print("⚠️ OTP input failed, continuing to monitor...")
            
            await asyncio.sleep(2)  # Wait 2 seconds before next check
        
        print("⏰ Email monitoring timeout")
        return False
    
    async def _get_otp_from_outlook(self) -> Optional[str]:
        """Get OTP code from Microsoft Outlook email"""
        
        try:
            # Connect to Outlook
            mail = imaplib.IMAP4_SSL(self.email_config.imap_server, self.email_config.imap_port)
            mail.login(self.email_config.email_address, self.email_config.email_password)
            mail.select('inbox')
            
            # Search for recent GHL emails from any sender pattern
            for sender in self.email_config.sender_patterns:
                search_criteria = f'(FROM "{sender}" UNSEEN)'
                result, data = mail.search(None, search_criteria)
                
                if result == 'OK' and data[0]:
                    email_ids = data[0].split()
                    
                    for email_id in reversed(email_ids):  # Check newest first
                        result, msg_data = mail.fetch(email_id, '(RFC822)')
                        
                        if result == 'OK':
                            raw_email = msg_data[0][1]
                            msg = email.message_from_bytes(raw_email)
                            
                            # Extract email body
                            body = self._extract_email_body(msg)
                            
                            # Look for OTP patterns
                            otp = self._extract_otp_from_body(body)
                            
                            if otp:
                                # Mark as read
                                mail.store(email_id, '+FLAGS', '\\Seen')
                                mail.close()
                                mail.logout()
                                return otp
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"📧 Email check error: {e}")
        
        return None
    
    def _extract_email_body(self, msg) -> str:
        """Extract body text from email message"""
        
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8')
                        break
                    except:
                        try:
                            body = part.get_payload(decode=True).decode('latin-1')
                            break
                        except:
                            continue
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8')
            except:
                try:
                    body = msg.get_payload(decode=True).decode('latin-1')
                except:
                    body = str(msg.get_payload())
        
        return body
    
    def _extract_otp_from_body(self, body: str) -> Optional[str]:
        """Extract OTP code from email body"""
        
        # Multiple patterns to catch different OTP formats
        otp_patterns = [
            r'verification code[:\s]*(\d{6})',
            r'security code[:\s]*(\d{6})',
            r'access code[:\s]*(\d{6})',
            r'login code[:\s]*(\d{6})',
            r'your code[:\s]*(\d{6})',
            r'code[:\s]*(\d{6})',
            r'\b(\d{6})\b',  # Any 6-digit number
            r'(\d{4})',     # 4-digit codes
        ]
        
        body_lower = body.lower()
        
        for pattern in otp_patterns:
            matches = re.findall(pattern, body_lower)
            if matches:
                # Return the first valid code
                for match in matches:
                    if len(match) in [4, 6]:  # Valid OTP length
                        print(f"🔍 Found OTP using pattern: {pattern}")
                        return match
        
        return None
    
    async def _input_otp_in_browser(self, page: Page, otp_code: str) -> bool:
        """Input OTP code in browser form"""
        
        try:
            print(f"⌨️ Inputting OTP code: {otp_code}")
            
            # Common selectors for OTP input fields
            otp_selectors = [
                'input[type="text"]',
                'input[type="number"]',
                'input[name*="code"]',
                'input[name*="otp"]',
                'input[name*="verification"]',
                'input[placeholder*="code"]',
                'input[placeholder*="Code"]',
                '.otp-input',
                '.verification-input',
                '[data-testid="otp-input"]'
            ]
            
            # Try to find and fill OTP input
            for selector in otp_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    
                    # Clear any existing content
                    await page.fill(selector, '')
                    await page.wait_for_timeout(500)
                    
                    # Input the OTP code
                    await page.fill(selector, otp_code)
                    await page.wait_for_timeout(1000)
                    
                    print(f"✅ OTP entered using selector: {selector}")
                    
                    # Submit the form
                    await self._submit_otp_form(page)
                    
                    return True
                    
                except:
                    continue
            
            # Try individual digit inputs (some forms have separate boxes)
            await self._try_individual_digit_inputs(page, otp_code)
            
            return True
            
        except Exception as e:
            print(f"⌨️ OTP input error: {e}")
            return False
    
    async def _try_individual_digit_inputs(self, page: Page, otp_code: str):
        """Try inputting OTP in individual digit boxes"""
        
        try:
            print("🔢 Trying individual digit inputs...")
            
            # Look for multiple OTP input boxes
            digit_selectors = [
                'input[maxlength="1"]',
                '.otp-digit',
                '.digit-input',
                '[data-testid="digit-input"]'
            ]
            
            for selector in digit_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    
                    if len(elements) >= len(otp_code):
                        print(f"📱 Found {len(elements)} digit inputs")
                        
                        for i, digit in enumerate(otp_code):
                            if i < len(elements):
                                await elements[i].fill(digit)
                                await page.wait_for_timeout(200)
                        
                        print("✅ OTP entered in individual digit boxes")
                        return
                        
                except:
                    continue
                    
        except Exception as e:
            print(f"🔢 Individual digit input error: {e}")
    
    async def _submit_otp_form(self, page: Page):
        """Submit the OTP form"""
        
        submit_selectors = [
            'button[type="submit"]',
            'text="Verify"',
            'text="Submit"',
            'text="Continue"',
            'text="Confirm"',
            '.submit-btn',
            '.verify-btn',
            '[data-testid="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                await page.click(selector)
                print(f"✅ Submitted OTP form using: {selector}")
                await page.wait_for_timeout(3000)
                return
            except:
                continue
        
        # If no submit button found, try pressing Enter
        try:
            await page.keyboard.press('Enter')
            print("✅ Submitted OTP form with Enter key")
            await page.wait_for_timeout(3000)
        except:
            print("⚠️ Could not submit OTP form")

# Test function
async def test_outlook_2fa():
    """Test the Outlook 2FA service"""
    
    print("🧪 Testing Outlook 2FA Service")
    print("=" * 40)
    
    email_config = OutlookEmailConfig()
    service = Enhanced2FAService(email_config)
    
    # Test email connection
    try:
        otp = await service._get_otp_from_outlook()
        if otp:
            print(f"✅ Found OTP: {otp}")
        else:
            print("ℹ️ No OTP found in recent emails")
    except Exception as e:
        print(f"❌ Email test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_outlook_2fa())