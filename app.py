import json
import os
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3
import whois
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

# Initialize Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')

# Environment Variables
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'cloud-airlock-evidence')

# Known brand domains for brand matching
BRAND_DOMAINS = {
    'google': ['google.com', 'gmail.com', 'youtube.com'],
    'microsoft': ['microsoft.com', 'outlook.com', 'live.com', 'office.com'],
    'apple': ['apple.com', 'icloud.com'],
    'amazon': ['amazon.com', 'aws.amazon.com'],
    'facebook': ['facebook.com', 'fb.com', 'meta.com'],
    'paypal': ['paypal.com'],
    'netflix': ['netflix.com'],
    'linkedin': ['linkedin.com'],
    'twitter': ['twitter.com', 'x.com'],
    'instagram': ['instagram.com'],
}

# 1. Initialize Slack App
# It automatically reads environment variables: SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET
app = App(process_before_response=True)


# ============================================
# Scanner Module
# ============================================

def scan_url(url):
    """
    Launch Headless Chrome to visit target URL.
    Returns: (screenshot_bytes, html, final_url)
    """
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1280,720')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--user-data-dir=/tmp/chrome-data')
    chrome_options.binary_location = '/usr/bin/google-chrome-stable'

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)

        driver.get(url)

        # Wait for page to stabilize
        driver.implicitly_wait(3)

        # Capture screenshot as PNG bytes
        screenshot_bytes = driver.get_screenshot_as_png()

        # Get page source (HTML)
        html = driver.page_source

        # Get final URL (after redirects)
        final_url = driver.current_url

        logger.info(f"Successfully scanned URL: {url} -> {final_url}")
        return screenshot_bytes, html, final_url

    except Exception as e:
        logger.error(f"Error scanning URL {url}: {str(e)}")
        raise
    finally:
        if driver:
            driver.quit()


# ============================================
# Evidence Module (S3 Upload)
# ============================================

def generate_scan_id():
    """Generate unique scan ID with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}-{unique_id}"


def upload_evidence(screenshot_bytes, scan_id):
    """
    Upload screenshot to S3.
    Returns: S3 object URL
    """
    key = f"scans/{scan_id}/screenshot.png"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=screenshot_bytes,
            ContentType='image/png'
        )

        # Generate presigned URL for viewing (valid for 7 days)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': key},
            ExpiresIn=604800  # 7 days
        )

        logger.info(f"Uploaded evidence to s3://{S3_BUCKET_NAME}/{key}")
        return presigned_url

    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise


# ============================================
# Risk Scoring Module
# ============================================

def get_domain_age(url):
    """
    Query Whois to get domain registration age in days.
    Returns: number of days since registration, or None if unavailable
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc

        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]

        w = whois.whois(domain)

        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if creation_date:
            # Normalize to UTC
            if creation_date.tzinfo is None:
                creation_date = creation_date.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            age_days = (now - creation_date).days
            logger.info(f"Domain {domain} age: {age_days} days")
            return age_days

    except Exception as e:
        logger.warning(f"Whois lookup failed for {url}: {str(e)}")

    return None


def has_password_field(html):
    """
    Check if HTML contains password input fields.
    Returns: True if password field detected
    """
    # Pattern to match password input fields
    patterns = [
        r'<input[^>]*type=["\']password["\'][^>]*>',
        r'<input[^>]*type=password[^>]*>',
    ]

    for pattern in patterns:
        if re.search(pattern, html, re.IGNORECASE):
            logger.info("Password field detected in page")
            return True

    return False


# Urgency keywords commonly used in phishing attacks
URGENCY_KEYWORDS = [
    # Account threats
    r'account.{0,20}(suspend|terminat|disabl|lock|restrict|compromis)',
    r'(suspend|terminat|disabl|lock|restrict).{0,20}account',
    r'unauthorized.{0,20}(access|activity|login)',
    # Time pressure
    r'(immediate|urgent|within|action required)',
    r'(24|48|72).{0,5}hours?',
    r'expires?.{0,10}(today|soon|immediately)',
    # Verification demands
    r'verify.{0,20}(your|account|identity|information)',
    r'confirm.{0,20}(your|account|identity|information)',
    r'update.{0,20}(your|account|payment|billing)',
    # Threat language
    r'failure to.{0,20}(comply|respond|verify)',
    r'will (be|result in).{0,20}(suspend|terminat|lock|los)',
    # Common phishing phrases
    r'click.{0,10}(here|below|link).{0,10}(to verify|to confirm|to update)',
    r'unusual.{0,20}(activity|sign-in|login)',
]


