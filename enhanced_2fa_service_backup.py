#!/usr/bin/env python3
"""
🔐 ENHANCED 2FA SERVICE FOR GMAIL
=================================
Handles GHL 2FA with Gmail email monitoring (simplified setup)
"""

import asyncio
import imaplib
import email
import re
import time
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright, Page

class GmailEmailConfig:
    """Configuration for Gmail email monitoring"""
    
    def __init__(self, location_id: str = None):
        # Gmail IMAP settings
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        
        # Simple Gmail configuration
        import os
        self.email_address = os.environ.get("GMAIL_2FA_EMAIL", "somashekhar34@gmail.com")
        self.email_password = os.environ.get("GMAIL_2FA_APP_PASSWORD", "your-gmail-app-password")
        self.account_id = "gmail"
        
        # COMMENTED OUT: Complex database account management for future use
        # try:
        #     from email_account_db_manager import get_email_account_for_integration
        #     account = get_email_account_for_integration(location_id)
        #     
        #     if account:
        #         self.email_address = account.email
        #         self.email_password = account.password
        #         self.account_id = str(account.account_number)
        #         self.account_db_id = account.id
        #     else:
        #         # Fallback to environment variables for development
        #         import os
        #         self.email_address = os.environ.get("OUTLOOK_2FA_EMAIL", "sa+01@squidgy.ai")
        #         self.email_password = os.environ.get("OUTLOOK_2FA_PASSWORD", "your-outlook-password")
        #         self.account_id = "01"
        #         self.account_db_id = None
        #         
        # except Exception as e:
        #     # Fallback in case of database issues
        #     import os
        #     print(f"⚠️ Using fallback email config due to: {e}")
        #     self.email_address = os.environ.get("OUTLOOK_2FA_EMAIL", "sa+01@squidgy.ai")
        #     self.email_password = os.environ.get("OUTLOOK_2FA_PASSWORD", "your-outlook-password")
        #     self.account_id = "01"
        #     self.account_db_id = None
        
        # Email patterns to search for (based on actual email received)
        self.sender_patterns = [
            "noreply@gohighlevel.com",
            "no-reply@gohighlevel.com", 
            "support@gohighlevel.com",
            "noreply",  # Sometimes shows just "noreply" in mobile
        ]

