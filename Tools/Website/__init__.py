# Website Analysis Tools
# Contains website screenshot and favicon capture functionality

from .web_scrape import capture_website_screenshot, capture_website_screenshot_async, get_website_favicon, get_website_favicon_async

__all__ = [
    'capture_website_screenshot', 
    'capture_website_screenshot_async',
    'get_website_favicon',
    'get_website_favicon_async'
]