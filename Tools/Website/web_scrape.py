# Website/web_scrape.py - FINAL VERSION
import os
import asyncio
import aiohttp
from supabase import create_client, Client
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import traceback
import tempfile
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=3)

# Create a lock for Chrome instances to prevent concurrent usage
chrome_lock = threading.Lock()

def capture_website_screenshot(url: str, session_id: str = None) -> dict:
    """
    Captures a screenshot of the entire website using headless browser.
    Optimized for Heroku environment.
    """
    driver = None
    tmp_path = None
    
    try:
        # Use session_id in filename if provided
        if session_id:
            filename = f"{session_id}_screenshot.jpg"
        else:
            filename = f"screenshot_{int(time.time())}.jpg"
        
        print(f"Attempting to capture screenshot for URL: {url}")
        
        # Set up Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set page load strategy to eager
        chrome_options.page_load_strategy = 'eager'
        
        # IMPORTANT: Remove user-data-dir related arguments for Heroku
        # Don't use these in Heroku:
        # chrome_options.add_argument(f"--user-data-dir={unique_temp_dir}")
        # chrome_options.add_argument(f"--data-path={unique_temp_dir}")
        # chrome_options.add_argument(f"--disk-cache-dir={unique_temp_dir}/cache")
        
        # Additional options for Heroku environment
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--disable-software-rasterizer")
        
        # Memory optimization for container environments
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        
        # Heroku specific: Set Chrome binary location if available
        chrome_bin = os.environ.get("GOOGLE_CHROME_BIN")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        
        # Heroku specific: Set ChromeDriver path if available
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        
        try:
            # Initialize driver
            print("Initializing Chrome driver...")
            if chromedriver_path:
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            
            print(f"Navigating to URL: {url}")
            try:
                driver.get(url)
            except Exception as e:
                print(f"Page load timeout/error, continuing anyway: {e}")
            
            # Wait for page to stabilize
            time.sleep(3)
            
            # Take screenshot
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                print("Taking screenshot...")
                
                screenshot_success = driver.save_screenshot(tmp_path)
                
                if not screenshot_success:
                    raise Exception("Failed to save screenshot")
                
                # Read the screenshot file
                with open(tmp_path, 'rb') as f:
                    file_content = f.read()
                
                storage_path = f"screenshots/{filename}"
                
                # TODO: Uncomment when ready to use Supabase
                # # Remove existing file if present
                try:
                    supabase.storage.from_('static').remove([storage_path])
                except:
                    pass
                
                response = supabase.storage.from_('static').upload(
                    storage_path,
                    file_content,
                    {
                        "content-type": "image/jpeg",
                        "upsert": "true"
                    }
                )
                
                # Handle the response
                if hasattr(response, 'error') and response.error:
                    if "already exists" in str(response.error):
                        public_url = supabase.storage.from_('static').get_public_url(storage_path)
                        return {
                            "status": "success",
                            "message": "Screenshot captured successfully",
                            "path": storage_path,
                            "public_url": public_url,
                            "filename": filename
                        }
                    else:
                        raise Exception(f"Failed to upload: {response.error}")
                else:
                    public_url = supabase.storage.from_('static').get_public_url(storage_path)
                    return {
                        "status": "success",
                        "message": "Screenshot captured successfully",
                        "path": storage_path,
                        "public_url": public_url,
                        "filename": filename
                    }
                
                # Temporary return for testing without Supabase
                # return {
                #     "status": "success",
                #     "message": "Screenshot captured successfully",
                #     "path": storage_path,
                #     "public_url": f"/temp/{filename}",  # Mock URL for testing
                #     "filename": filename,
                #     "file_size": len(file_content)
                # }
                    
        finally:
            # Cleanup
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"Error closing driver: {e}")
            
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Error removing temp file: {e}")
                    
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"Error capturing screenshot: {e}")
        print(f"Traceback: {error_traceback}")
        
        return {
            "status": "error",
            "message": str(e),
            "error_details": error_traceback,
            "path": None
        }

