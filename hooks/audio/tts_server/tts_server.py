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
import argparse
import json

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
    parser = argparse.ArgumentParser(description="Qwen3-TTS server and one-shot generator")
    parser.add_argument("--oneshot", action="store_true", help="Generate once and exit")
    parser.add_argument("--text", default="", help="Text to synthesize")
    parser.add_argument("--output", default="output.mp3", help="Output audio file path")
    parser.add_argument("--speaker", default="Ryan", help="Speaker name")
    parser.add_argument("--instruct", default="", help="Instruction prompt")
    parser.add_argument("--language", default="Auto", help="Language")
    parser.add_argument("--host", default="127.0.0.1", help="Server bind host")
    parser.add_argument("--port", type=int, default=7865, help="Server bind port")
    args = parser.parse_args()

    if args.oneshot:
        if not args.text:
            print(json.dumps({"error": "text is required"}))
            sys.exit(1)

        start = time.time()
        results = list(
            MODEL.generate_custom_voice(
                text=args.text,
                language=args.language,
                speaker=args.speaker,
                instruct=args.instruct,
                verbose=False,
            )
        )
        audio = results[0].audio
        sf.write(args.output, np.array(audio), MODEL.sample_rate)
        elapsed_ms = int((time.time() - start) * 1000)
        print(json.dumps({"output": args.output, "tts_ms": elapsed_ms}))
        sys.exit(0)

    app.run(host=args.host, port=args.port)
