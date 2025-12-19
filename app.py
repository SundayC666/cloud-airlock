from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import time
import json
import os
import boto3
import whois
from datetime import datetime, timezone 

# ⚠️ CONFIGURATION: Verify this matches your actual S3 Bucket name
BUCKET_NAME = "cloud-airlock-evidence-2025-v1" 

def upload_to_s3(local_path, url):
    """ Uploads screenshot to AWS S3 and generates a unique key """
    s3 = boto3.client('s3')
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")
    s3_filename = f"evidence/{timestamp}_{safe_url}.png"
    
    try:
        s3.upload_file(local_path, BUCKET_NAME, s3_filename)
        return s3_filename
    except Exception as e:
        print(f"⚠️ S3 Upload Warning: {e}")
        return None

def get_domain_age(url):
    """
    Telemetry Signal: Checks domain registration age via Whois.
    Fix: Handles timezone-aware vs naive datetimes.
    """
    domain = urlparse(url).netloc
    print(f"🔍 Checking Whois for domain: {domain}")
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        
        # Whois sometimes returns a list of dates; take the first one
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        if creation_date:
            # --- Timezone Fix Start ---
            # 1. Get current time in UTC (aware)
            now = datetime.now(timezone.utc)
            
            # 2. Check if creation_date is naive (no timezone), if so, assume UTC
            if creation_date.tzinfo is None:
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            
            # 3. Calculate days difference
            age_days = (now - creation_date).days
            # --- Timezone Fix End ---
            
            return age_days, str(creation_date)
            
    except Exception as e:
        print(f"⚠️ Whois lookup failed: {e}")
    
    return None, "Unknown"

def ai_logo_detection(s3_bucket, s3_key):
    """ 
    AWS Rekognition: Performs visual analysis to detect brand logos.
    """
    rekognition = boto3.client('rekognition')
    detected_brands = []
    
    if not s3_key:
        return []

    try:
        print(f"🧠 AI Analyzing visual evidence...")
        response = rekognition.detect_text(
            Image={'S3Object': {'Bucket': s3_bucket, 'Name': s3_key}}
        )
        
        for text in response['TextDetections']:
            if text['Type'] == 'LINE' and text['Confidence'] > 85:
                content = text['DetectedText'].lower()
                if "google" in content: detected_brands.append("Google")
                elif "microsoft" in content: detected_brands.append("Microsoft")
                elif "paypal" in content: detected_brands.append("PayPal")
                elif "apple" in content: detected_brands.append("Apple")
                    
        return list(set(detected_brands))
    except Exception as e:
        print(f"⚠️ AI Analysis Failed: {e}")
        return []

def analyze_risk(driver, url, page_title, ai_brands):
    """
    Comprehensive Risk Scoring Engine (0-100 Score).
    """
    score = 0
    reasons = []
    domain = urlparse(url).netloc.lower()
    
    # 1. [Telemetry] Domain Age Check
    age_days, creation_date = get_domain_age(url)
    if age_days is not None and age_days < 30:
        score += 40
        reasons.append(f"🚨 NEW DOMAIN: Registered only {age_days} days ago (+40)")
    
    # 2. [Visual] AI Brand Spoofing Detection
    for brand in ai_brands:
        official_domains = {
            "Google": "google.com", 
            "Microsoft": "microsoft.com", 
            "PayPal": "paypal.com", 
            "Apple": "apple.com"
        }
        official = official_domains.get(brand)
        if official and official not in domain:
            score += 50
            reasons.append(f"🚨 VISUAL SPOOFING: Found '{brand}' logo but domain is not '{official}' (+50)")

    # 3. [Heuristic] Password Input Detection
    password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
    if len(password_inputs) > 0:
        score += 20
        reasons.append("Input: Password field detected (+20)")

    # 4. [Heuristic] Suspicious Keyword Detection
    page_source = driver.page_source.lower()
    suspicious_keywords = ["verify your account", "urgent action", "suspended", "account locked"]
    if any(k in page_source for k in suspicious_keywords):
        score += 10
        reasons.append("Content: Suspicious urgency keywords detected (+10)")

    final_score = min(score, 100)
    
    risk_level = "LOW"
    if final_score >= 80: risk_level = "CRITICAL"
    elif final_score >= 50: risk_level = "HIGH"
    
    return {
        "score": final_score,
        "risk_level": risk_level,
        "domain_age_days": age_days,
        "reasons": reasons
    }

def take_screenshot(target_url):
    print(f"🚀 Starting Cloud-Airlock scan for: {target_url}")
    
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/google-chrome"
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
    
    os.environ['WDM_CACHE_DIR'] = '/tmp/wdm_cache'
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"🔗 Navigating to {target_url}...")
        driver.get(target_url)
        time.sleep(3)

        page_title = driver.title
        screenshot_path = "/tmp/evidence.png"
        driver.save_screenshot(screenshot_path)
        
        s3_key = upload_to_s3(screenshot_path, target_url)
        ai_brands = ai_logo_detection(BUCKET_NAME, s3_key)
        risk_analysis = analyze_risk(driver, target_url, page_title, ai_brands)
        print(f"⚠️ Risk Score: {risk_analysis['score']} - {risk_analysis['reasons']}")
        
        return {
            "status": "success",
            "url": target_url,
            "title": page_title,
            "s3_key": s3_key,
            "risk_analysis": risk_analysis
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        try: driver.quit()
        except: pass

def handler(event, context):
    print("Received event:", json.dumps(event))
    target_url = event.get("url", "https://www.google.com")
    result = take_screenshot(target_url)
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }