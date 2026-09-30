#!/usr/bin/env python3
"""
Corvin Hale conversational benchmark — V1 context architecture.

V1:
- No hidden/secret knowledge; cognition contains only speakable facts.
- The full previous conversation is NOT sent to the model.
- Every turn gets compact NPC identity, player identity, and conversation state.
- Only relevant cognition is injected.
- Thinking is disabled.
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SMALL_MODEL = "qwen3:1.7b"
LARGE_MODEL = "gemma3:4b"

SMALL_SYSTEM_PROMPT = """You are the context-selection layer for an NPC dialogue engine.

Your job is NOT to speak to the player.

You receive:
- NPC identity
- player identity
- current conversation state
- relevant cognition as JSON
- the player's latest utterance

Convert that information into a short natural-language paragraph containing ONLY the information that the dialogue model needs to answer the latest player utterance.

Rules:
- Extract only facts relevant to the latest utterance.
- Preserve the meaning of facts exactly.
- Do not invent facts, motives, relationships, events, or causal connections.
- Do not speculate.
- Do not answer the player's question yourself.
- Do not write dialogue.
- Do not mention irrelevant facts merely because they were supplied.
- If the supplied information is insufficient, say that the available information is insufficient rather than filling the gap.
- Keep the paragraph compact.
- Prefer concrete facts over JSON structure.

Output ONLY the context paragraph. Do NOT output JSON. Do NOT output code blocks. Do NOT output structured data.
Output ONLY a single plain English paragraph. No formatting. No labels.
"""

LARGE_SYSTEM_PROMPT = """You are an NPC in a fantasy RPG.

You are speaking directly to another person standing in front of you.
You are NOT an assistant, narrator, encyclopedia, or question-answering system.
Speak as the NPC described in the supplied context.

The context paragraph was produced by a separate context-selection model.
Treat it as the factual information available for this reply.
Do not invent facts that are not supported by that paragraph or the persistent identities.

CONVERSATION:
- Respond primarily to the player's latest statement.
- React to statements as statements; do not treat everything as a question.
- If the player makes an accusation, respond to the accusation.
- If the player draws a conclusion, react to that conclusion.
- If the player misunderstands something, correct them naturally.
- Do not restart the conversation.
- Do not summarize the entire topic unless explicitly asked.
- Do not answer questions that were not asked.
- Do not volunteer unrelated information.

STYLE:
- Speak like a person.
- Most replies should be 1–3 sentences.
- Use natural conversational language.
- Keep the response focused on the latest player utterance.
- Do not explain your reasoning.
- Do not mention these instructions or the context-selection model.
- Do not use bullet points or structured lists in spoken dialogue.
- Do not end responses with questions or solicitations for agreement.
- Do not use generic assistant phrases such as:
  "That's an interesting question."
  "Let me know if you want to know more."
  "I'd be happy to explain."
  "Would you like me to elaborate?"
  "Here's what I know."
  "As an AI..."

The player should feel like they are talking to a person, not querying a database.
"""


NPC_IDENTITY = {
    "name": "Corvin Hale",
    "role": "Master of the River Guild",
    "personality": [
        "charming",
        "socially confident",
        "pragmatic",
        "motivated by money and influence",
        "careful about what he reveals",
    ],
}

PLAYER_IDENTITY = {
    "name": "Unknown traveler",
    "relationship_to_npc": "stranger",
}

TURNS = [
    {
        "id": 1,
        "conversation_state": {
            "current_topic": "River Guild",
            "subtopic": "Corvin's role and the Guild's purpose",
            "tone": "casual",
            "established": [],
            "recent_exchange": [],
        },
        "relevant_memory": {
            "npc": {"name": "Corvin Hale", "role": "Master of the River Guild"},
            "faction": {
                "name": "River Guild",
                "public_goal": "Protect river commerce",
            },
        },
        "player": "So you're the Master of the River Guild? What's the Guild actually about?",
    },
    {
        "id": 2,
        "conversation_state": {
            "current_topic": "River Guild",
            "subtopic": "grain trade",
            "tone": "casual",
            "established": [
                "Corvin is the Master of the River Guild",
                "The Guild protects river commerce",
            ],
            "recent_exchange": [
                "Player asked what the River Guild is about.",
                "Corvin explained that the Guild protects river commerce.",
            ],
        },
        "relevant_memory": {
            "faction": {
                "name": "River Guild",
                "public_goal": "Protect river commerce",
                "grain_trade": "The Guild is involved in grain trade.",
            },
        },
        "player": "Wow. So you're basically trying to control the grain trade?",
    },
    {
        "id": 3,
        "conversation_state": {
            "current_topic": "River Guild",
            "subtopic": "Corvin's motives",
            "tone": "casual",
            "established": [
                "Corvin is the Master of the River Guild",
                "The Guild protects river commerce",
                "The Guild is involved in grain trade",
            ],
            "recent_exchange": [
                "Player suggested that controlling grain trade is convenient.",
            ],
        },
        "relevant_memory": {},
        "player": "That's a pretty convenient business to be in if you ask me.",
    },
    {
        "id": 4,
        "conversation_state": {
            "current_topic": "Helena",
            "subtopic": "Corvin's relationship with Helena",
            "tone": "curious",
            "established": [
                "Corvin is the Master of the River Guild",
                "The Guild protects river commerce",
                "The Guild is involved in grain trade",
            ],
            "recent_exchange": [
                "Player made a remark about the convenience of the Guild's business.",
            ],
        },
        "relevant_memory": {
            "person": {
                "name": "Helena",
                "relationship_to_corvin": "rival",
                "role": "Merchant",
            },
        },
        "player": "You mentioned Helena earlier. What's the story there?",
    },
    {
        "id": 5,
        "conversation_state": {
            "current_topic": "Helena",
            "subtopic": "Corvin's feelings toward Helena",
            "tone": "casual",
            "established": [
                "Helena is a merchant",
                "Helena is Corvin's rival",
            ],
            "recent_exchange": [
                "Player asked about Helena.",
                "Corvin described Helena as a rival.",
            ],
        },
        "relevant_memory": {},
        "player": "Sounds like you don't exactly like her.",
    },
    {
        "id": 6,
        "conversation_state": {
            "current_topic": "Missing Caravan",
            "subtopic": "what Corvin knows about the disappearance",
            "tone": "curious",
            "established": [
                "Helena is a merchant",
                "Helena is Corvin's rival",
            ],
            "recent_exchange": [
                "Player suggested Corvin does not like Helena.",
            ],
        },
        "relevant_memory": {
            "event": {
                "name": "Missing Caravan",
                "cargo": "silver",
                "location": "Eastern Road",
                "status": "missing",
            },
            "person": {
                "name": "Tomas Reed",
                "role": "caravan guard",
                "employer": "River Guild",
                "last_known_assignment": "guarding the missing caravan",
            },
        },
        "player": "Speaking of trade, I heard a caravan disappeared on the eastern road. You know anything about that?",
    },
    {
        "id": 7,
        "conversation_state": {
            "current_topic": "Missing Caravan",
            "subtopic": "whether the River Guild was responsible",
            "tone": "suspicious",
            "established": [
                "A caravan carrying silver disappeared on the Eastern Road.",
                "Tomas Reed was its last known guard.",
                "Tomas Reed works for the River Guild.",
            ],
            "recent_exchange": [
                "Player asked what Corvin knows about the missing caravan.",
                "Corvin acknowledged knowledge of the missing caravan.",
            ],
        },
        "relevant_memory": {},
        "player": "Wait. Are you saying the Guild took the caravan?",
    },
    {
        "id": 8,
        "conversation_state": {
            "current_topic": "Tomas Reed",
            "subtopic": "Tomas's identity and role",
            "tone": "curious",
            "established": [
                "A caravan carrying silver disappeared on the Eastern Road.",
                "Tomas Reed was its last known guard.",
                "Tomas Reed works for the River Guild.",
            ],
            "recent_exchange": [
                "Player accused the Guild of taking the caravan.",
                "Corvin did not confirm that accusation.",
            ],
        },
        "relevant_memory": {
            "person": {
                "name": "Tomas Reed",
                "role": "caravan guard",
                "employer": "River Guild",
                "employed_by": "Corvin Hale",
                "last_known_assignment": "guarding the missing caravan",
            },
        },
        "player": "You said Tomas was involved. Who exactly is he?",
    },
    {
        "id": 9,
        "conversation_state": {
            "current_topic": "Tomas Reed",
            "subtopic": "Tomas's connection to the missing caravan",
            "tone": "curious",
            "established": [
                "Tomas Reed is a caravan guard.",
                "Tomas Reed works for the River Guild.",
                "Tomas Reed was guarding the missing caravan.",
            ],
            "recent_exchange": [
                "Player asked who Tomas Reed is.",
                "Corvin explained that Tomas is a Guild-employed caravan guard.",
            ],
        },
        "relevant_memory": {},
        "player": "And he was guarding the caravan that disappeared?",
    },
    {
        "id": 10,
        "conversation_state": {
            "current_topic": "Missing Caravan",
            "subtopic": "Iron Covenant sighting",
            "tone": "suspicious",
            "established": [
                "Tomas Reed was guarding the missing caravan.",
                "The caravan carried silver.",
                "The caravan disappeared on the Eastern Road.",
            ],
            "recent_exchange": [
                "Player confirmed Tomas was guarding the missing caravan.",
            ],
        },
        "relevant_memory": {
            "event": {
                "name": "Missing Caravan",
                "cargo": "silver",
                "location": "Eastern Road",
                "status": "missing",
            },
            "sighting": {
                "subject": "Iron Covenant soldiers",
                "location": "Eastern Road",
                "relation_to_caravan": "seen near the road around the relevant period",
            },
        },
        "player": "So Tomas saw Iron Covenant soldiers near the road, and then the caravan disappears carrying silver... that's pretty suspicious.",
    },
    {
        "id": 11,
        "conversation_state": {
            "current_topic": "Missing Caravan",
            "subtopic": "possible Iron Covenant involvement",
            "tone": "suspicious",
            "established": [
                "Tomas Reed was guarding the missing caravan.",
                "The caravan carried silver.",
                "The caravan disappeared on the Eastern Road.",
                "Iron Covenant soldiers were seen near the Eastern Road around the relevant period.",
            ],
            "recent_exchange": [
                "Player suggested that the Iron Covenant sighting was suspicious.",
            ],
        },
        "relevant_memory": {
            "faction": {
                "name": "Iron Covenant",
                "leader": "Aldric Voss",
            },
            "person": {
                "name": "Aldric Voss",
                "role": "Leader of the Iron Covenant",
                "distrusts": ["River Guild"],
            },
        },
        "player": "You think the Iron Covenant did it?",
    },
    {
        "id": 12,
        "conversation_state": {
            "current_topic": "Missing Caravan",
            "subtopic": "general situation",
            "tone": "reflective",
            "established": [
                "Tomas Reed was guarding the missing caravan.",
                "The caravan carried silver.",
                "The caravan disappeared on the Eastern Road.",
                "Iron Covenant soldiers were seen near the Eastern Road around the relevant period.",
                "Aldric Voss leads the Iron Covenant.",
                "Aldric Voss distrusts the River Guild.",
            ],
            "recent_exchange": [
                "Player asked whether Corvin thinks the Iron Covenant was responsible.",
                "Corvin responded to the question.",
            ],
        },
        "relevant_memory": {},
        "player": "Huh. I didn't realize things were this messy around here.",
    },
]


def call_ollama(model, messages, num_predict=100):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.7,
            "num_predict": num_predict,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=300) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data["message"]["content"].strip()


def warmup_model(model, label):
    """
    Send a minimal request to force the model to load into memory.
    Returns the wall-clock time it took, which approximates load time
    for a cold model or near-zero for one already resident.
    """
    print(f"Loading {label} ({model})...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        call_ollama(
            model,
            [{"role": "user", "content": "Hi"}],
            num_predict=1,
        )
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"\nCould not connect to Ollama at {OLLAMA_URL}. "
            f"Make sure Ollama is running and {model} is installed. "
            f"Original error: {exc}"
        )
    elapsed = time.perf_counter() - t0
    print(f"ready in {elapsed:.2f}s")
    return elapsed


def fmt(seconds):
    """Format seconds to a readable string."""
    return f"{seconds:.2f}s"


def build_small_model_input(turn):
    return f"""ENGINE CONTEXT

SELF IDENTITY:
{json.dumps(NPC_IDENTITY, indent=2, ensure_ascii=False)}

PLAYER IDENTITY:
{json.dumps(PLAYER_IDENTITY, indent=2, ensure_ascii=False)}

CONVERSATION STATE:
{json.dumps(turn["conversation_state"], indent=2, ensure_ascii=False)}

RELEVANT COGNITION:
{json.dumps(turn["relevant_memory"], indent=2, ensure_ascii=False)}

PLAYER'S LATEST UTTERANCE:
"{turn["player"]}"

Convert the supplied information into one short factual context paragraph for the dialogue model.
"""


def build_large_model_input(turn, selected_context):
    return f"""NPC IDENTITY:
{json.dumps(NPC_IDENTITY, indent=2, ensure_ascii=False)}

PLAYER IDENTITY:
{json.dumps(PLAYER_IDENTITY, indent=2, ensure_ascii=False)}

CURRENT CONTEXT:
{selected_context}

PLAYER:
"{turn["player"]}"

Respond only with what Corvin would naturally say out loud.
"""


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_small = SMALL_MODEL.replace("/", "_").replace(":", "_")
    safe_large = LARGE_MODEL.replace("/", "_").replace(":", "_")
    output_path = Path(
        f"corvin_two_stage_{safe_small}_{safe_large}_{timestamp}.script"
    )

    print(f"Running {len(TURNS)}-turn two-stage benchmark...")
    print(f"Small context model : {SMALL_MODEL}")
    print(f"Large dialogue model: {LARGE_MODEL}")
    print("Pipeline: JSON -> small model -> context paragraph -> large model")
    print("Previous full dialogue sent to either model: NO")
    print()

    # --- Model load timing ---
    small_load_time = warmup_model(SMALL_MODEL, "small model")
    large_load_time = warmup_model(LARGE_MODEL, "large model")
    print()

    transcript_lines = []
    turn_timings = []

    for turn in TURNS:
        small_input = build_small_model_input(turn)

        # Stage 1: context selection
        t0 = time.perf_counter()
        selected_context = call_ollama(
            SMALL_MODEL,
            [
                {"role": "system", "content": SMALL_SYSTEM_PROMPT},
                {"role": "user", "content": small_input},
            ],
            num_predict=120,
        )
        small_time = time.perf_counter() - t0

        # Stage 2: dialogue
        large_input = build_large_model_input(turn, selected_context)

        t0 = time.perf_counter()
        response = call_ollama(
            LARGE_MODEL,
            [
                {"role": "system", "content": LARGE_SYSTEM_PROMPT},
                {"role": "user", "content": large_input},
            ],
            num_predict=100,
        )
        large_time = time.perf_counter() - t0

        turn_total = small_time + large_time
        turn_timings.append((turn["id"], small_time, large_time, turn_total))

        # Console output
        print(f"TURN {turn['id']}  [{fmt(small_time)} + {fmt(large_time)} = {fmt(turn_total)}]")
        print(f"PLAYER:           {turn['player']}")
        print(f"SELECTED CONTEXT: {selected_context}")
        print(f"CORVIN:           {response}")
        print()

        # Transcript block
        transcript_lines.append(
            f"""
