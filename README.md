Global environment requiurements:
- python version mentionned in the yaml file for both models: 3.14.3 for arabic and 3.11 for english and french 
- Python 3.14.3 was used as the global python interpreter
- ffmpeg and espeak-ng shall be configured as well

# TTS Service – AI Backend for Text-to-Speech

This service provides a unified HTTP REST API for text-to-speech synthesis using multiple TTS models (Kokoro, Mixer80+Vocos). It manages model lifecycles, handles language routing, and streams audio responses.

## Architecture Overview

A dedicated framework was implemented to take into account these considerations:
- The scalability of the used models: To make it easy to test, run and integrate each model within the framework
- The specific dependencies and requirements of each model: Each model was wrapped within its own virtual environment (venv). A proper isolation is necessary. This isolation take into consideration the specific Python version that was used to implement the model, the plateform specific commands (Windows and Linux OS) and the relates dependencies (requirements.txt files)
- The separation of concerns: The modularity of the dispatcher and the isolation of each model to delegate each part its responsibility and to facilitate debugging and future improvements

The following Figure summarizes the architecture of the framework
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DISPATCHER (orchestrator)                           │
│                                                                             │
│  CLI commands:                                                              │
│  • build-all              – create venvs & install dependencies             │
│  • run-model <name>       – one‑shot inference (subprocess)                 │
│  • run-all-models         – sequential inference for all models             │
│  • serve                  – start FastAPI server (persistent mode)          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ (depending on command)
                                        │
            ┌───────────────────────────┬─────────────────────┐
            │                           │                     │
            ▼                           ▼                     │             
    ┌───────────────────┐     ┌─────────────────────────┐     │
    │   build-all       │     │   run-model             │     │
    │                   │     │   run-all-models        │     │
    │  • create venv    │     │                         │     │
    │  • activate       │     │  • launch model once    │     │
    │  • pip install    │     │  • capture audio        │     │
    │                   │     │  • save or return       │     │
    └───────────────────┘     └─────────────────────────┘     │
                                                              │ 
                                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                         │  
    │   ┌─────────────────────────────────────────────────────────────────┐   │ 
    │   │ FastAPI Service                                                 │   │
    │   │ - Receives POST /synthesize requests                            │   │
    │   │ - Routes by language                                            │   │
    │   │ - Returns audio as StreamingResponse                            │   │
    │   └───────────────────────────────┬─────────────────────────────────┘   │
    │                                   │                                     │
    │                                   ▼                                     │
    │    ┌─────────────────────────────────────────────────────────────────┐  │
    │    │ ModelRegistry                                                   │  │
    │    │ - Starts persistent subprocesses per model at startup           │  │
    │    │ - Maps language → model process                                 │  │
    │    │ - Graceful shutdown                                             │  │
    │    └───────────────────────────────┬─────────────────────────────────┘  │
    │                                    │                                    │
    │                                    ▼ (IPC via stdin/stdout)             │
    │    ┌─────────────────────────────────────────────────────────────────┐  │
    │    │ Model Process                                                   │  │ 
    │    │ - Loads ONNX models (text→mel, vocoder, vowelizers) once        │  │
    │    │ - Reads JSON commands, writes binary audio                      │  │
    │    │ - Runs forever until "shutdown" command                         │  │
    │    └─────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────┘
```

The following figure illustrates the general execution flow in the run-as-a-server scenario:
```
1. python dispatcher.py serve --port 8000
                   │
                   ▼
2. The dispatcher detects the command "serve" and parses arguments (host, port)
                   │
                   ▼
3. The dispatcher delegates the responsability to the server component: start_server(...)
                   │
                   ▼
4. The server componenet loads the configuration from the yaml file via load_config()
                   │
                   ▼
5. The server component creates a TTSService instance creating FastAPI with lifespan
                   │
                   ▼
6. The TTSService instance setup routes and registers the "/synthesize" endpoint
                   │
                   ▼
7. uvicorn.run() starts the ASGI (Asynchronous Server Gateway Interface) server 
                   │
                   ▼
8. The TTSService instance instantiates ModelRegistry class that handles (create/shutdown/register) ModelProcess instances: models are defined in the config.yaml file.
The start_all method of ModelRegistry class checks if models environment is properly built and invoque the correspoding start() method of the every ModelProcess instance.
It finally outputs the success rate of loaded models and list the models by name. 
                   │
                   ▼
