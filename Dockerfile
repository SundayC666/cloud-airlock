# 1. Base Image: Python 3.12 (Amazon Linux 2023)
FROM public.ecr.aws/lambda/python:3.12

# 2. Install System Dependencies
# We explicitly install 'rpm' and libraries required for Headless Chrome.
# 'whois' is added for domain age telemetry.
RUN dnf install -y \
    rpm \
    atk cups-libs gtk3 libXcomposite libXcursor libXdamage libXext libXi libXtst \
    pango alsa-lib tar gzip unzip nss nss-util nspr mesa-libgbm \
    libXrandr libXScrnSaver libdrm libxkbcommon xdg-utils iputils \
    liberation-fonts liberation-serif-fonts liberation-sans-fonts liberation-mono-fonts \
    vulkan-loader \
    wget \
    whois

# 3. Download and Install Google Chrome
# Strategy: Use 'rpm -ivh' to bypass dnf local file resolution issues on AL2023.
RUN cd /tmp && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm && \
    rpm -ivh google-chrome-stable_current_x86_64.rpm && \
    rm google-chrome-stable_current_x86_64.rpm

# 4. Install ChromeDriver matching Chrome version
# Get the full Chrome version (all 4 parts: major.minor.build.patch)
RUN CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}') && \
    echo "Chrome version: $CHROME_VERSION" && \
    CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
    echo "Downloading chromedriver from: $CHROMEDRIVER_URL" && \
    cd /tmp && \
    wget -q "$CHROMEDRIVER_URL" -O chromedriver.zip && \
    unzip chromedriver.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf chromedriver.zip chromedriver-linux64 && \
    echo "ChromeDriver installed: $(chromedriver --version)"

# 5. Copy Project Files
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 6. Install Python Dependencies
RUN pip install -r requirements.txt

# 7. Copy Application Code
COPY app.py ${LAMBDA_TASK_ROOT}

# 8. Set the Container Entrypoint
# CRITICAL FIX: This must match the function name defined in app.py (lambda_handler)
CMD [ "app.lambda_handler" ]