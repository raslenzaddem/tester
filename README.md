

# TTS Service – AI Backend for Text-to-Speech:

This service provides a unified HTTP REST API for text-to-speech synthesis using multiple TTS models (Kokoro, Mixer80+Vocos). It manages model lifecycles, handles language routing, and streams audio responses.
This service provides a framewok for building, running AI models in run-once and server/persistent mode.

## Table of Contents

- [1. Service Overall Dependencies](#1-service-overall-dependencies)
- [2.Development and Testing Notes](#2-development-and-testing-notes)
- [3. Architecture Overview and Consideration](#3-architecture-overview-and-consideration)
  - [3.1 Architecture Consideration](#31-architecture-consideration)
  - [3.2Architecture Overview](#32-architecture-overview)
- [4. REST HTTP Protocol (TTS Service ↔ Client)](#4-rest-http-protocol-tts-service--client)
  - [4.1 Endpoint](#41-endpoint)
  - [4.2 Request Format](#42-request-format)
- [5. Model Configuration (models_config.yaml)](#5-model-configuration-models_configyaml)
- [6. Communication Protocol (Model ↔ Dispatcher)](#6-communication-protocol-model--dispatcher)
  - [6.1 Initialisation (model subprocess → ModelProcess instance)](#61-initialisation-model-subprocess--modelprocess-instance)
  - [6.2 Request (ModelProcess instance → model subprocess)](#62-request-modelprocess-instance--model-subprocess)
  - [6.3 Response (model subprocess → ModelProcess instance)](#63-response-model-subprocess--modelprocess-instance)
  - [6.4 Summary](#64-summary)
- [7. TTS Models Used in the Project](#7-tts-models-used-in-the-project)
  - [7.1 Selection Criterion](#71-selection-criterion)
  - [7.2 Kokoro (English & French)](#72-kokoro-english--french)
  - [7.3 Mixer80Vocos: Mixer80 and Vocos (Arabic)](#73-mixer80vocos-mixer80-and-vocos-arabic)
    - [7.3.1 Mel Spectogram Definition](#731-mel-spectogram-definition)
    - [7.3.2 Benchmark Results (Arabic, diacritized input)](#732-benchmark-results-arabic-diacritized-input)
    - [7.3.3 Diacritization (Tashkeel) for Arabic](#733-diacritization-tashkeel-for-arabic)
    - [7.3.4 Final Pipeline](#734-final-pipeline)
- [8 Ressources and References](#8-ressources-and-references)
  - [8.1 kokoro Model](#81-kokoro-model)
  - [8.2 Mixer80Vocos](#82-mixer80vocos)
  - [8.3 catt-eo](#83-catt-eo)
- [9. License & Attribution](#9-license--attribution)

## 1. service overall dependencies:
Global environment requiurements:
- python version mentionned in the yaml file for both models: 3.14.3 for arabic and 3.11 for english and french 
- Python 3.14.3 was used as the global python interpreter 
- ffmpeg and espeak-ng shall be configured as well

For future reference, the benchmarking of mentionned models were done on local machine:
- CPU: 11th Gen Intel(R) Core(TM) i7-11800H @ 2.3GHz
- RAM: 40 GB

PS: To install python3.11 for the kokoro model, run these commands (tested with WSL):
```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```
To verify installation:
```bash
python3.11 --version
```

## 2. Development and testing notes:
- Develoment notes:
    - The following work was firstly developped with VS code within Windows then was tested for LINUX Ubuntu distribution using WSL.
    - At first the models were tested, ran and benchmarked in isolated projects and python venvs, then were tested within the framework (building, run-once mode, persistent/server mode).
    - A general venv was created to wrap the service and configure general requirements as it was either prohibited or risky to do directly within WSl.
    - Postman was used to test the serivce endpoint.
    - For the WINDOWS OS case the tts-service was tested using postman then from the Frontend.
    - For Linux Ubuntu (WSL), it was only tested with Postman.
    - The testing considered requesting the tts service with english, french, and arabic texts. 

- Testing notes:
    - The overall results showcased a response bounded by a maximum response time of 6 seconds for the kokoro model and two seconds of the Mixer80Vocos case.
    - The used models are considered lightweight ins terms of RAM consumption and number of parameters relatively to the current state-of-art and CPU-use-case.
    - The lifecycle defined for persistent/server mode leverage one-time model-loading which optimizes the response time.
    - A possible optimization is localized at the IPC level within the framework. It would consist of defining a set of worker and input/output pipes for parallel requests: the read/write operations with pipes are considered critical sections; such optimization consideration is advised to be delegated as a layer added to the AI model subprocesses.
    

## 3. Architecture Overview and consideration:

### 3.1 Architecture consideration:

A dedicated framework was implemented to take into account these considerations:
- The scalability of the used models: To make it easy to test, run and integrate each model within the framework.
- The isolation of each model to delegate each part its responsibility and to facilitate debugging and future improvements.
  - The specific dependencies and requirements of each model: Each model was wrapped within its own virtual environment (venv). A proper isolation is necessary. This isolation take into consideration the specific Python version that was used to implement the model, the plateform specific commands (Windows and Linux OS) and the related dependencies (requirements.txt files).
- Modularity and separation of concerns:
  - The dispatcher component (dispatcher.py) is the main entry point of the tts-service and defines the proper work flow:
    - building mode (create the corresponding venv and install related dependencies): 
    ```bash
    python dispatcher.py build-all
    ```

    - running a specific model for isolate testing and debugging (model IDs are defined in the config.yaml file) in run-once mode:
    ```bash
    python dispatcher.py run-model <model-name>
    ```

    - running all models sequentially in run-once mode:
    ```bash
    python dispatcher.py run-all-models
    ```

    - running in server mode (persistent mode for AI models) with optional flags:
    ```bash
    python dispatcher.py serve --host <host> --port <port>
    ```

    - PS: server mode uses uvicorn but "--reload" is not configured yet.

  -  The server component (server.py) is delegated the responsability of initializing, launching and handling a FASTapi application:
    - It can only be ran by the dispatcher.
    - It is responsible for handling AI models subprocesses in persistent mode by defining lifecycle handling mechanisms.
    - Each AI model subprocess is handled by its own venv defined in the config.yaml file, built in the model's specific directory.
    - The server component is responsible of channeling the incoming TTS requests to the proper AI model subprocess by language:
      - If the requested language is either french "fr" or english "en", the tts request is delegated to the Kokoro AI model subprocess.
      - If the requested language is arabic "ar" the tts request is delegated to the Mixer80Vocos AI model subprocess.
      - It receives the status (init, success, error) of the each AI model subprocess and acts accordingly.
  
  - Each AI model subprocess is responsible for the TTS conversion of the provided text and the requested language (fr, ar, en):
    - The Kokoro subprocess is responsible for converting either English or French language TTS requests and eventually sends raw MP3 audio bytes.
    - The Mixer80Vocos subprocess is responsible for converting Arabic language TTS requests and eventually sends raw MP3 audio bytes.
    - Each model can be runn directly using its own main function, add "--persistent" flag, to run them in persistent mode. But the corresponsing venv must be activated

### 3.2 Architecture overview:

The following Figure summarizes the architecture of the framework:
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

The following Figure illustrates the general execution flow in the run-as-a-server scenario:
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
│13. The passively waiting AI model subprocess (e.g., kokoro_en_fr for English/French or   │
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
                    
## 4. REST HTTP Protocol (TTS Service ↔ Client):
The TTS service exposes a single HTTP endpoint for speech synthesis. Clients communicate with the service using standard HTTP requests.

### 4.1 Endpoint:
- POST /synthesize
- The service was tested on localhost, port 8000: "http://localhost:8000/synthesize".

### 4.2 Request Format:
- Content-Type: application/json
- Body: JSON object with the following schema:
```json
{
  "text": "string",
  "language": "string"
}
```

| Field    | Type    | Required | Description                                                                  |
|----------|---------|----------|------------------------------------------------------------------------------|
| text     | string  | Yes      | The text to be synthesized. Must be written in the language specified below. |
| language | string  | Yes      | Language code for the input text. Supported values: "en", "fr", "ar".        |

- Language codes:
  - "en" for English.
  - "fr" for French.
  - "ar" for Arabic.

These are samples of the tested requests:
- French (fr):
```
{
    "text": "Notre plus grande peur n'est pas de manquer de force. Notre plus grande peur est d'être puissants au-delà de toute mesure.",
    "language": "fr"
}
```

- Arabic (ar) - diacritized arabic text:
```
{
   "text":  " هُوَ دُرَّةُ التُّرَاثِ الْعَالَمِيِّ. وَوَاحِدٌ مِنْ أَفْضَلِ كُتُبِ الْأَدَبِ الَّتِي تَخَطَّتْ أُطُرَ الْمَكَانِ وَحُدُودَ الزَّمَانِ، لِتَعِيشَ بَيْنَنَا حَتَّى الْيَوْمِ .",
   "language": "ar"
}
```

- English (en)
```
{
    "text": "Our deepest fear is not that we are inadequate. Our deepest fear is that we are powerful beyond measure.",
    "language": "en"
}
```

## 5. Model Configuration (models_config.yaml):

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

## 6. Communication Protocol (Model ↔ Dispatcher):
The model process communicates via stdin/stdout using a simple line‑based JSON protocol. At the sending part, the JSON document is encoded into UTF-8 bytes.
The process is reversed at the recieving end. The JSON document must be followed by "\n" to be used as line separator essential for IPC exchange. 

### 6.1 Initialisation (model subprocess → ModelProcess instance):
```
{"status":"init"}\n
```
to signal readiness.

### 6.2 Request (ModelProcess instance → model subprocess):
```
{"action": "synthesize", "text": "...", "language": "ar"}\n
```
### 6.3 Response (model subprocess → ModelProcess instance):
- Success case:

Metadata line: 
```
{"status":"success","audio_length":12345}\n
```

Binary audio data (exactly audio_length bytes)

- Error case:

Metadata line:
```
{"status":"error","error":"reason"}\n
```

No audio data follows.

### 6.4 Summary:
| Direction                                         | Data type    | Format        | Encoding       |
|---------------------------------------------------|--------------|---------------|----------------|
| ModelProcess instance  -> model subprocess        | Command      | JSON + "\n"   | UTF-8 encoding |
| model subprocess       ->  ModelProcess instance  | Metadata     | JSON + "\n"   | UTF-8 encoding |
| model subprocess       ->  ModelProcess instance  | Metadata     | Audio         | Raw bytes      |

PS: At the model subprocess level ran in persistent mode (in contrast to run-once mode), stdout messages (e.g print functions ) are redirected to stderr and error cases were handled to be sent as an UTF-8 encode JSON files to be dealt with at the reciever end (ModelProcess instances).

## 7. TTS Models Used in the Project:
This project integrates two main families of TTS models: Kokoro (for English and French) and MixerTTS + Vocos (for Arabic). Both are selected for their lightweight design, CPU‑compatibility, and permissive licenses (MIT/Apache 2.0).

### 7.1 Selection Criterion:
All chosen models shall respect the following constraints:

- Lightweight (low RAM consumption)
- CPU‑only (no CUDA/GPU required)
- Real‑time capable (response time < 2 seconds)
- Commercial‑friendly licence (MIT, Apache 2.0)

### 7.2 Kokoro (English & French):
- Kokoro is based on the KPipeline architecture. The heavy neural network (KModel) is loaded only once and shared across language‑specific pipelines.
```python
# Shared neural model
shared_model = KModel(repo_id='hexgrad/Kokoro-82M')

# Lightweight text processors (one per language)
pipeline_en = KPipeline(lang_code='a', model=shared_model)   # American English
pipeline_fr = KPipeline(lang_code='f', model=shared_model)   # French
```

- Model size: 82M parameters (neural net) + small language‑specific rules.
- Output quality: excellent for English and French. It does not support Arabic.

- This approach optimized the RAM usage of the Kokoro model: The KModel itself is language blind it converts phonemes (vocal/sound units) into wav format (audible sound);
Loading the the KModel twice unecessary.

- For model benchmarking refer/run to the "kokoro_benchmark.py" python script.
- For english language, an american accent was used identified by "af_heart". The model natively offers multiple choices for both american and british accents.
- The only available french voice available for the Kokoro model is refered as "ff_siwis". The voice be indexed but not downloaded. In this case run the "voice_testers.py" python script.
- Refer to the Ressources and References section of this documentation for more information about the model.

### 7.3 Mixer80Vocos: Mixer80 and Vocos (Arabic):
For Arabic, we benchmarked three text‑to‑mel models (FastPitch, Mixer128, Mixer80) and three vocoders (HiFi‑GAN, Vocos22, Vocos44).

#### 7.3.1 Mel Spectogram Definition:
Human hearing perceives frequency logarithmically (pitch is not linear). A mel‑spectrogram converts linear frequency bins into mel‑scale bins, mimicking human ear sensitivity.
The conversion formula is:

$$ 
m = 2595 \cdot \log_{10}\left(1 + \frac{f}{700}\right)
$$

A mel‑spectrogram with 80 bins means the frequency axis is divided into 80 mel‑scale bands. This is the standard input for many TTS vocoders (e.g., HiFi‑GAN, Vocos). The number of bins determines the frequency resolution; 80 bins is a good trade‑off between detail and computational cost.

|Model	    |Type	      |#Parameters|	Output                |
|-----------|-----------|-----------|-----------------------|
|FastPitch	|Text → Mel	|46.3 M	Mel |(80 bins, 22.05 kHz)   |
|Mixer128	  |Text → Mel	|2.9 M	Mel |(80 bins, 22.05 kHz)   |
|Mixer80	  |Text → Mel	|2.9 M	Mel |(80 bins, 22.05 kHz)   |
|HiFi‑GAN  	|Mel → Wave	|13.9 M	    |Waveform (22.05 kHz)   |
|Vocos22  	|Mel → Wave	|13.4 M	    |Waveform (22.05 kHz)   |
|Vocos44  	|Mel → Wave	|14.0 M	    |Waveform (44.1 kHz)    |

Note: HiFi‑GAN and Vocos22/44 artificially extend the audio bandwidth to 11 kHz (HiFi‑GAN) or 22 kHz (Vocos44). However, the true effective bandwidth is limited by the mel‑spectrogram’s frequency range (around 8 kHz for the 22.05 kHz models).

#### 7.3.2 Benchmark Results (Arabic, diacritized input):
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

- Total parameters: 2.9 M (mixer80) + 13.4 M (vocos22) = 16.3 M.
- Response time: ~1.4 seconds for a typical sentence.
- Quality: clear, natural, no degradation over long text.
- The "models_onnx.py" file provides the needed ressources to download the corresponding onnx files. The onnx files are loaded once (for )the first time) into the "models_onnx" subdirectory. 
- Refer to the Ressources and References section of this documentation for more information about the model.

#### 7.3.3 Diacritization (Tashkeel) for Arabic:
Several diacritization models were tested:

- shakkala, shakkelha, catt‑eo – initial candidates. catt‑eo was selected for its audible correctness (better than visible diacritic anomalies).
- SILMA – good state‑of‑the‑art but slow for real‑time CPU usage.
- Fine‑Tashkeel (ByT5) – excellent accuracy, but:
    - Too slow for real‑time CPU.
    - Optimisations (caching, static KV, ONNX export) either worsened latency or were incompatible due to the model’s age and reliance on a GPU.

Decision: Diacritization is delegated to a separate AI model (outside this TTS service). The current pipeline expects already diacritized Arabic text. Yet the cat-eo is kept in use within the pipeline.

#### 7.3.4 Final Pipeline:

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

## 8. Ressources and References:

### 8.1 kokoro Model:
- Reference: hexgrad (2024). *Kokoro-82M* (Version v0.19) [Text-to-Speech Model]. Hugging Face. https://huggingface.co/hexgrad/Kokoro-82M
- Technical details: The model is based on StyleTTS2 [7†L9-L10], with 82 million parameters, and is licensed under Apache 2.0 [8†L11-L13]. It was trained on less than 100 hours of audio data [8†L18-L19].

### 8.2 Mixer80Vocos:

- Reference: nipponjo (2024). tts_arabic (Version v0.1) [Text-to-Speech Models]. GitHub. https://github.com/nipponjo/tts_arabic / https://huggingface.co/nipponjo/tts-arabic-onnx
  - The repository also has an accompanying manuscript: Arabic TTS with FastPitch: Reproducible Baselines, Adversarial Training, and Oversmoothing Analysis (arXiv:2512.00937).
  - speakers reference: [https://nipponjo.github.io/tts-arabic-speakers/](https://nipponjo.github.io/tts-arabic-speakers/): 4 voice references were provided (Men: S0, S1; women: S3, S4) - S1 was selected.

- Technical details:
  - The mixer80 model is a MixerTTS model, a non‑autoregressive architecture based on MLP‑Mixer adapted for speech synthesis. It has 2.9M parameters and generates 80‑bin mel‑spectrograms.
  - The vocos model is a GAN‑based vocoder that directly generates Fourier spectral coefficients, achieving state‑of‑the‑art audio quality with an order‑of‑magnitude speed improvement over time‑domain vocoders. It has 13.4M parameters and outputs 22.05kHz waveforms (with a vocos44 variant for 44.1kHz).
  - Both models are distributed in the ONNX format for offline, CPU‑efficient inference. The mel‑spectrogram covers frequencies up to 8kHz; the vocoder artificially extends bandwidth to 11.025kHz (22.05kHz for vocos44).
  - Refer to the Ressources and References section of this documentation for more information about the model.


### 8.3 catt-eo:
- Reference: The model page lists it as a vowelizer for Arabic text, converted from a PyTorch checkpoint (best_eo_mlm_ns_epoch_193.pt) [0†L4-L7][7†L13].
- Technical Basis: catt_eo is a character‑based transformer for Arabic diacritization, built on pretrained BERT‑like models [3†L8-L13][5†L4-L8].

## 9. License & Attribution

This project uses the following third-party components:

- **Kokoro** – Copyright (c) 2024 hexgrad.  
  - Licensed under the Apache License, Version 2.0.  
  - Source: [https://github.com/hexgrad/kokoro](https://github.com/hexgrad/kokoro)  
  - A copy of the license is available at [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0).

- **Vocos** – Copyright (c) 2024 Language Technologies Unit, Barcelona Supercomputing Center.  
  - Licensed under the **MIT License**.
  - Source: [BSC-LT/vocos](https://github.com/langtech-bsc/vocos)  
  - Model: `vocos22.onnx`

- **MixerTTS (mixer80)** – Copyright (c) 2021 NVIDIA.  
  - Licensed under the **Apache License 2.0**.  
  - Source: [NVIDIA/NeMo](https://github.com/NVIDIA/NeMo)  
  - Model: `mixer80.onnx`

- **catt_eo** model by the CATT project (© Abjad AI)
  - Licensed under the **Apache License 2.0**.
  - Source: https://github.com/abjadai/catt
  - Model: `cat-eo.onnx`

