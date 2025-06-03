# Add these imports at the top of web_scrape.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Can use anon key since bucket is public
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def capture_website_screenshot(url: str, session_id: str = None) -> dict:
    """
    Captures a screenshot of the entire website using headless browser.
    Uploads to Supabase Storage instead of local filesystem.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import time
    import traceback
    import tempfile

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
        
        # Create unique user data directory for each instance
        import tempfile
        user_data_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Initialize driver with options
        print("Initializing Chrome driver...")
        driver = webdriver.Chrome(options=chrome_options)
        
        print(f"Navigating to URL: {url}")
        # No timeout - let it take as long as needed
        driver.get(url)
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Use temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            print("Taking screenshot...")
            screenshot_success = driver.save_screenshot(tmp_path)
            
            if not screenshot_success:
                print("Driver save_screenshot returned False")
                driver.quit()
                return {
                    "status": "error",
                    "message": "Failed to save screenshot",
                    "path": None
                }
            
            driver.quit()
            
            # Clean up temp user data directory
            try:
                import shutil
                shutil.rmtree(user_data_dir)
            except:
                pass
            
            # Upload to Supabase Storage
            with open(tmp_path, 'rb') as f:
                file_content = f.read()
                
            # Upload to 'static/screenshots' folder in your bucket
            storage_path = f"screenshots/{filename}"
            
            # Check if file already exists and remove it
            try:
                existing = supabase.storage.from_('static').list(path='screenshots/')
                if any(f['name'] == filename for f in existing):
                    supabase.storage.from_('static').remove([storage_path])
            except:
                pass
            
            response = supabase.storage.from_('static').upload(
                storage_path,
                file_content,
                {
                    "content-type": "image/jpeg",
                    "upsert": "true"  # Allow overwriting
                }
            )
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if response.status_code == 200 or (response.status_code == 400 and "already exists" in str(response.json())):
                # Get public URL
                public_url = supabase.storage.from_('static').get_public_url(storage_path)
                
                print(f"Screenshot uploaded successfully: {public_url}")
                return {
                    "status": "success",
                    "message": "Screenshot captured successfully",
                    "path": storage_path,
                    "public_url": public_url,
                    "filename": filename
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to upload to Supabase: {response.json()}",
                    "path": None
                }
        
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

def get_website_favicon(url: str, session_id: str = None) -> dict:
    """
    Gets the favicon from a website and saves it to Supabase Storage.
    """
    from bs4 import BeautifulSoup
    import requests
    import time
    from PIL import Image
    from io import BytesIO
    import tempfile
    
    print(f"Getting favicon for URL: {url}, session_id: {session_id}")

    try:
        # Create filename with timestamp or session ID
        if session_id:
            filename = f"{session_id}_logo.jpg"
        else:
            filename = f"logo_{int(time.time())}.jpg"
        
        # Get the website's HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        print(f"Sending HTTP request to {url}")
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for favicon in link tags
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
        
        # If no favicon found, try default location
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
            
            print(f"Resolved favicon URL: {favicon_url}")
        
        # Download the favicon
        if favicon_url:
            try:
                print(f"Requesting favicon from {favicon_url}")
                favicon_response = requests.get(favicon_url, headers=headers, timeout=15, stream=True)
                if favicon_response.status_code == 200:
                    # Convert to JPG
                    img = Image.open(BytesIO(favicon_response.content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                        tmp_path = tmp_file.name
                        img.save(tmp_path, 'JPEG')
                    
                    # Upload to Supabase Storage
                    with open(tmp_path, 'rb') as f:
                        file_content = f.read()
                    
                    storage_path = f"favicons/{filename}"
                    
                    # Check if file already exists and remove it
                    try:
                        existing = supabase.storage.from_('static').list(path='favicons/')
                        if any(f['name'] == filename for f in existing):
                            supabase.storage.from_('static').remove([storage_path])
                    except:
                        pass
                    
                    response = supabase.storage.from_('static').upload(
                        storage_path,
                        file_content,
                        {
                            "content-type": "image/jpeg",
                            "upsert": "true"  # Allow overwriting
                        }
                    )
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if response.status_code == 200 or (response.status_code == 400 and "already exists" in str(response.json())):
                        public_url = supabase.storage.from_('static').get_public_url(storage_path)
                        
                        print(f"Favicon uploaded successfully: {public_url}")
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
                            "message": f"Failed to upload favicon: {response.json()}",
                            "path": None
                        }
                else:
                    print(f"Failed to download favicon, status code: {favicon_response.status_code}")
            except Exception as e:
                print(f"Error downloading favicon from {favicon_url}: {e}")
        
        print("No favicon found or could not be downloaded")
        return {
            "status": "error",
            "message": "No favicon found",
            "path": None
        }
    
    except Exception as e:
        print(f"Error fetching favicon: {e}")
        return {
            "status": "error",
            "message": str(e),
            "path": None
        }