class Enhanced2FAService:
    """Enhanced 2FA service with Gmail support (simplified)"""
    
    def __init__(self, email_config: GmailEmailConfig):
        self.email_config = email_config
        self._log_function = None
    
    def set_log_function(self, log_function):
        """Set external logging function"""
        self._log_function = log_function
    
    def _log(self, step: str, details: str = ""):
        """Internal logging method"""
        if self._log_function:
            self._log_function(f"[2FA] {step}", details)
        else:
            print(f"🔐 [2FA] {step}: {details}")
        
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
            self._log("🚀 2FA Start", "Beginning enhanced 2FA flow...")
            
            # Step 1: Wait for 2FA page to load
            self._log("⏱️ Page Analysis", "Analyzing current page for 2FA requirements...")
            await page.wait_for_timeout(3000)
            current_url = page.url
            page_content = await page.content()
            
            # Check for 2FA indicators in URL or page content
            is_2fa_page = (
                "2fa" in current_url.lower() or 
                "verify" in current_url.lower() or
                "Verify Security Code" in page_content or
                "Send code to email" in page_content or
                "security code" in page_content.lower()
            )
            
            if not is_2fa_page:
                self._log("ℹ️ No 2FA Needed", f"Current URL does not require 2FA: {current_url}")
                return {"success": True, "2fa_required": False}
            
            self._log("📱 2FA Detected", f"2FA page detected at: {current_url}")
            
            # Step 2: Select email option if multiple options available
            self._log("📧 Email Option", "Selecting email option for 2FA...")
            await self._select_email_2fa_option(page)
            
            # Step 3: Click send code button
            self._log("📤 Send Code", "Clicking send code button...")
            await self._click_send_code_button(page)
            
            # Step 4: Monitor email and input code
            self._log("👀 Email Monitor", "Starting email monitoring and code input process...")
            success = await self._monitor_and_input_code(page)
            
            if success:
                self._log("✅ 2FA Complete", "2FA process completed successfully!")
                return {"success": True, "2fa_required": True, "2fa_completed": True}
            else:
                self._log("❌ 2FA Failed", "2FA code input or verification failed")
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
            'text="Send Security Code"',  # Exact text from GHL 2FA screen
            'text="Send Code"',
            'text="Send"',
            'text="Send Verification Code"',
            'text="Send OTP"',
            'button:has-text("Send Security Code")',
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
        """Monitor email for OTP and input it in browser - FAST & RELIABLE"""
        
        print("⚡ Starting FAST email monitoring for OTP...")
        
        # Reduced timeout for faster response
        max_attempts = 30  # 30 seconds total
        
        for attempt in range(max_attempts):
            self._log("📧 Quick Check", f"Fast OTP check ({attempt + 1}/{max_attempts})...")
            
            # Get OTP from email
            otp_code = await self._get_otp_from_gmail()
            
            if otp_code:
                self._log("🎯 OTP FOUND!", f"GOT IT: {otp_code} - Inputting immediately!")
                
                # Input the code in browser IMMEDIATELY with multiple attempts
                for input_attempt in range(3):  # Try 3 times quickly
                    self._log("⚡ Rapid Input", f"Attempt {input_attempt + 1}: Inputting {otp_code}")
                    success = await self._input_otp_in_browser(page, otp_code)
                    
                    if success:
                        self._log("✅ OTP SUCCESS!", "Code entered successfully!")
                        return True
                    else:
                        self._log("🔄 Retry", f"Input attempt {input_attempt + 1} failed, trying again...")
                        await asyncio.sleep(0.5)  # Very short delay between attempts
                
                self._log("❌ Input Failed", f"Could not input {otp_code} after 3 attempts")
                return False
            else:
                self._log("🔍 Scanning...", f"Checking... ({attempt + 1})")
            
            await asyncio.sleep(1)  # Check every 1 second (faster)
        
        self._log("⏰ Fast Timeout", f"No OTP found in {max_attempts} seconds")
        return False
    
    async def _get_otp_from_gmail(self) -> Optional[str]:
        """Get OTP code from Gmail email - ROBUST VERSION (always gets latest email)"""
        
        try:
            # Connect to Gmail (using same config as working test script)
            import os
            from datetime import datetime, timedelta
            
            email_address = os.environ.get("GMAIL_2FA_EMAIL", "somashekhar34@gmail.com")
            email_password = os.environ.get("GMAIL_2FA_APP_PASSWORD", "ytmfxlelgyojxjmf")
            
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(email_address, email_password)
            mail.select('inbox')
            
            # Calculate time window - only look at emails from last 5 minutes
            now = datetime.now()
            five_minutes_ago = now - timedelta(minutes=5)
            date_threshold = five_minutes_ago.strftime('%d-%b-%Y')
            
            print(f"📧 Searching for emails since: {date_threshold}")
            
            # Collect all potential emails with timestamps
            candidate_emails = []
            
            for sender in self.email_config.sender_patterns:
                # Search for emails from today (both read and unread)
                search_criteria = f'(FROM "{sender}" SINCE "{date_threshold}")'
                result, data = mail.search(None, search_criteria)
                
                if result == 'OK' and data[0]:
                    email_ids = data[0].split()
                    print(f"📨 Found {len(email_ids)} email(s) from {sender}")
                    
                    for email_id in email_ids:
                        try:
                            # Get email metadata first
                            result, msg_data = mail.fetch(email_id, '(RFC822)')
                            
                            if result == 'OK':
                                raw_email = msg_data[0][1]
                                msg = email.message_from_bytes(raw_email)
                                
                                # Parse email date
                                email_date_str = msg.get('Date', '')
                                email_subject = msg.get('Subject', '')
                                
                                try:
                                    # Parse email date
                                    from email.utils import parsedate_to_datetime
                                    email_date = parsedate_to_datetime(email_date_str)
                                    # Convert to local time if needed
                                    if email_date.tzinfo is None:
                                        email_date = email_date.replace(tzinfo=timezone.utc)
                                    
                                    # Only consider emails from last 5 minutes
                                    if email_date >= five_minutes_ago.replace(tzinfo=timezone.utc):
                                        candidate_emails.append({
                                            'id': email_id,
                                            'date': email_date,
                                            'subject': email_subject,
                                            'sender': sender,
                                            'msg': msg
                                        })
                                        print(f"📅 Valid email: {email_subject} ({email_date})")
                                    else:
                                        print(f"⏰ Email too old: {email_subject} ({email_date})")
                                
                                except Exception as date_error:
                                    print(f"📅 Date parsing error: {date_error}")
                                    # If date parsing fails, include it anyway (fallback)
                                    candidate_emails.append({
                                        'id': email_id,
                                        'date': now,  # Use current time as fallback
                                        'subject': email_subject,
                                        'sender': sender,
                                        'msg': msg
                                    })
                        
                        except Exception as email_error:
                            print(f"📧 Error processing email {email_id}: {email_error}")
                            continue
            
            # Sort emails by date (newest first)
            candidate_emails.sort(key=lambda x: x['date'], reverse=True)
            
            print(f"🔍 Processing {len(candidate_emails)} candidate email(s) (newest first)...")
            
            # Process emails from newest to oldest
            for i, email_info in enumerate(candidate_emails, 1):
                print(f"\n📨 Processing email #{i}:")
                print(f"   📧 Subject: {email_info['subject']}")
                print(f"   📅 Date: {email_info['date']}")
                print(f"   👤 Sender: {email_info['sender']}")
                
                # Extract email body
                body = self._extract_email_body(email_info['msg'])
                
                # Look for OTP patterns
                otp = self._extract_otp_from_body(body)
                
                if otp:
                    print(f"   🎯 OTP FOUND: {otp}")
                    
                    # Mark as read
                    mail.store(email_info['id'], '+FLAGS', '\\Seen')
                    mail.close()
                    mail.logout()
                    
                    print(f"✅ Using OTP from LATEST email: {otp}")
                    return otp
                else:
                    print(f"   ❌ No OTP found in this email")
            
            print("📧 No OTP found in any recent emails")
            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"📧 Email check error: {e}")
            import traceback
            print(f"📧 Full error: {traceback.format_exc()}")
        
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
            r'Your login security code[:\s]*(\d{6})',  # Exact GHL format
            r'login security code[:\s]*(\d{6})',       # GHL format variation
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
            
            # GHL typically uses individual digit boxes, so try that first
            print("🔢 Attempting individual digit input (GHL format)...")
            success = await self._try_individual_digit_inputs(page, otp_code)
            if success:
                await self._submit_otp_form(page)
                return True
            
            print("🔄 Trying single input field approach...")
            # Fallback to single input field approach
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
            
            # Try to find and fill single OTP input
            for selector in otp_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    
                    # Clear any existing content
                    await page.fill(selector, '')
                    await page.wait_for_timeout(500)
                    
                    # Input the OTP code
                    await page.fill(selector, otp_code)
                    await page.wait_for_timeout(1000)
                    
                    print(f"✅ OTP entered using single input selector: {selector}")
                    
                    # Submit the form
                    await self._submit_otp_form(page)
                    
                    return True
                    
                except:
                    continue
            
            print("❌ Could not find suitable OTP input fields")
            return False
            
        except Exception as e:
            print(f"⌨️ OTP input error: {e}")
            return False
    
    async def _try_individual_digit_inputs(self, page: Page, otp_code: str):
        """Try inputting OTP in individual digit boxes"""
        
        try:
            print("🔢 Trying individual digit inputs...")
            
            # GHL uses 6 individual input boxes - try multiple approaches
            digit_selectors = [
                'input[maxlength="1"]',  # Most common for digit inputs
                'input[type="text"][maxlength="1"]',  # Specific text inputs with single char
                '.otp-digit',
                '.digit-input', 
                '[data-testid="digit-input"]',
                'input[class*="digit"]',  # Any input with "digit" in class name
                'input[id*="digit"]',     # Any input with "digit" in ID
            ]
            
            for selector in digit_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    
                    if len(elements) >= len(otp_code):
                        print(f"📱 Found {len(elements)} digit inputs using selector: {selector}")
                        
                        # Clear all inputs first
                        for element in elements[:len(otp_code)]:
                            await element.fill('')
                            await page.wait_for_timeout(100)
                        
                        # Input each digit with small delays
                        for i, digit in enumerate(otp_code):
                            if i < len(elements):
                                await elements[i].click()  # Focus the input
                                await page.wait_for_timeout(200)
                                await elements[i].fill(digit)
                                await page.wait_for_timeout(300)
                                
                                # Try typing as backup
                                await elements[i].type(digit)
                                await page.wait_for_timeout(200)
                        
                        print("✅ OTP entered in individual digit boxes")
                        
                        # Wait a moment for auto-submit or find submit button
                        await page.wait_for_timeout(2000)
                        
                        return True
                        
                except Exception as e:
                    print(f"🔢 Selector {selector} failed: {e}")
                    continue
            
            # If individual inputs not found, try a different approach
            print("🔍 Trying alternative input methods...")
            
            # Look for any input field that might accept the full code
            fallback_selectors = [
                'input[type="text"]',
                'input[type="number"]', 
                'input[name*="code"]',
                'input[placeholder*="code"]'
            ]
            
            for selector in fallback_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=1000)
                    await page.fill(selector, otp_code)
                    print(f"✅ OTP entered using fallback selector: {selector}")
                    return True
                except:
                    continue
                    
            return False
                    
        except Exception as e:
            print(f"🔢 Individual digit input error: {e}")
            return False
    
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