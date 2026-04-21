# 👨‍🍳 AI Chef Assistant

A full-stack AI-powered culinary guide that accepts ingredients, understands available food,
and walks the user through **four strict stages** to a complete meal — never skipping steps,
speaking like a real human chef.

---

## Project Structure

```
ai-chef-assistant/
├── frontend/
│   └── index.html          ← Standalone UI (calls API directly from browser)
├── backend/
│   ├── app.py              ← Flask server — Anthropic Claude API (Part a)
│   └── requirements.txt
├── ollama/
│   ├── ollama_app.py       ← Flask server — Ollama local LLM (Part b)
│   └── requirements.txt
└── README.md
```

---

## Features

| Feature | Detail |
|---|---|
| 🥦 Ingredient Input | Free-text ingredients list |
| 🪜 Step-by-step guidance | 4 strict stages — Ingredients → Meal Type → Preferences → Recipe |
| 👨‍🍳 Human-like Chef | Speaks with culinary flair, addresses user warmly |
| 🧠 Conversation Memory | Full chat history sent to model each turn |
| 🎨 Creativity Slider | 0 = classical/strict → 100 = experimental/creative (maps to temperature) |
| 📝 Detail Toggle | Brief (concise) ↔ Detailed (thorough explanation) |
| 🔁 Session Reset | Start a fresh conversation at any time |
| 🖥️ Ollama Support | Identical logic running on local open-source LLM |

---

## Part A — Anthropic Claude Backend

### Option 1: Open `frontend/index.html` directly in your browser

Enter your Anthropic API key in the header field — no server needed.

### Option 2: Run the Flask backend

```bash
cd backend
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-api03-...

python app.py
# → http://localhost:5000
```

#### API Endpoint

```
POST /chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "I have eggs, spinach, and cheddar"}
  ],
  "creativity": 70,
  "detailed": false
}
```

Response:
```json
{
  "reply": "Magnifique! Eggs, spinach, and cheddar — the holy trinity of a great omelette...",
  "stage": 2
}
```

---

## Part B — Ollama (Local LLM)

The same chef logic runs on a local model via [Ollama](https://ollama.com/).

### Setup

```bash
# 1. Install and start Ollama
ollama serve

# 2. Pull a model (choose one)
ollama pull llama3        # recommended
ollama pull mistral
ollama pull gemma2

# 3. Run the Ollama backend
cd ollama
pip install -r requirements.txt
python ollama_app.py
# → http://localhost:5001
```

### Configuration via environment variables

```bash
export OLLAMA_HOST=http://localhost:11434   # default
export OLLAMA_MODEL=llama3                 # default
```

### List available models

```
GET http://localhost:5001/models
```

### Chat endpoint (identical contract to Anthropic backend)

```
POST http://localhost:5001/chat
Content-Type: application/json

{
  "messages": [...],
  "creativity": 50,
  "detailed": false,
  "model": "llama3"   // optional override
}
```

---

## The Four Chef Stages

The system prompt enforces strict stage ordering — the AI **never** skips stages:

```
Stage 1 — INGREDIENTS
  → User lists what they have
  → Chef acknowledges and categorises

Stage 2 — MEAL TYPE
  → Chef asks: breakfast / lunch / dinner / snack?
  → Checks for dietary restrictions

Stage 3 — PREFERENCES
  → Chef proposes 2–3 meal ideas
  → User picks one

Stage 4 — RECIPE
  → Full step-by-step recipe with quantities, technique, and a pro tip
```

---

## System Prompt Design

The chef persona and stage logic are controlled via a single system prompt injected into every API call.
Two runtime tags customise behaviour:

- `[CREATIVITY]`: maps slider value 0–100 to a text description (classical → experimental).  
  Also controls model temperature (0.3 → 1.3).
- `[DETAIL]`: toggles concise vs. thorough response style.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Anthropic backend | Python · Flask · `anthropic` SDK |
| Ollama backend | Python · Flask · `requests` |
| AI Model (A) | `claude-sonnet-4-20250514` |
| AI Model (B) | `llama3` / `mistral` / `gemma2` (via Ollama) |
