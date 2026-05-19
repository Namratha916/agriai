# AgriAI

AgriAI is an AI-powered pesticide safety and farmer assistance platform for farmers and pesticide workers who need fast, practical guidance after chemical exposure.

## Features

- Chemical identifier with a local pesticide seed database.
- Danger level, symptoms, and first-aid guidance.
- Step-by-step decontamination checklist for skin/clothes, eye, and inhalation exposure.
- Symptom checker that flags emergency and high-concern patterns.
- Emergency alert message builder with optional GPS location.
- Nearby hospital and poison-control map links.
- Offline-first Ollama chatbot endpoint for contextual GenAI replies.
- Prompt-template based chat behavior in `prompt_templates.py`.
- English/Hindi/Kannada language switching with auto language detection.
- Browser voice input and voice output using Web Speech APIs.
- Pesticide label photo upload with optional local Hugging Face image-to-text analysis.
- Multi-engine OCR pipeline: image preprocessing, Tesseract OCR, EasyOCR, and Hugging Face TrOCR fallback.
- Pesticide detail extraction: product name, active ingredients, usage, toxicity level, side effects, first aid, decontamination, and environmental impact.
- RAG retrieval over `data/pesticides.json` and text manuals in `knowledge/`, with optional ChromaDB + sentence-transformers.
- Optional Whisper speech-to-text and gTTS/Coqui server-side text-to-speech APIs.
- Optional Streamlit companion UI in `streamlit_app.py`.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Ollama Chatbot

Install and run Ollama separately, then pull a model:

```powershell
ollama pull phi3:mini
ollama pull tinyllama
ollama serve
```

Optional environment variables:

```powershell
$env:OLLAMA_MODEL="phi3:mini"
$env:OLLAMA_URL="http://localhost:11434/api/chat"
$env:OLLAMA_TIMEOUT="90"
python app.py
```

Recommended low-RAM models:

- `phi3:mini`: better quality on 8GB RAM systems.
- `tinyllama`: fastest fallback, lower quality.
- `mistral:latest`: better quality if the laptop can handle it.

The app retrieves pesticide context before generation, uses compact LangChain PromptTemplates, caches Ollama replies, supports `/api/chat-stream` for streaming output, and falls back to structured safety guidance if Ollama is slow.

## Language And Voice

Use the language selector in the header:

- `Auto`: replies in Kannada/Hindi when the user types/speaks Kannada/Hindi, otherwise English.
- `English`: forces English replies.
- `Hindi`: requests Hindi replies.
- `Kannada`: asks the chatbot and built-in safety replies to use Kannada.

Voice input and voice output use the browser Web Speech APIs, so they work best in browsers that support `SpeechRecognition` and `speechSynthesis`. Kannada voice support depends on the voices installed in the browser/operating system.

The dedicated speaker button controls voice replies globally:

- `Voice ON`: AgriAI speaks chatbot and image-analysis replies.
- `Voice OFF`: AgriAI immediately calls `window.speechSynthesis.cancel()` and stops any server audio playback.

## OCR And Hugging Face Photo Analysis

The pesticide photo analyzer is offline-first. Pipeline:

```text
Image upload
-> PIL preprocessing
-> Tesseract OCR
-> EasyOCR fallback
-> Hugging Face TrOCR fallback
-> pesticide/active ingredient extraction
-> RAG retrieval
-> structured AI safety explanation
```

```powershell
$env:HF_OCR_MODEL="microsoft/trocr-base-printed"
$env:HF_WHISPER_MODEL="openai/whisper-tiny"
$env:HF_LOCAL_ONLY="1"
$env:AGRIAI_DEEP_OCR="1"
python app.py
```

Install Tesseract OCR on Windows separately, then make sure `tesseract.exe` is on PATH. The OCR service applies grayscale conversion, contrast enhancement, sharpening, OpenCV resizing, adaptive thresholding, Otsu thresholding, Tesseract OCR, and optional EasyOCR/TrOCR fallback.

Because `HF_LOCAL_ONLY=1`, Hugging Face models must already be cached locally. Set `HF_LOCAL_ONLY=0` only if you want Transformers to download models.

## RAG Knowledge Base

AgriAI always indexes `data/pesticides.json`. You can add pesticide manuals or safety notes as `.txt` files inside `knowledge/`. By default it uses a lightweight keyword retriever for low-end laptops. Set `AGRIAI_ENABLE_CHROMA=1` to enable ChromaDB + sentence-transformers local vector search.

## Voice AI

Frontend voice input uses browser Web Speech API. Backend voice endpoints are also available:

- `POST /api/speech-to-text`: accepts an uploaded audio file named `audio`, uses `openai/whisper-tiny` by default for lower latency.
- `POST /api/text-to-speech`: accepts JSON `{ "text": "...", "language": "en|hi|kn" }`, uses gTTS first and optional Coqui TTS fallback if installed.

Browser speech synthesis is still used as a low-memory fallback.

## Streamlit

Start Flask first:

```powershell
python app.py
```

Then in another terminal:

```powershell
streamlit run streamlit_app.py
```

## Database

The prototype uses `data/pesticides.json` so it works without MySQL/Firebase setup. For a production project, migrate the same fields into MySQL or Firebase and build an admin/import tool from approved pesticide sources such as product labels, government registrations, WHO safety documents, and PesticideInfo.

`database_schema.sql` contains a starter MySQL schema for pesticide names, aliases, symptoms, and exposure routes.

This seed is not a complete global pesticide database. It contains common high-risk and common-use examples so the app can be demonstrated safely.

## Safety Sources

Guidance was aligned with public safety recommendations from:

- WHO pesticide poisoning resource tools: https://www.who.int/publications/m/item/sound-management-of-pesticides-and-diagnosis-and-treatment-of-pesticide-poisoing-a-resource-tool
- WHO chemical release decontamination guidance: https://www.who.int/environmental_health_emergencies/deliberate_events/chemical_release/en/
- US EPA pesticide first aid: https://www.epa.gov/pesticide-incidents/first-aid-case-pesticide-exposure
- CDC chemical decontamination: https://www.cdc.gov/chemical-emergencies/response/get-clean.html
- CCOHS pesticide first aid: https://www.ccohs.ca/oshanswers/chemicals/pesticides/firstaid.html

## Important

This is an educational prototype, not medical advice. In real exposure cases, follow the pesticide label and contact emergency medical services, poison control, or a hospital immediately when serious symptoms occur.
