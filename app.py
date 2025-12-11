from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def take_screenshot(target_url):
    print(f"🚀 Starting Cloud-Airlock scan for: {target_url}")

    # 1. Configure Chrome Options (Critical for Serverless/Docker environments)
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Headless mode: Run without a UI window
    chrome_options.add_argument("--no-sandbox") # Bypass OS security model (Required for Docker)
    chrome_options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    chrome_options.add_argument("--disable-gpu") # Disable GPU hardware acceleration
    chrome_options.add_argument("--window-size=1280x1696") # Set the screenshot resolution

    # 2. Initialize Headless Chrome Browser
    print("🔧 Initializing Headless Chrome...")
    # Use webdriver_manager to automatically download and install the compatible ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 3. Navigate to the target URL
        print("🔗 Navigating to URL...")
        driver.get(target_url)
        
        # Wait for the page to load (We will implement smarter waits later)
        time.sleep(3) 

        # 4. Extract page metadata (e.g., Title) for evidence
        page_title = driver.title
        print(f"✅ Page Title: {page_title}")

        # 5. Capture screenshot and save to disk
        filename = "evidence.png"
        driver.save_screenshot(filename)
        print(f"📸 Screenshot saved as: {filename}")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

    finally:
        # 6. Close the browser to release resources (Crucial for Lambda)
        driver.quit()
        print("🔒 Browser closed.")

if __name__ == "__main__":
    # Test case: Scan Google's homepage
    take_screenshot("https://www.google.com")