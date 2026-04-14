#!/usr/bin/env python3
"""Persistent TTS server for Linux with Qwen3-TTS loaded in memory.

Usage:
    # Start server:
    uv run tts_server_linux.py

    # Generate audio:
    curl -s 'http://localhost:7865/speak?text=Hello+world&output=/tmp/test.mp3'
    curl -s -G http://localhost:7865/speak --data-urlencode "text=Hey, come back" \
         --data-urlencode "output=/tmp/out.mp3" --data-urlencode "instruct=speak clearly"
"""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "qwen-tts",
#     "torch",
#     "flask",
#     "numpy",
#     "soundfile",
# ]
# ///
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from flask import Flask, jsonify, request
from qwen_tts import Qwen3TTSModel

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

app = Flask(__name__)
MODEL: Qwen3TTSModel | None = None
MODEL_NAME = DEFAULT_MODEL
MODEL_DEVICE = "cpu"


def _resolve_device(device_arg: str) -> str:
    requested = device_arg.strip().lower()
    if requested == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"

    if requested.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA device requested but no CUDA runtime is available")

    return requested


def _resolve_dtype(device: str) -> torch.dtype:
    return torch.bfloat16 if device.startswith("cuda") else torch.float32


def _load_model(model_name: str, device: str) -> Qwen3TTSModel:
    kwargs: dict[str, Any] = {
        "device_map": device,
        "dtype": _resolve_dtype(device),
    }
    if device.startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    try:
        return Qwen3TTSModel.from_pretrained(model_name, **kwargs)
    except Exception as exc:
        # FlashAttention2 is optional; retry with standard attention when absent.
        if kwargs.get("attn_implementation"):
            print(
                f"FlashAttention2 unavailable ({exc!s}); retrying without it...",
                file=sys.stderr,
            )
            kwargs.pop("attn_implementation", None)
            return Qwen3TTSModel.from_pretrained(model_name, **kwargs)
        raise


def _write_audio(output_path: str, audio: np.ndarray, sample_rate: int) -> None:
    output_file = Path(output_path).expanduser()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_file), audio, sample_rate)


def _synthesize(text: str, output: str, speaker: str, instruct: str, language: str) -> int:
    if MODEL is None:
        raise RuntimeError("Model is not loaded")

    start = time.time()
    wavs, sample_rate = MODEL.generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct=instruct,
    )
    if not wavs:
        raise RuntimeError("Model returned no audio output")

    _write_audio(output, np.asarray(wavs[0]), sample_rate)
    return int((time.time() - start) * 1000)


def _request_data() -> dict[str, Any]:
    if request.method == "POST":
        if request.is_json:
            return request.get_json(silent=True) or {}
        return request.form.to_dict()

    return request.args.to_dict()


def _parse_fields(data: dict[str, Any]) -> tuple[str, str, str, str, str]:
    text = str(data.get("text", "")).strip()
    output = str(data.get("output", "output.mp3"))
    speaker = str(data.get("speaker", "Ryan"))
    instruct = str(data.get("instruct", ""))
    language = str(data.get("language", "Auto"))
    return text, output, speaker, instruct, language


@app.route("/speak", methods=["GET", "POST"])
def speak():
    text, output, speaker, instruct, language = _parse_fields(_request_data())
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        elapsed_ms = _synthesize(
            text=text,
            output=output,
            speaker=speaker,
            instruct=instruct,
            language=language,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"output": output, "tts_ms": elapsed_ms})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": MODEL_NAME, "device": MODEL_DEVICE})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Linux Qwen3-TTS server and one-shot generator"
    )
    parser.add_argument("--oneshot", action="store_true", help="Generate once and exit")
    parser.add_argument("--text", default="", help="Text to synthesize")
    parser.add_argument("--output", default="output.mp3", help="Output audio file path")
    parser.add_argument("--speaker", default="Ryan", help="Speaker name")
    parser.add_argument("--instruct", default="", help="Instruction prompt")
    parser.add_argument("--language", default="Auto", help="Language")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID or local path")
    parser.add_argument(
        "--device",
        default="auto",
        help="Device to run on: auto, cpu, cuda:0, ...",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server bind host")
    parser.add_argument("--port", type=int, default=7865, help="Server bind port")
    args = parser.parse_args()

    MODEL_NAME = args.model
    MODEL_DEVICE = _resolve_device(args.device)

    print(f"Loading {MODEL_NAME} on {MODEL_DEVICE}...", file=sys.stderr)
    load_start = time.time()
    MODEL = _load_model(MODEL_NAME, MODEL_DEVICE)
    print(f"Model loaded in {time.time() - load_start:.1f}s", file=sys.stderr)

    if args.oneshot:
        if not args.text:
            print(json.dumps({"error": "text is required"}))
            sys.exit(1)

        try:
            elapsed_ms = _synthesize(
                text=args.text,
                output=args.output,
                speaker=args.speaker,
                instruct=args.instruct,
                language=args.language,
            )
        except Exception as exc:
            print(json.dumps({"error": str(exc)}))
            sys.exit(1)

        print(json.dumps({"output": args.output, "tts_ms": elapsed_ms}))
        sys.exit(0)

    app.run(host=args.host, port=args.port)