def detect_urgency_keywords(html):
    """
    Detect urgency/threat keywords commonly used in phishing.
    Returns: list of matched keyword patterns
    """
    # Remove HTML tags for text analysis
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.lower()

    matched_keywords = []

    for pattern in URGENCY_KEYWORDS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            matched_keywords.extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])

    # Deduplicate and limit
    unique_keywords = list(set(matched_keywords))[:5]

    if unique_keywords:
        logger.info(f"Urgency keywords detected: {unique_keywords}")

    return unique_keywords


def detect_brands(screenshot_bytes):
    """
    Use AWS Rekognition to detect brand logos in screenshot.
    Returns: list of detected brand names
    """
    try:
        response = rekognition_client.detect_labels(
            Image={'Bytes': screenshot_bytes},
            MaxLabels=20,
            MinConfidence=70
        )

        detected_brands = []
        brand_keywords = list(BRAND_DOMAINS.keys())

        for label in response['Labels']:
            label_name = label['Name'].lower()
            for brand in brand_keywords:
                if brand in label_name:
                    detected_brands.append(brand.capitalize())

        # Also use detect_text for logo text
        text_response = rekognition_client.detect_text(
            Image={'Bytes': screenshot_bytes}
        )

        for text_detection in text_response['TextDetections']:
            if text_detection['Type'] == 'WORD':
                word = text_detection['DetectedText'].lower()
                for brand in brand_keywords:
                    if brand == word and brand.capitalize() not in detected_brands:
                        detected_brands.append(brand.capitalize())

        logger.info(f"Detected brands: {detected_brands}")
        return list(set(detected_brands))

    except Exception as e:
        logger.warning(f"Rekognition detection failed: {str(e)}")
        return []


