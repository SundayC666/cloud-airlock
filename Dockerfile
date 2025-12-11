# 1. Base Image: Python 3.12 (Amazon Linux 2023)
FROM public.ecr.aws/lambda/python:3.12

# 2. Install Dependencies
# 注意：我們多裝了 'rpm' 這個工具，因為我們要用它來繞過 dnf
RUN dnf install -y \
    rpm \
    atk cups-libs gtk3 libXcomposite libXcursor libXdamage libXext libXi libXtst \
    pango alsa-lib tar gzip unzip nss nss-util nspr mesa-libgbm \
    libXrandr libXScrnSaver libdrm libxkbcommon xdg-utils iputils \
    liberation-fonts liberation-serif-fonts liberation-sans-fonts liberation-mono-fonts \
    vulkan-loader wget

# 3. Download and Install Chrome (Force Install)
# 我們改用 rpm -ivh (Install Verbose Hash)
# 這會繞過 dnf 的路徑檢查 Bug
RUN cd /tmp && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm && \
    rpm -ivh google-chrome-stable_current_x86_64.rpm && \
    rm google-chrome-stable_current_x86_64.rpm

# 4. Copy Project Files
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 5. Install Python Dependencies
RUN pip install -r requirements.txt

# Copy app code
COPY app.py ${LAMBDA_TASK_ROOT}

# 6. Entrypoint
CMD [ "app.handler" ]