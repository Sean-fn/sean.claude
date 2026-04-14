FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    libsndfile1 \
    sox \
    libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

COPY tts_server_linux.py /app/tts_server_linux.py

# Resolve everything in one pass so pip cannot upgrade torch to a cu130 build
# from PyPI when installing qwen-tts and its transitive deps.
RUN pip3 install --no-cache-dir --break-system-packages \
    --index-url https://download.pytorch.org/whl/cu126 \
    --extra-index-url https://pypi.org/simple \
    torch torchaudio qwen-tts flask numpy soundfile

EXPOSE 7865

CMD ["python3", "tts_server_linux.py", "--host", "0.0.0.0", "--port", "7865"]
