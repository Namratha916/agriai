# PestiSafe AI

PestiSafe AI is an AI-powered pesticide safety and farmer assistance platform for farmers and pesticide workers who need fast, practical guidance after chemical exposure.

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
- Render-friendly OCR pipeline: browser Tesseract.js, image preprocessing, and lightweight Tesseract OCR when available.
- Pesticide detail extraction: product name, active ingredients, usage, toxicity level, side effects, first aid, decontamination, and environmental impact.
- RAG retrieval over `data/pesticides.json` and text manuals in `knowledge/`, with lightweight embeddings and optional ChromaDB + sentence-transformers.
- Optional internet search context for pesticide names that are not in the local database.
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

For local server-side EasyOCR/Tesseract/TrOCR support, install the optional OCR package set:

```powershell
pip install -r requirements-local-ocr.txt
```

## Ollama Chatbot

PestiSafe AI supports model switching with `MODEL_PROVIDER`.

Use local Ollama for testing:

```powershell
ollama pull mistral
ollama serve
```

```powershell
$env:MODEL_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:OLLAMA_MODEL="mistral"
$env:OLLAMA_TIMEOUT="90"
python app.py
```

Use xAI Grok for production/deployment:

```powershell
$env:MODEL_PROVIDER="grok"
$env:XAI_API_KEY="your_xai_api_key"
$env:GROK_MODEL="grok-4.3"
python app.py
```

Both Grok and Ollama use this prompt format with retrieved pesticide context:

```text
You are PestiSafe AI, a pesticide safety Generative AI assistant.
Reply in the selected language: {language}.
Use the given pesticide context.
If image text is provided, identify pesticide or chemical name.
Give short, clear, farmer-friendly answer.

Context:
{context}

Image text:
{image_text}

User question:
{question}

Answer format:
1. Identified pesticide/chemical
2. Danger level
3. Side effects
4. First aid
5. Safety precautions
6. When to visit hospital
```

If `MODEL_PROVIDER=grok` but `XAI_API_KEY` is missing, the app returns a clear fallback message. Existing Ollama/local model support remains available with `MODEL_PROVIDER=ollama`.

## Vercel Deployment With Grok

1. Import the GitHub repository in Vercel.
2. Add environment variables:

```text
MODEL_PROVIDER=grok
XAI_API_KEY=your_xai_api_key
GROK_MODEL=grok-4.3
HF_LOCAL_ONLY=0
AI_IMAGE_EXPLANATION=0
AGRIAI_ENABLE_CHROMA=0
```

3. Deploy. `vercel.json` routes requests to `app.py`.

The deployed analyzer uses browser OCR first through Tesseract.js, so Vercel does not need heavy local OCR packages like Torch/EasyOCR. If browser OCR cannot read the label, add `HF_API_TOKEN` to Vercel to enable hosted Hugging Face OCR fallback.

## GitHub Commit Commands

```powershell
git status
git add .
git commit -m "Add Grok API provider support"
git push origin main
```

For a more ChatGPT-like assistant, configure GitHub Models as a cloud fallback:

```powershell
$env:GITHUB_TOKEN="your_github_models_token"
$env:GITHUB_MODEL="gpt-4o-mini"
python app.py
```

PestiSafe AI tries Ollama first, then GitHub Models, then its local pesticide/RAG fallback.

## Language And Voice

Use the language selector in the header:

- `Auto`: replies in Kannada/Hindi when the user types/speaks Kannada/Hindi, otherwise English.
- `English`: forces English replies.
- `Hindi`: requests Hindi replies.
- `Kannada`: asks the chatbot and built-in safety replies to use Kannada.

Voice input and voice output use the browser Web Speech APIs, so they work best in browsers that support `SpeechRecognition` and `speechSynthesis`. Kannada voice support depends on the voices installed in the browser/operating system.

The dedicated speaker button controls voice replies globally:

- `Voice ON`: PestiSafe AI speaks chatbot and image-analysis replies.
- `Voice OFF`: PestiSafe AI immediately calls `window.speechSynthesis.cancel()` and stops any server audio playback.

## OCR And Photo Analysis

The pesticide photo analyzer is deployment-first and still supports local OCR. Pipeline:

```text
Image upload
-> browser OCR with Tesseract.js
-> backend pesticide/active ingredient extraction
-> if browser OCR is empty: PIL preprocessing
-> lightweight Tesseract OCR when available
-> optional EasyOCR/TrOCR only if explicitly enabled
-> pesticide/active ingredient extraction
-> local RAG + lightweight embeddings + optional internet search context
-> LLM or fast structured safety explanation
```

```powershell
$env:HF_WHISPER_MODEL="openai/whisper-tiny"
$env:HF_LOCAL_ONLY="0"
$env:AGRIAI_DEEP_OCR="0"
$env:AGRIAI_ENABLE_TROCR="0"
$env:AGRIAI_ENABLE_WEB_SEARCH="1"
python app.py
```

Install Tesseract OCR on Windows separately, then make sure `tesseract.exe` is on PATH. The OCR service applies grayscale conversion, contrast enhancement, sharpening, OpenCV resizing, adaptive thresholding, and Otsu thresholding before OCR.

Large OCR models are disabled by default for Render stability. Keep `AGRIAI_DEEP_OCR=0` and `AGRIAI_ENABLE_TROCR=0` on small deployments.

## Render Deployment

Create a Python Web Service on Render with:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
```

Render also reads `apt.txt` to install lightweight Tesseract language packs for English, Hindi, and Kannada.

## RAG Knowledge Base

PestiSafe AI always indexes `data/pesticides.json`. You can add pesticide manuals or safety notes as `.txt` files inside `knowledge/`. By default it uses keyword retrieval plus lightweight hashed embeddings for low-end laptops. Set `AGRIAI_ENABLE_CHROMA=1` to enable ChromaDB + sentence-transformers local vector search on stronger machines.

If `AGRIAI_ENABLE_WEB_SEARCH=1`, unknown pesticide names and label text can also be searched online and added to the LLM prompt as external context. If internet is unavailable, the app silently falls back to local RAG.

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
