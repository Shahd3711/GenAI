from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("ANTHROPIC_API_KEY")


app = Flask(__name__, static_folder="../frontend")
CORS(app)

# ── System prompt ────────────────────────────────────────────────────────────
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


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """
    Expects JSON:
    {
      "messages": [{"role": "user"|"assistant", "content": "..."}],
      "creativity": 50,      // 0–100
      "detailed": false      // bool
    }
    Returns JSON:
    {
      "reply": "...",
      "stage": 1|2|3|4
    }
    """
    data = request.get_json(force=True)
    messages: list = data.get("messages", [])
    creativity: int = int(data.get("creativity", 50))
    detailed: bool = bool(data.get("detailed", False))

    if not messages:
        return jsonify({"error": "messages array is required"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY") or data.get("api_key", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 401

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=build_system(
                creativity=creativity_label(creativity),
                detail=detail_label(detailed)
            ),
            messages=messages,
            temperature=creativity_to_temperature(creativity),
        )
    except anthropic.APIError as e:
        return jsonify({"error": str(e)}), 502

    reply_text = response.content[0].text

    # Heuristic: detect current stage from reply content
    stage = detect_stage(messages, reply_text)

    return jsonify({"reply": reply_text, "stage": stage})


def detect_stage(messages: list, latest_reply: str) -> int:
    """
    Rough heuristic to determine which stage the conversation is in.
    """
    # Count prior assistant messages
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")
    r = latest_reply.lower()

    if assistant_turns == 0:
        return 1  # Just started
    if assistant_turns <= 1 and any(w in r for w in ["meal", "mood", "breakfast", "dinner", "lunch", "snack"]):
        return 2
    if assistant_turns <= 2 and any(w in r for w in ["option", "suggest", "how about", "1.", "•"]):
        return 3
    if any(w in r for w in ["recipe", "step 1", "serves", "minutes", "preheat", "heat the pan"]):
        return 4
    return min(assistant_turns + 1, 4)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🍳  AI Chef Assistant running at http://localhost:5000")
    print("    Set ANTHROPIC_API_KEY in your environment or pass api_key in request body.")
    app.run(debug=True, port=5000)
