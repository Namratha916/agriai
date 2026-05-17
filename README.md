# Safe Return

Safe Return is a beginner-friendly Flask prototype for farmers and pesticide workers who need quick decontamination guidance after chemical exposure.

## Features

- Chemical identifier with a local pesticide seed database.
- Danger level, symptoms, and first-aid guidance.
- Step-by-step decontamination checklist for skin/clothes, eye, and inhalation exposure.
- Symptom checker that flags emergency and high-concern patterns.
- Emergency alert message builder with optional GPS location.
- Nearby hospital and poison-control map links.
- Ollama-powered chatbot endpoint for contextual GenAI replies.

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
ollama pull tinyllama
ollama serve
```

Optional environment variables:

```powershell
$env:OLLAMA_MODEL="tinyllama"
$env:OLLAMA_URL="http://localhost:11434/api/chat"
$env:OLLAMA_TIMEOUT="90"
python app.py
```

The app first creates a chemical-aware safety answer from its pesticide database, then asks Ollama to rewrite it in natural language. If Ollama is slow, the app quickly returns the safety answer instead of waiting forever.

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
