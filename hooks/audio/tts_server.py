#!/usr/bin/env python3
"""Persistent TTS server that keeps the Qwen3-TTS model loaded in memory.

Usage:
    # Start server:
    uv run tts_server.py

    # Generate audio:
    curl -s 'http://localhost:7865/speak?text=Hello+world&output=/tmp/test.mp3'
    curl -s -G http://localhost:7865/speak --data-urlencode "text=Hey, come back" \
         --data-urlencode "output=/tmp/out.mp3" --data-urlencode "instruct=speak clearly"
"""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "transformers>=5.0.0rc1",
#     "mlx-audio @ git+https://github.com/Blaizzy/mlx-audio.git",
#     "flask",
#     "numpy",
#     "soundfile",
# ]
# ///
import sys
import time

import numpy as np
import soundfile as sf
from flask import Flask, request, jsonify
from mlx_audio.tts.utils import load_model

app = Flask(__name__)

print("Loading Qwen3-TTS 0.6B model...", file=sys.stderr)
start = time.time()
MODEL = load_model("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
print(f"Model loaded in {time.time() - start:.1f}s", file=sys.stderr)


@app.route("/speak", methods=["GET", "POST"])
def speak():
    if request.method == "POST":
        data = request.json or {}
    else:
        data = request.args

    text = data.get("text", "")
    output = data.get("output", "output.mp3")
    speaker = data.get("speaker", "Ryan")
    instruct = data.get("instruct", "")
    language = data.get("language", "Auto")

    if not text:
        return jsonify({"error": "text is required"}), 400

    start = time.time()
    results = list(
        MODEL.generate_custom_voice(
            text=text,
            language=language,
            speaker=speaker,
            instruct=instruct,
            verbose=False,
        )
    )
    audio = results[0].audio
    sf.write(output, np.array(audio), MODEL.sample_rate)
    elapsed_ms = int((time.time() - start) * 1000)

    return jsonify({"output": output, "tts_ms": elapsed_ms})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7865)
