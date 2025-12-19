# 1. Base Image: Python 3.12 (Amazon Linux 2023)
FROM public.ecr.aws/lambda/python:3.12

# 2. Install System Dependencies
# Note: We explicitly install 'rpm' to use it for the Chrome installation, 
# bypassing dnf's local file resolution issues.
# We also added 'whois' for domain age telemetry.
RUN dnf install -y \
    rpm \
    atk cups-libs gtk3 libXcomposite libXcursor libXdamage libXext libXi libXtst \
    pango alsa-lib tar gzip unzip nss nss-util nspr mesa-libgbm \
    libXrandr libXScrnSaver libdrm libxkbcommon xdg-utils iputils \
    liberation-fonts liberation-serif-fonts liberation-sans-fonts liberation-mono-fonts \
    vulkan-loader \
    wget \
    whois

# 3. Download and Install Google Chrome (Force Install)
# Strategy: We use 'rpm -ivh' (Install Verbose Hash) instead of 'dnf'.
# This bypasses the "Package not found" bug when installing local RPMs on AL2023.
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
CMD [ "app.handler" ]