# 🛡️ Cloud-Airlock: Serverless Phishing Analyzer

**Automated phishing evidence collector and risk scoring engine powered by AWS Lambda, Docker, and Computer Vision.**

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20S3%20%7C%20ECR-orange?logo=amazon-aws)
![Docker](https://img.shields.io/badge/Docker-Amazon%20Linux%202023-2496ED?logo=docker)
![Status](https://img.shields.io/badge/Status-Active-success)

## 📖 Overview

**Cloud-Airlock** is a "Safe Sandbox" designed for security analysts. It allows for the automated inspection of suspicious URLs without exposing the analyst's machine to potential malware or drive-by downloads.

Built on a **Serverless Architecture**, it launches a disposable Headless Chrome container to visit the target site, captures forensic evidence (screenshots, DOM structure), and analyzes the content using **Computer Vision (AWS Rekognition)** and **OSINT telemetry** to calculate a Phishing Risk Score.

## 🏗️ Architecture

The system utilizes an Event-Driven Architecture to ensure isolation and scalability.

```mermaid
graph LR
    User[Client / Slack Bot] -->|POST /scan| API[API Gateway]
    API -->|Trigger| Lambda[AWS Lambda (Docker)]
    
    subgraph "Secure Sandbox (Ephemeral)"
        Lambda -->|1. Launch| Chrome[Headless Chrome v143]
        Chrome -->|2. Scrape| Web[Suspicious Website]
    end
    
    Lambda -->|3. Store Evidence| S3[AWS S3]
    Lambda -->|4. Visual Analysis| AI[AWS Rekognition]
    Lambda -->|5. Whois Lookup| Whois[Domain Registry]
    
    Lambda -->|6. Return JSON| User
```

✨ Key Features
Secure Isolation: Execution happens in a temporary Docker container that is destroyed immediately after analysis.

Visual Brand Spoofing Detection: Integrates AWS Rekognition (AI) to detect if a site is visually mimicking major brands (Google, Microsoft, PayPal) on non-official domains.

Risk Scoring Engine (0-100): Calculates a risk score based on:

Telemetry: Domain age (High risk for domains < 30 days old).

Heuristics: Presence of password input fields and urgency keywords.

Computer Vision: Logo/Brand mismatch.

Evidence Preservation: Automatically uploads screenshots and logs to AWS S3 for forensic audit trails.

🔧 Technical Challenges & Solutions
1. The "Dependency Hell" of Headless Chrome
Running the latest Chrome (v143) on AWS Lambda is non-trivial due to glibc version conflicts.

Problem: The standard Lambda Python runtime lacks the necessary shared libraries for Chrome v143.

Solution: I engineered a custom Docker image based on Amazon Linux 2023. I bypassed the standard dnf package manager limitations by implementing a direct rpm injection strategy to install Chrome dependencies within the Lambda size limits.

2. Timezone-Aware Telemetry
Problem: Integrating Whois data caused crashes due to Python's datetime offset-naive vs. offset-aware conflicts.

Solution: Implemented a robust timezone normalization layer to standardizing all timestamps to UTC before performing date arithmetic calculations.

🚀 Usage (API)
You can trigger a scan using curl or any HTTP client.

Endpoint: POST https://3e3ax9d659.execute-api.us-east-1.amazonaws.com/scan

Request:
curl -X POST "https://3e3ax9d659.execute-api.us-east-1.amazonaws.com/scan" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.google.com"}'

Response (Example):
{
    "status": "success",
    "url": "https://www.google.com",
    "risk_analysis": {
        "score": 0,
        "risk_level": "LOW",
        "domain_age_days": 10322,
        "reasons": []
    },
    "s3_key": "evidence/20251219-222148_www.google.com.png"
}

🛠️ Tech Stack
Runtime: Python 3.12, Amazon Linux 2023

Browser Automation: Selenium WebDriver, Google Chrome (Headless)

Cloud Infrastructure: AWS Lambda, API Gateway, S3, ECR

AI/ML: AWS Rekognition (OCR & Object Detection)

DevOps: Docker, Git

📜 License
MIT License