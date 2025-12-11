# 1. Base Image: Use the official AWS Lambda Python image
# This ensures the environment matches the actual AWS Lambda runtime.
FROM public.ecr.aws/lambda/python:3.9

# 2. Install Linux system dependencies required by Chrome
# Headless Chrome needs these libraries (e.g., Alsa, GTK, X11) to render pages even without a screen.
RUN yum install -y \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamn \
    libXext \
    libXi \
    libXtst \
    pango \
    xorg-x11-fonts-100dpi \
    xorg-x11-fonts-75dpi \
    xorg-x11-utils \
    xorg-x11-fonts-cyrillic \
    xorg-x11-fonts-Type1 \
    xorg-x11-fonts-misc \
    alsa-lib \
    tar \
    gzip \
    unzip \
    nss \
    nss-util \
    nspr \
    mesa-libgbm

# 3. Install Google Chrome
# Download and install the stable version of Chrome using yum.
RUN curl -LO https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
    && yum install -y ./google-chrome-stable_current_x86_64.rpm \
    && rm google-chrome-stable_current_x86_64.rpm

# 4. Copy Project Files
# ${LAMBDA_TASK_ROOT} is the default directory where Lambda expects code (/var/task).
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 5. Install Python Dependencies
# Installs Selenium and WebDriver Manager.
RUN pip install -r requirements.txt

# Copy the main application code
COPY app.py ${LAMBDA_TASK_ROOT}

# 6. Set the Container Entrypoint
# Point to the function in app.py. 
# Note: For local testing with 'docker run', we might override this, 
# but this is the default for AWS Lambda.
CMD [ "app.take_screenshot" ]