from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
import shutil

def take_screenshot(target_url):
    print(f"🚀 Starting Cloud-Airlock scan for: {target_url}")

    # 1. Configure Chrome Options
    chrome_options = Options()
    
    # Use the new Headless mode
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280x1696")
    
    # 🛑 CRITICAL FIX: Removed "--single-process" 
    # This flag causes crashes in Chrome 143+ on AWS Lambda.
    
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    
    # Fix for file permissions in Lambda /tmp directory
    chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-user-data")
    chrome_options.add_argument(f"--data-path=/tmp/chrome-data-path")
    chrome_options.add_argument(f"--disk-cache-dir=/tmp/chrome-cache")
    
    # Debugging flags
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_argument("--verbose") 
    
    # Explicitly specify the binary location (Safety check)
    chrome_options.binary_location = "/usr/bin/google-chrome"

    print("🔧 Initializing Headless Chrome...")
    
    # Set the cache directory for webdriver_manager to /tmp
    os.environ['WDM_CACHE_DIR'] = '/tmp/wdm_cache'

    # Initialize the browser
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 2. Navigate to the target URL
        print(f"🔗 Navigating to {target_url}...")
        driver.get(target_url)
        
        # Wait for the page to load
        time.sleep(2) 

        # 3. Extract metadata
        page_title = driver.title
        print(f"✅ Page Title: {page_title}")

        # 4. Capture screenshot
        screenshot_path = "/tmp/evidence.png"
        driver.save_screenshot(screenshot_path)
        print(f"📸 Screenshot saved locally at: {screenshot_path}")
        
        return {
            "status": "success",
            "title": page_title,
            "url": target_url,
            "screenshot_local_path": screenshot_path
        }

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        # 5. Cleanup
        try:
            driver.quit()
            print("🔒 Browser closed.")
        except Exception:
            pass

def handler(event, context):
    """
    AWS Lambda Entry Point.
    """
    print("Received event:", json.dumps(event))
    
    # Parse target URL, default to Google if not provided
    target_url = event.get("url", "https://www.google.com")
    
    result = take_screenshot(target_url)
    
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }