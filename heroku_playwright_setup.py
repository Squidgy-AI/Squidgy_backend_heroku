#!/usr/bin/env python3
"""
🚀 HEROKU PLAYWRIGHT SETUP
==========================
Configure Playwright for Heroku deployment
"""

import os
import asyncio
from playwright.async_api import async_playwright

async def configure_playwright_for_heroku():
    """Configure Playwright to work on Heroku"""
    
    # Heroku-specific browser launch args
    heroku_args = [
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
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--disable-ipc-flooding-protection',
        '--disable-background-networking',
        '--disable-client-side-phishing-detection',
        '--disable-default-apps',
        '--disable-extensions',
        '--disable-sync',
        '--disable-translate',
        '--hide-scrollbars',
        '--metrics-recording-only',
        '--mute-audio',
        '--no-default-browser-check',
        '--no-first-run',
        '--safebrowsing-disable-auto-update',
        '--disable-features=VizDisplayCompositor',
        '--headless'  # MUST be headless on Heroku
    ]
    
    return heroku_args

def get_browser_executable_path():
    """Get browser executable path for Heroku"""
    
    # Check if we're on Heroku
    if os.environ.get('DYNO'):
        # On Heroku, use the buildpack-installed Chromium
        return '/app/.apt/usr/bin/chromium-browser'
    else:
        # Local development
        return None

async def test_heroku_browser():
    """Test browser launch on Heroku"""
    
    try:
        heroku_args = await configure_playwright_for_heroku()
        executable_path = get_browser_executable_path()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # Must be headless
                args=heroku_args,
                executable_path=executable_path
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://httpbin.org/get")
            content = await page.content()
            
            await browser.close()
            
            print("✅ Heroku browser test successful!")
            print(f"Page content length: {len(content)}")
            
            return True
            
    except Exception as e:
        print(f"❌ Heroku browser test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_heroku_browser())