def domain_matches_brand(url, brands):
    """
    Check if the URL domain matches any detected brands.
    Returns: True if domain legitimately belongs to detected brand
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for brand in brands:
        brand_lower = brand.lower()
        if brand_lower in BRAND_DOMAINS:
            legitimate_domains = BRAND_DOMAINS[brand_lower]
            for legit_domain in legitimate_domains:
                if domain == legit_domain or domain.endswith('.' + legit_domain):
                    return True

    return False


def analyze_risk(url, html, screenshot_bytes):
    """
    Multi-factor risk scoring engine.
    Returns: (score 0-100, list of risk factors)
    """
    score = 0
    factors = []

    # A. Domain Age Analysis
    domain_age = get_domain_age(url)
    if domain_age is not None:
        if domain_age < 7:
            score += 45
            factors.append(f"⚠️ Very new domain ({domain_age} days old)")
        elif domain_age < 30:
            score += 35
            factors.append(f"⚠️ New domain ({domain_age} days old)")
        elif domain_age < 90:
            score += 15
            factors.append(f"📅 Recently registered domain ({domain_age} days old)")
    else:
        factors.append("❓ Domain age unknown (Whois lookup failed)")

    # B. Password Field Detection
    if has_password_field(html):
        score += 25
        factors.append("🔐 Password input field detected")

    # C. Urgency Keywords Detection
    urgency_matches = detect_urgency_keywords(html)
    if urgency_matches:
        score += 20
        factors.append(f"⏰ Urgency keywords detected: {', '.join(urgency_matches[:3])}")

    # D. Brand Spoofing Detection
    detected_brands = detect_brands(screenshot_bytes)
    if detected_brands:
        if not domain_matches_brand(url, detected_brands):
            score += 35
            factors.append(f"🎭 Brand spoofing suspected: {', '.join(detected_brands)}")
        else:
            factors.append(f"✅ Legitimate brand domain: {', '.join(detected_brands)}")

    # Cap score at 100
    score = min(score, 100)

    logger.info(f"Risk analysis complete: score={score}, factors={factors}")
    return score, factors


# ============================================
# Report Formatting
# ============================================

def get_risk_level(score):
    """Convert numeric score to risk level."""
    if score >= 70:
        return "🔴 HIGH RISK"
    elif score >= 40:
        return "🟡 MEDIUM RISK"
    else:
        return "🟢 LOW RISK"


def format_report(url, final_url, score, factors, evidence_url, scan_id):
    """Format the scan results into a Slack message."""
    risk_level = get_risk_level(score)

    # Build factors list
    factors_text = "\n".join([f"  • {f}" for f in factors]) if factors else "  • No risk factors detected"

    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 *Phishing Scan Report*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Target URL:* {url}
*Final URL:* {final_url}
*Scan ID:* `{scan_id}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*Risk Score:* {score}/100  {risk_level}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Risk Factors:*
{factors_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📸 *Evidence:* <{evidence_url}|View Screenshot>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report


# ============================================
# Slack Handlers
# ============================================

# Handle Slack's "Challenge" (URL Verification)
@app.event("url_verification")
def handle_challenge(body, logger):
    return body["challenge"]


# Handle the "/scan" command
@app.command("/scan")
def handle_scan_command(ack, body, respond):
    # Acknowledge within 3 seconds to prevent Slack timeout
    ack()

    user_id = body["user_id"]
    url = body["text"].strip()

    # Validate URL
    if not url:
        respond("❌ Please provide a URL to scan. Usage: `/scan https://example.com`")
        return

    # Add https:// if no protocol specified
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    scan_id = generate_scan_id()

    # Send initial response
    respond(f"🔍 *Scan initiated*\n• Target: `{url}`\n• Scan ID: `{scan_id}`\n\n⏳ Analyzing... This may take 15-30 seconds.")

    try:
        # 1. Scan URL with headless Chrome
        screenshot_bytes, html, final_url = scan_url(url)

        # 2. Upload evidence to S3
        evidence_url = upload_evidence(screenshot_bytes, scan_id)

        # 3. Analyze risk factors
        score, factors = analyze_risk(url, html, screenshot_bytes)

        # 4. Format and send report
        report = format_report(url, final_url, score, factors, evidence_url, scan_id)
        respond(report)

        logger.info(f"Scan completed: {scan_id} - Score: {score}")

    except Exception as e:
        logger.error(f"Scan failed for {url}: {str(e)}")
        respond(f"❌ *Scan failed*\n• Target: `{url}`\n• Error: `{str(e)}`\n\nPlease check if the URL is accessible and try again.")


# ============================================
# REST API Handler
# ============================================

def handle_rest_api_scan(event):
    """
    Handle REST API scan requests.
    Returns: JSON response with scan results
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        url = body.get('url', '').strip()

        if not url:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Missing required parameter: url'
                })
            }

        # Add https:// if no protocol specified
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url

        scan_id = generate_scan_id()

        # 1. Scan URL
        screenshot_bytes, html, final_url = scan_url(url)

        # 2. Upload evidence
        s3_key = f"scans/{scan_id}/screenshot.png"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=screenshot_bytes,
            ContentType='image/png'
        )

        # 3. Analyze risk
        score, factors = analyze_risk(url, html, screenshot_bytes)

        # 4. Get domain age for response
        domain_age = get_domain_age(url)

        # Determine risk level
        if score >= 70:
            risk_level = "HIGH"
        elif score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Build response
        response_body = {
            'status': 'success',
            'url': url,
            'final_url': final_url,
            'scan_id': scan_id,
            'risk_analysis': {
                'score': score,
                'risk_level': risk_level,
                'domain_age_days': domain_age,
                'reasons': [f.replace('⚠️ ', '').replace('🔐 ', '').replace('⏰ ', '').replace('🎭 ', '').replace('✅ ', '').replace('❓ ', '').replace('📅 ', '') for f in factors]
            },
            's3_key': s3_key
        }

        logger.info(f"REST API scan completed: {scan_id} - Score: {score}")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body)
        }

    except Exception as e:
        logger.error(f"REST API scan failed: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            })
        }


# ============================================
# AWS Lambda Entry Point
# ============================================

def lambda_handler(event, context):
    """
    AWS Lambda handler - routes to Slack or REST API based on request type.
    """
    logger.info(f"Received event: {json.dumps(event)[:500]}")

    # Check if this is a Slack request (has slack-specific headers or body format)
    headers = event.get('headers', {}) or {}
    headers_lower = {k.lower(): v for k, v in headers.items()}

    # Slack requests have x-slack-signature header
    if 'x-slack-signature' in headers_lower:
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(event, context)

    # Check body for Slack-specific content
    body = event.get('body', '')
    if isinstance(body, str) and ('command=' in body or 'payload=' in body or '"type":"url_verification"' in body):
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(event, context)

    # Otherwise, treat as REST API request
    return handle_rest_api_scan(event)
