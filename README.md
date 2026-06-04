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
 ┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. python dispatcher.py serve --port 8000                                                 │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. The dispatcher detects the command "serve" and parses arguments (host, port).          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. The dispatcher delegates the responsibility to the server component: start_server(...) │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. The server component loads the configuration from the YAML file via load_config().     │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. The server component creates a TTSService instance, which sets up FastAPI with lifespan│
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 6. The TTSService instance sets up routes and registers the "/synthesize" endpoint.       │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 7. uvicorn.run() starts the ASGI (Asynchronous Server Gateway Interface) server.          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 8. The TTSService instance instantiates the ModelRegistry class, which handles creation,  │
│    shutdown, and registration of ModelProcess instances for each model defined in the     │
│    YAML file. The start_all() method checks if each model's environment is properly built │
│    and invokes the corresponding start() method for every ModelProcess instance. It       │
│    finally outputs the success rate of loaded models and lists the models by name.        │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 9. Each ModelProcess instance defines methods to start, stop, and request audio generation│
│    from the associated model subprocess. The established IPC (Inter‑Process Communication)│
│    is ensured via stdin and stdout pipes. Each model subprocess is launched with its own  │
│    virtual environment (pointing to the corresponding python and pip executables). Once   │
│    the connection is established, the server stays idle for all models to load properly.  │
│    The server keeps running even if all models fail to load, but it will not accept any   │
│    HTTP request that requires a model which failed to load.                               │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│10. Each created model subprocess has its own defined lifecycle. Once started, it loads    │
│    the corresponding AI model and pipeline and signals readiness to its ModelProcess      │
│    instance via stdout. It then passively waits for TTS requests in a blocked while loop. │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│11. Once a ModelProcess instance receives a confirmation that the corresponding model is   │
│    loaded, the FastAPI server starts accepting HTTP RESTful requests for that specific    │
│    model.                                                                                 │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│12. When the server receives a TTS request, it delegates the responsibility to the         │
│    corresponding subprocess dynamically based on the requested language. It waits for a   │
│    response for both success and error scenarios.                                         │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│13. The passively awaiting AI model subprocess (e.g., kokoro_en_fr for English/French or   │
│    Mixer80Vocos_ar for Arabic) receives via its stdin the TTS request as a UTF‑8 encoded  │
│    JSON document, decodes it, feeds the text to its pipeline, and generates the           │
│    corresponding MP3 audio bytes.                                                         │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│14. The AI subprocess sends the metadata of the generated MP3 audio bytes as a UTF‑8       │
│    encoded JSON document, followed by the raw audio bytes, via its stdout. The subprocess │
│    then passively waits for the next request.                                             │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│15. The corresponding ModelProcess receives the metadata, decodes it back into a JSON      │
│    object to obtain the length of the expected bytes (in case of success) or catches the  │
│    corresponding error to raise an HTTPException. In case of success, it receives the     │
│    bytes and streams them back via an HTTP response.                                      │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│16. The FastAPI server receives a shutdown signal (Ctrl+C). It kills all subprocesses      │
│    gracefully before terminating the application.                                         │
└───────────────────────────────────────────────────────────────────────────────────────────┘
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
The model process communicates via stdin/stdout using a simple line‑based JSON protocol. At the sending part, the JSON document is encoded into UTF-8 bytes.
The process is reversed at the recieving end. The JSON document must be followed by "\n" to used as line separator essential for IPC exchange. 

## Initialisation (model subprocess → ModelProcess instance ):
On startup, model must send {"status":"init"}\n to signal readiness.

## Request (ModelProcess instance → model subprocess):
{"action": "synthesize", "text": "...", "language": "ar"}\n

## Response (model subprocess → ModelProcess instance):
- Success case:

Metadata line: {"status":"success","audio_length":12345}\n
Binary audio data (exactly audio_length bytes)

- Error case:

Metadata line: {"status":"error","error":"reason"}\n
No audio data follows.

## Summary 
| Direction                                         | Data type    | Format        | Encoding       |
|---------------------------------------------------|--------------|---------------|----------------|
| ModelProcess instance  -> model subprocess        | Command      | JSON + "\n"   | UTF-8 encoding |
| model subprocess       ->  ModelProcess instance  | Metadata     | JSON + "\n"   | UTF-8 encoding |
| model subprocess       ->  ModelProcess instance  | Metadata     | Audio         | Raw bytes      |

PS: At the models subprocess level ran in persistant mode (in contrast to run-once mode), stdout messages (e.g print functions ) are redirected to stderr and error cases were handled to be sent as an UTF-8 encode JSON files to be dealt with at the reciever end (ModelProcess instances).

# TTS Models Used in the Project
This project integrates two main families of TTS models: Kokoro (for English and French) and MixerTTS + Vocos (for Arabic). Both are selected for their lightweight design, CPU‑compatibility, and permissive licenses (MIT/Apache 2.0).

## Selection Criteria
All chosen models shall respect the following constraints:

- Lightweight (low RAM consumption)
- CPU‑only (no CUDA/GPU required)
- Real‑time capable (response time < 2 seconds)
- Commercial‑friendly licence (MIT, Apache 2.0)

## Kokoro (English & French)
Kokoro is based on the KPipeline architecture. The heavy neural network (KModel) is loaded only once and shared across language‑specific pipelines.
```
# Shared neural model
shared_model = KModel(repo_id='hexgrad/Kokoro-82M')

# Lightweight text processors (one per language)
pipeline_en = KPipeline(lang_code='a', model=shared_model)   # American English
pipeline_fr = KPipeline(lang_code='f', model=shared_model)   # French
```

