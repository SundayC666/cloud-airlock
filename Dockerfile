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

# 4. Copy Project Files
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 5. Install Python Dependencies
RUN pip install -r requirements.txt

# 6. Copy Application Code
COPY app.py ${LAMBDA_TASK_ROOT}

# 7. Set the Container Entrypoint
# CRITICAL FIX: This must match the function name defined in app.py (lambda_handler)
CMD [ "app.lambda_handler" ]