async def capture_website_screenshot_async(url: str, session_id: str = None) -> dict:
    """Async wrapper for capturing website screenshot"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        capture_website_screenshot,
        url,
        session_id
    )

def get_website_favicon(url: str, session_id: str = None) -> dict:
    """
    Gets the favicon from a website and saves it to Supabase Storage.
    Synchronous version for backward compatibility.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_website_favicon_async(url, session_id))
    finally:
        loop.close()

async def get_website_favicon_async(url: str, session_id: str = None) -> dict:
    """
    Async function to get website favicon
    """
    print(f"Getting favicon for URL: {url}, session_id: {session_id}")
    
    try:
        # Create filename
        if session_id:
            filename = f"{session_id}_logo.jpg"
        else:
            filename = f"logo_{int(time.time())}.jpg"
        
        # Use aiohttp for async HTTP requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # NO TIMEOUT - let it take as long as needed
        timeout = aiohttp.ClientTimeout(total=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Get the website HTML
            async with session.get(url, headers=headers) as response:
                html_text = await response.text()
                
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # Look for favicon
            favicon_url = None
            for link in soup.find_all('link'):
                rel = link.get('rel', [])
                if isinstance(rel, list):
                    rel = ' '.join(rel).lower()
                else:
                    rel = rel.lower()
                    
                if 'icon' in rel or 'shortcut icon' in rel or 'apple-touch-icon' in rel:
                    favicon_url = link.get('href')
                    print(f"Found favicon link: {favicon_url}")
                    break
            
            # Default favicon location
            if not favicon_url:
                favicon_url = f"{url}/favicon.ico"
                print(f"No favicon link found, trying default: {favicon_url}")
            
            # Fix relative URLs
            if favicon_url and not favicon_url.startswith('http'):
                if favicon_url.startswith('//'):
                    favicon_url = 'https:' + favicon_url
                elif favicon_url.startswith('/'):
                    base_url = '/'.join(url.split('/')[0:3])
                    favicon_url = base_url + favicon_url
                else:
                    base_url = '/'.join(url.split('/')[0:3])
                    favicon_url = f"{base_url}/{favicon_url}"
            
            # Download favicon
            if favicon_url:
                try:
                    async with session.get(favicon_url, headers=headers) as favicon_response:
                        if favicon_response.status == 200:
                            favicon_content = await favicon_response.read()
                            
                            # Convert to JPG using PIL
                            img = Image.open(BytesIO(favicon_content))
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            # Save to temporary file
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                                tmp_path = tmp_file.name
                                img.save(tmp_path, 'JPEG')
                            
                            # Upload to Supabase
                            with open(tmp_path, 'rb') as f:
                                file_content = f.read()
                            
                            storage_path = f"favicons/{filename}"
                            
                            # Remove existing file if present
                            try:
                                supabase.storage.from_('static').remove([storage_path])
                            except:
                                pass
                            
                            response = supabase.storage.from_('static').upload(
                                storage_path,
                                file_content,
                                {
                                    "content-type": "image/jpeg",
                                    "upsert": "true"
                                }
                            )
                            
                            # Clean up
                            os.unlink(tmp_path)
                            
                            # Handle the response properly
                            if hasattr(response, 'error') and response.error:
                                # Check if it's just a duplicate file error
                                if "already exists" in str(response.error):
                                    public_url = supabase.storage.from_('static').get_public_url(storage_path)
                                    return {
                                        "status": "success",
                                        "message": "Favicon captured successfully",
                                        "path": storage_path,
                                        "public_url": public_url,
                                        "filename": filename
                                    }
                                else:
                                    return {
                                        "status": "error",
                                        "message": f"Upload error: {response.error}",
                                        "path": None
                                    }
                            else:
                                # Success case
                                public_url = supabase.storage.from_('static').get_public_url(storage_path)
                                return {
                                    "status": "success",
                                    "message": "Favicon captured successfully",
                                    "path": storage_path,
                                    "public_url": public_url,
                                    "filename": filename
                                }
                except Exception as e:
                    print(f"Error downloading favicon: {e}")
                    
        return {
            "status": "error",
            "message": "No favicon found",
            "path": None
        }
        
    except Exception as e:
        print(f"Error fetching favicon: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "path": None
        }