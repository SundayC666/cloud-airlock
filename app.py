from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
import boto3
from datetime import datetime

# ⚠️ CONFIGURATION: Replace with your actual S3 Bucket name
BUCKET_NAME = "cloud-airlock-evidence-2025-v1" 

def upload_to_s3(local_path, url):
    """
    Uploads the screenshot to AWS S3 and generates a unique filename.
    """
    s3 = boto3.client('s3')
    
    # Generate a unique filename based on time and target URL
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Simple clean up of the URL for the filename
    safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")
    s3_filename = f"evidence/{timestamp}_{safe_url}.png"
    
    print(f"⬆️ Uploading {local_path} to S3 bucket: {BUCKET_NAME}...")
    
    try:
        s3.upload_file(local_path, BUCKET_NAME, s3_filename)
        print(f"✅ Upload successful! S3 Key: {s3_filename}")
        return s3_filename
    except Exception as e:
        print(f"❌ S3 Upload Failed: {e}")
        return None

def take_screenshot(target_url):
    print(f"🚀 Starting Cloud-Airlock scan for: {target_url}")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280x1696")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-user-data")
    chrome_options.add_argument(f"--data-path=/tmp/chrome-data-path")
    chrome_options.add_argument(f"--disk-cache-dir=/tmp/chrome-cache")
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_argument("--verbose") 
    chrome_options.binary_location = "/usr/bin/google-chrome"

    print("🔧 Initializing Headless Chrome...")
    os.environ['WDM_CACHE_DIR'] = '/tmp/wdm_cache'

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"🔗 Navigating to {target_url}...")
        driver.get(target_url)
        time.sleep(2) 

        page_title = driver.title
        print(f"✅ Page Title: {page_title}")

        screenshot_path = "/tmp/evidence.png"
        driver.save_screenshot(screenshot_path)
        print(f"📸 Screenshot saved locally at: {screenshot_path}")
        
        # --- NEW: Upload to S3 ---
        s3_key = upload_to_s3(screenshot_path, target_url)
        
        return {
            "status": "success",
            "title": page_title,
            "url": target_url,
            "s3_bucket": BUCKET_NAME,
            "s3_key": s3_key
        }

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        try:
            driver.quit()
        except Exception:
            pass

def handler(event, context):
    print("Received event:", json.dumps(event))
    target_url = event.get("url", "https://www.google.com")
    result = take_screenshot(target_url)
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }