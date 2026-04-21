
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__, static_folder="../frontend")
CORS(app)

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# ── System prompt (identical to Anthropic version) ────────────────────────────
BASE_SYSTEM = """You are Chef Claude — a warm, passionate, and deeply knowledgeable culinary expert.
You speak with the confidence and flair of a real chef, using rich culinary language without being
pretentious. You address the user warmly (occasionally "mon ami", "my friend", or "chef").

Your mission is to guide the user step-by-step through these EXACT stages — NEVER skip or combine them:

**STAGE 1 — INGREDIENTS**: The user tells you what ingredients they have. Acknowledge each ingredient
enthusiastically. Identify food categories (proteins, produce, pantry staples). Then move to Stage 2.

**STAGE 2 — MEAL TYPE**: Ask what kind of meal they are in the mood for (breakfast, lunch, dinner, snack).
Also ask about dietary preferences or restrictions if not already known.

**STAGE 3 — PREFERENCES**: Based on ingredients + meal type, propose 2–3 specific meal ideas.
Ask which appeals most, or if they have another direction in mind.

**STAGE 4 — RECIPE**: Once the user has chosen, deliver the full step-by-step recipe with ingredients,
quantities, and technique. Use chef-style language. Include a pro tip at the end.

RULES:
- NEVER skip a stage. Always complete each stage in order before moving to the next.
- NEVER output a full recipe before Stage 4.
- Remember everything the user has told you throughout the conversation.
- Creativity and detail level will be specified via [CREATIVITY] and [DETAIL] tags.
- Always stay in character as a real, human chef."""


def build_system(creativity: str = "balanced", detail: str = "concise") -> str:
    return f"""{BASE_SYSTEM}

[CREATIVITY]: {creativity}
[DETAIL]: {detail}"""


def creativity_label(value: int) -> str:
    if value < 30:
        return "strict classical technique — stick to traditional, proven recipes"
    elif value < 70:
        return "balanced — classic with occasional creative touches"
    else:
        return "highly creative and experimental — bold flavour combinations welcome"


def detail_label(detailed: bool) -> str:
    return "detailed and thorough — explain techniques, why things work" if detailed else \
           "concise and punchy — get to the point, chef-speak only"


def creativity_to_temperature(value: int) -> float:
    """Map 0–100 slider to 0.3–1.3 temperature."""
    return round(0.3 + (value / 100) * 1.0, 2)


def openai_messages_to_ollama(system: str, messages: list) -> list:
    """
    Convert Anthropic-style message list to Ollama /api/chat format.
    Ollama's /api/chat uses the same role structure as OpenAI:
    [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    result = [{"role": "system", "content": system}]
    for m in messages:
        result.append({"role": m["role"], "content": m["content"]})
    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


@app.route("/models", methods=["GET"])
def list_models():
    """List available Ollama models."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 502


@app.route("/chat", methods=["POST"])
def chat():
    """
    Same API contract as the Anthropic backend — drop-in replacement.

    Expects JSON:
    {
      "messages": [{"role": "user"|"assistant", "content": "..."}],
      "creativity": 50,
      "detailed": false,
      "model": "llama3"     // optional, overrides DEFAULT_MODEL
    }
    Returns JSON:
    {
      "reply": "...",
      "stage": 1|2|3|4,
      "model": "llama3"
    }
    """
    data = request.get_json(force=True)
    messages: list = data.get("messages", [])
    creativity: int = int(data.get("creativity", 50))
    detailed: bool = bool(data.get("detailed", False))
    model: str = data.get("model", DEFAULT_MODEL)

    if not messages:
        return jsonify({"error": "messages array is required"}), 400

    ollama_messages = openai_messages_to_ollama(
        system=build_system(
            creativity=creativity_label(creativity),
            detail=detail_label(detailed)
        ),
        messages=messages
    )

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": creativity_to_temperature(creativity),
                    "num_predict": 1024,
                }
            },
            timeout=120
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": f"Cannot connect to Ollama at {OLLAMA_HOST}. "
                     "Make sure `ollama serve` is running."
        }), 502
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"Ollama HTTP error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    reply_text = payload.get("message", {}).get("content", "")
    if not reply_text:
        return jsonify({"error": "Empty response from Ollama"}), 500

    stage = detect_stage(messages, reply_text)

    return jsonify({"reply": reply_text, "stage": stage, "model": model})


def detect_stage(messages: list, latest_reply: str) -> int:
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")
    r = latest_reply.lower()
    if assistant_turns == 0:
        return 1
    if assistant_turns <= 1 and any(w in r for w in ["meal", "mood", "breakfast", "dinner", "lunch", "snack"]):
        return 2
    if assistant_turns <= 2 and any(w in r for w in ["option", "suggest", "how about", "1.", "•"]):
        return 3
    if any(w in r for w in ["recipe", "step 1", "serves", "minutes", "preheat", "heat the pan"]):
        return 4
    return min(assistant_turns + 1, 4)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🍳  AI Chef Assistant (Ollama) running at http://localhost:5001")
    print(f"    Ollama host : {OLLAMA_HOST}")
    print(f"    Default model: {DEFAULT_MODEL}")
    print("    Make sure `ollama serve` is running and the model is pulled.")
    app.run(debug=True, port=5001)
