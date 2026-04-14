FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps for soundfile backend.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY tts_server_linux.py /app/tts_server_linux.py

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    qwen-tts \
    torch \
    flask \
    numpy \
    soundfile

EXPOSE 7865

CMD ["python", "tts_server_linux.py", "--host", "0.0.0.0", "--port", "7865"]