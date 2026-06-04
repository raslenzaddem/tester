Global environment requiurements:
- python version mentionned in the yaml file for both models: 3.14.3 for arabic and 3.11 for english and french 
- Python 3.14.3 was used as the global python interpreter
- ffmpeg and espeak-ng shall be configured as well

# TTS Service – AI Backend for Text-to-Speech

This service provides a unified HTTP API for text-to-speech synthesis using multiple TTS models (Kokoro, Mixer80+Vocos). It manages model lifecycles, handles language routing, and streams audio responses.

## Architecture Overview

The service consists of three main components:
                    ┌─────────────────────────────────────────────────────────────────┐
                    │ FastAPI Service                                                 │
                    │ - Receives POST /synthesize requests                            │
                    │ - Routes by language                                            │
                    │ - Returns audio as StreamingResponse                            │
                    └───────────────────────────────┬─────────────────────────────────┘
                                                    │
                                                    ▼
                    ┌─────────────────────────────────────────────────────────────────┐
                    │ ModelRegistry                                                   │
                    │ - Starts persistent subprocesses per model at startup           │
                    │ - Maps language → model process                                 │
                    │ - Graceful shutdown                                             │
                    └───────────────────────────────┬─────────────────────────────────┘
                                                    │
                                                    ▼ (IPC via stdin/stdout)
                    ┌─────────────────────────────────────────────────────────────────┐
                    │ Model Process                                                   │
                    │ - Loads ONNX models (text→mel, vocoder, vowelizers) once        │
                    │ - Reads JSON commands, writes binary audio                      │
                    │ - Runs forever until "shutdown" command                         │
                    └─────────────────────────────────────────────────────────────────┘

                    
## Model Configuration (models_config.yaml)

Each model is defined with its own virtual environment, dependencies, and runtime script.

```yaml
models:
  model_dir: "tts_models"
  venv_script_dir: "Scripts"
  venv_bin_dir: "bin"
  interpreter_name: "python"
  interpreter_exe: "python.exe"

kokoro_en_fr:
  model_name: "kokoro_en_fr"
  env_name: "kokoroEnv_3_11"
  python_version: "3.11"
  lang: ["en", "fr"]
  create_venv:
    windows: "py -3.11 -m venv"
    linux: "python3.11 -m venv"
  setup:
    windows:
      - "{venv_python_exe} -m pip install -r requirements.txt"
  run:
    script: "kokoro_service.py"

Mixer80Vocos_ar:
  model_name: "Mixer80Vocos_ar"
  env_name: "Mixer80VocosEnv_ar_3_12"
  python_version: "3.12"
  lang: ["ar"]
  create_venv:
    windows: "py -3.12 -m venv"
  setup:
    windows:
      - "{venv_python_exe} -m pip install -r requirements.txt"
  run:
    script: "mixer80Vocos_main.py"

# Communication Protocol (Model ↔ Dispatcher)
The model process communicates via stdin/stdout using a simple line‑based JSON protocol.

Request (dispatcher → model)
{"action": "synthesize", "text": "...", "language": "ar", "voice": "optional"}\n

Response (model → dispatcher)
Success case:


Metadata line: {"status":"success","audio_length":12345}\n

Binary audio data (exactly audio_length bytes)

Error case:

Metadata line: {"status":"error","error":"reason"}\n

No audio data follows.

Initialisation:

On startup, model must send {"status":"init"}\n to signal readiness.

Setup & Installation
Prerequisites
Python 3.11/3.12 (match model requirements)

ffmpeg in PATH (for MP3 conversion)

ONNX Runtime (onnxruntime) and other dependencies listed in each model's requirements.txt