Model size: 82M parameters (neural net) + small language‑specific rules.
Output quality: excellent for English and French.

## Mixer80Vocos: Mixer80  + Vocos (vovos22) (Arabic)
For Arabic, we benchmarked three text‑to‑mel models (FastPitch, Mixer128, Mixer80) and three vocoders (HiFi‑GAN, Vocos22, Vocos44).

### What is a Mel‑spectrogram?
Human hearing perceives frequency logarithmically (pitch is not linear). A mel‑spectrogram converts linear frequency bins into mel‑scale bins, mimicking human ear sensitivity.
The conversion formula is:

A mel‑spectrogram with 80 bins means the frequency axis is divided into 80 mel‑scale bands. This is the standard input for many TTS vocoders (e.g., HiFi‑GAN, Vocos). The number of bins determines the frequency resolution; 80 bins is a good trade‑off between detail and computational cost.

|Model	    |Type	    |#Parameters|	Output              |
|-----------|-----------|-----------|-----------------------|
|FastPitch	|Text → Mel	|46.3 M	Mel |(80 bins, 22.05 kHz)   |
|Mixer128	|Text → Mel	|2.9 M	Mel |(80 bins, 22.05 kHz)   |
|Mixer80	|Text → Mel	|2.9 M	Mel |(80 bins, 22.05 kHz)   |
|HiFi‑GAN	|Mel → Wave	|13.9 M	    |Waveform (22.05 kHz)   |
|Vocos22	|Mel → Wave	|13.4 M	    |Waveform (22.05 kHz)   |
|Vocos44	|Mel → Wave	|14.0 M	    |Waveform (44.1 kHz)    |

Note: HiFi‑GAN and Vocos22/44 artificially extend the audio bandwidth to 11 kHz (HiFi‑GAN) or 22 kHz (Vocos44). However, the true effective bandwidth is limited by the mel‑spectrogram’s frequency range (around 8 kHz for the 22.05 kHz models).

### Benchmark Results (Arabic, diacritized input)
We measured inference time on CPU (no GPU). The key observations:
- Without diacritics (plain Arabic text), all models produce bad pronunciation (rejected).
- FastPitch degrades after 33 seconds of audio.
- Remaining valid combinations were evaluated for quality and response time.

| Text→Mel  | Vocoder   | Diacritics | Time (s) | Comment                                           |
|-----------|-----------|------------|----------|---------------------------------------------------|
| fastpitch | hifigan   | Y          | 16.59    | degrades after 33s                                |
| fastpitch | hifigan   | N          | 13.83    | bad                                               |
| fastpitch | vocos     | Y          | 21.00    | slightly better                                   |
| fastpitch | vocos     | N          | 2.70     | bad                                               |
| fastpitch | vocos44   | Y          | 34.90    | slightly better, small mistakes                   |
| mixer128  | hifigan   | Y          | 25.00    | good, lacks stops at “.”                          |
| mixer128  | hifigan   | N          | 11.38    | bad                                               |
| mixer128  | vocos     | Y          | 1.35     | overall good                                      |
| mixer128  | vocos     | N          | 1.19     | bad                                               |
| mixer128  | vocos44   | Y          | 1.60     | better                                            |
| mixer128  | vocos44   | N          | 1.33     | bad                                               |
| mixer80   | hifigan   | Y          | 20.00    | better                                            |
| mixer80   | hifigan   | N          | 11.64    | bad                                               |
| mixer80   | vocos     | Y          | 1.38     | best balance                                      |
| mixer80   | vocos     | N          | 1.16     | bad                                               |
| mixer80   | vocos44   | Y          | 1.48     | also good but slower than vocos22                 |
| mixer80   | vocos44   | N          | 1.33     | bad                                               |

Conclusion: The combination mixer80 + vocos22 gives the best practical result:

- Total parameters: 2.9 M (mixer80) + 13.4 M (vocos22) = 16.3 M
- Response time: ~1.4 seconds for a typical sentence
- Quality: clear, natural, no degradation over long text

### Diacritization (Tashkeel) for Arabic
Several diacritization models were tested:

- shakkala, shakkelha, catt‑eo – initial candidates. catt‑eo was selected for its audible correctness (better than visible diacritic anomalies).
- SILMA – good state‑of‑the‑art but slow for real‑time CPU usage.
- Fine‑Tashkeel (ByT5) – excellent accuracy, but:
    - Too slow for real‑time CPU.
    - Optimisations (caching, static KV, ONNX export) either worsened latency or were incompatible due to the model’s age and reliance on a GPU.

Decision: Diacritization is delegated to a separate AI model (outside this TTS service). The current pipeline expects already diacritized Arabic text.

### Final Pipeline (Diacritization omitted)

Mixer80Vocos:  Mixer80 + Vocos22 is the primary engine for Arabic TTS, while Kokoro handles English and French. Both are integrated into the unified dispatcher framework.
```
1. Arabic text (diacritized)
                │
                ▼
┌─────────────────────────────────┐
│ 2. Phonemizer (internal)        │
│              → Phonemes         │
└─────────────────────────────────┘
                │
                ▼
3. Tokenizer → token IDs
                │
                ▼
┌─────────────────────────────────┐
│ 4. Mixer80 (Text → Mel)         │
│   → Mel spectrogram (80 bins)   │
└─────────────────────────────────┘
                │
                ▼
5. Vocos22 (Mel → Wave) → waveform (22.05 kHz)
                │
                ▼
┌─────────────────────────────────┐
│ 6. WAV to MP3 converter         │
│     → MP3 audio bytes           │
└─────────────────────────────────┘
```