9. Each ModelProcess instance defines methods to start, stop, request a audio generation of the associated model subprocess.
The established IPC (Inter-Process Communication) is ensured via stdin and stdout pipes and each model subprocess is launched with the corresponding venv (pointing to the corresponding python and pip executable).
Once the connection is established, the server stays idle for all models to load properly. The server keeps running even if all models fail to load but would not accept any HTTP requests if that request requires a model that failed to load.
                   │
                   ▼
10. Each created model subprocess has its own defined lifecycle.
Once started, it loads the corresponding AI model and pipeline and signals that to the corresponding Model Process instance via its stdout and passively waits for tts-requests.
This is ensured by a blocked while loop.
                   │
                   ▼
11. Once a ModelProcess instance recieve a confirmation that the corresponding model is loaded, the FastAPI start accepting HTTP RESTful request for that specific model.
                   │
                   ▼
12. Once the Server recieves a tts request, it delegates the responsibility to the corresponding subprocess dynamically based on the requested language.
IT waits for a response for both success and error scenarios
                   │
                   ▼
13. The passively awaiting AI model subprocess (Kokoro_en_fr for english and french and Mixer80Vocos_ar) recieves via its stdin the tts request in the form of a UTF-8-encoded json document, decode it, feed the corresponding text to its pipeline and generate the corresponding mp3 audio Bytes
                   │
                   ▼
14. The Corresponding AI subprocess sends the meta data of the generated mp3 audio bytes in the form of UTF-8 encode json document then the raw audio bytes via its stdout.
The subprocess wait passivey for the next request.
                   │
                   ▼
15. The corresponding ModelProcess recieves the metadata, decode it back int json file to get the length of the expected bytes in case of success or catch the corresponsing error otherwise to raise HTTPException.
In case of success, it recieves the bytes and stream them back Via HTTPResponse.
                   │
                   ▼
16. The FASTApi server recieves a shutdown signal (CTR+C) and kill all subprocesses gracefully before terminating the application.

```
                    
## Model Configuration (models_config.yaml)

Each model is defined with its own virtual environment, dependencies, and runtime script. The general schema of the configuration yaml file is presented as follows:

```yaml
# ----------------------------------------------------------------------
# Global metadata (shared by all models)
# ----------------------------------------------------------------------
models:                       # <-- mandatory top-level key
  model_dir: "string"         # path to the directory containing all model folders
  venv_script_dir: "string"   # name of the Scripts folder inside a venv (Windows)
  venv_bin_dir: "string"      # name of the bin folder inside a venv (Linux/macOS)
  interpreter_name: "string"  # Python interpreter name on Unix (e.g., "python")
  interpreter_exe: "string"   # Python interpreter name on Windows (e.g., "python.exe")

# ----------------------------------------------------------------------
# Global metadata (shared by all models)
# ----------------------------------------------------------------------
models:                       # <-- mandatory top-level key
  model_dir: "string"         # path to the directory containing all model folders
  venv_script_dir: "string"   # name of the Scripts folder inside a venv (Windows)
  venv_bin_dir: "string"      # name of the bin folder inside a venv (Linux/macOS)
  interpreter_name: "string"  # Python interpreter name on Unix (e.g., "python")
  interpreter_exe: "string"   # Python interpreter name on Windows (e.g., "python.exe")

# ----------------------------------------------------------------------
# Model definitions (each model is a separate mapping)
# ----------------------------------------------------------------------
<model_identifier>:           # unique identifier (e.g., "kokoro_en_fr")
  # --- Identity ---
  model_name: "string"        # display name (can be same as identifier)
  env_name: "string"          # name of the virtual environment folder
  python_version: "string"    # Python version to use (e.g., "3.11", "3.12")
  lang: ["string", ...]       # list of supported language codes (e.g., ["en","fr"])

  # --- Virtual environment creation ---
  create_venv:                # command to create the venv (platform‑specific)
    windows: "string"         # command for Windows (e.g., "py -3.11 -m venv")
    linux: "string"           # command for Linux (e.g., "python3.11 -m venv")

  # --- Post‑creation setup ---
  setup:                      # list of commands to run inside the model directory
    windows: ["string", ...]  # commands for Windows (use {venv_python_exe} placeholder)
    linux: ["string", ...]    # commands for Linux

  # --- Runtime ---
  run:
    script: "string"          # Python script to execute (must support --persistent flag)
```

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