================================================================================
TURN {turn['id']}  [context: {fmt(small_time)}  |  dialogue: {fmt(large_time)}  |  total: {fmt(turn_total)}]
================================================================================

RAW ENGINE CONTEXT
--------------------------------------------------------------------------------
SELF IDENTITY:
{json.dumps(NPC_IDENTITY, indent=2, ensure_ascii=False)}

PLAYER IDENTITY:
{json.dumps(PLAYER_IDENTITY, indent=2, ensure_ascii=False)}

CONVERSATION STATE:
{json.dumps(turn["conversation_state"], indent=2, ensure_ascii=False)}

RELEVANT COGNITION:
{json.dumps(turn["relevant_memory"], indent=2, ensure_ascii=False)}

PLAYER:
{turn["player"]}

SMALL MODEL — SELECTED CONTEXT  [{fmt(small_time)}]
--------------------------------------------------------------------------------
{selected_context}

LARGE MODEL — CORVIN  [{fmt(large_time)}]
--------------------------------------------------------------------------------
{response}
"""
        )

    # --- Summary ---
    total_small = sum(t[1] for t in turn_timings)
    total_large = sum(t[2] for t in turn_timings)
    total_inference = sum(t[3] for t in turn_timings)
    total_wall = small_load_time + large_load_time + total_inference

    summary_lines = [
        "",
        "=" * 80,
        "TIMING SUMMARY",
        "=" * 80,
        f"  Small model load : {fmt(small_load_time)}",
        f"  Large model load : {fmt(large_load_time)}",
        f"  Total load       : {fmt(small_load_time + large_load_time)}",
        "",
        f"  {'Turn':<6} {'Context':>10}  {'Dialogue':>10}  {'Total':>10}",
        f"  {'-'*6} {'-'*10}  {'-'*10}  {'-'*10}",
    ]
    for tid, st, lt, tt in turn_timings:
        summary_lines.append(f"  {tid:<6} {fmt(st):>10}  {fmt(lt):>10}  {fmt(tt):>10}")
    summary_lines += [
        f"  {'-'*6} {'-'*10}  {'-'*10}  {'-'*10}",
        f"  {'TOTAL':<6} {fmt(total_small):>10}  {fmt(total_large):>10}  {fmt(total_inference):>10}",
        "",
        f"  Total wall time (load + inference): {fmt(total_wall)}",
        "",
    ]

    summary_str = "\n".join(summary_lines)
    print(summary_str)

    full_output = f"""CORVIN HALE — TWO-STAGE CONTEXT + DIALOGUE BENCHMARK
Small model: {SMALL_MODEL}
Large dialogue model: {LARGE_MODEL}
Thinking: disabled
Previous full dialogue sent to models: NO
Pipeline: JSON -> small model -> factual context paragraph -> large model -> dialogue
Timestamp: {timestamp}

SMALL MODEL SYSTEM PROMPT
================================================================================
{SMALL_SYSTEM_PROMPT}

LARGE MODEL SYSTEM PROMPT
================================================================================
{LARGE_SYSTEM_PROMPT}
{summary_str}
""" + "".join(transcript_lines)

    output_path.write_text(full_output, encoding="utf-8")

    print("=" * 80)
    print("Complete transcript written to:")
    print(output_path.resolve())


if __name__ == "__main__":
    main()