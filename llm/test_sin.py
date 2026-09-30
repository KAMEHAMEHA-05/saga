#!/usr/bin/env python3
"""
Corvin Hale conversational benchmark — direct JSON to dialogue.

Pipeline: raw JSON cognition -> single model -> NPC dialogue
No intermediate context selection step.
Streaming with TPS measurement.
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:1.7b"

SYSTEM_PROMPT = """You are an NPC in a fantasy RPG speaking directly to a person standing in front of you.

You will receive:
- Your identity and personality
- The player's identity
- The current conversation state
- Relevant facts about the world as JSON (COGNITION)
- The player's latest utterance

Your job is to respond as your character, out loud, in natural speech.

COGNITION RULES:
- Use ONLY facts present in the COGNITION block and CONVERSATION STATE.
- If the cognition block is empty or contains nothing relevant, respond from your personality alone.
- Do not invent facts, people, events, or relationships not present in the data.
- Do not reveal facts your character would not share with a stranger.
- Do not volunteer information that was not asked about.

CONVERSATION:
- Respond primarily to the player's latest utterance.
- React to statements as statements; do not treat everything as a question.
- If the player makes an accusation, respond to the accusation.
- If the player draws a conclusion, react to that conclusion.
- If the player misunderstands something, correct them naturally.
- Do not restart the conversation.
- Do not summarize the entire topic unless explicitly asked.

STYLE:
- Speak in first person as your character. Always.
- Never narrate actions or describe the scene.
- Never refer to yourself in third person.
- Speak only your words. Nothing else.
- Most replies should be 1-3 sentences.
- Use natural conversational language.
- Do not end responses with questions or solicitations for agreement.
- Do not use bullet points or lists in spoken dialogue.
- Do not use generic assistant phrases such as:
  "That's an interesting question."
  "Let me know if you want to know more."
  "I'd be happy to explain."
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
            "faction": {"name": "River Guild", "public_goal": "Protect river commerce"},
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
            "person": {"name": "Helena", "relationship_to_corvin": "rival", "role": "Merchant"},
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
            "event": {"name": "Missing Caravan", "cargo": "silver", "location": "Eastern Road", "status": "missing"},
            "person": {"name": "Tomas Reed", "role": "caravan guard", "employer": "River Guild", "last_known_assignment": "guarding the missing caravan"},
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
            "event": {"name": "Missing Caravan", "cargo": "silver", "location": "Eastern Road", "status": "missing"},
            "sighting": {"subject": "Iron Covenant soldiers", "location": "Eastern Road", "relation_to_caravan": "seen near the road around the relevant period"},
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
            "faction": {"name": "Iron Covenant", "leader": "Aldric Voss"},
            "person": {"name": "Aldric Voss", "role": "Leader of the Iron Covenant", "distrusts": ["River Guild"]},
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


# ---------------------------------------------------------------------------
# Tool definitions (MCP-style): the model can call these to fetch extra info.
# In a real engine these would query your knowledge graph.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledge",
            "description": (
                "Query the world knowledge graph for information about a person, "
                "faction, event, or place. Use this when the player asks about "
                "something and the supplied cognition does not contain enough detail "
                "to answer properly. Returns a JSON object with the relevant facts, "
                "or an empty object if nothing is found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["person", "faction", "event", "place"],
                        "description": "The category of the entity to look up.",
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the entity to look up.",
                    },
                },
                "required": ["entity_type", "name"],
            },
        },
    }
]

# Stub knowledge base — replace with real graph queries later.
KNOWLEDGE_BASE = {
    "person": {
        "Helena": {"name": "Helena", "role": "Merchant", "relationship_to_corvin": "rival", "known_for": "undercutting Guild trade routes"},
        "Tomas Reed": {"name": "Tomas Reed", "role": "caravan guard", "employer": "River Guild", "employed_by": "Corvin Hale", "last_known_assignment": "guarding the missing caravan"},
        "Aldric Voss": {"name": "Aldric Voss", "role": "Leader of the Iron Covenant", "distrusts": ["River Guild"]},
    },
    "faction": {
        "River Guild": {"name": "River Guild", "public_goal": "Protect river commerce", "grain_trade": "The Guild is involved in grain trade."},
        "Iron Covenant": {"name": "Iron Covenant", "leader": "Aldric Voss", "known_for": "military discipline and territorial expansion"},
    },
    "event": {
        "Missing Caravan": {"name": "Missing Caravan", "cargo": "silver", "location": "Eastern Road", "status": "missing"},
    },
    "place": {
        "Eastern Road": {"name": "Eastern Road", "description": "A major trade route east of the city, known for bandit activity."},
    },
}


def handle_tool_call(tool_name, tool_args):
    """Execute a tool call and return the result as a JSON string."""
    if tool_name == "query_knowledge":
        entity_type = tool_args.get("entity_type", "")
        name = tool_args.get("name", "")
        result = KNOWLEDGE_BASE.get(entity_type, {}).get(name, {})
        return json.dumps(result) if result else json.dumps({"result": "No information found."})
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def build_user_message(turn):
    return f"""YOUR IDENTITY:
{json.dumps(NPC_IDENTITY, indent=2, ensure_ascii=False)}

PLAYER IDENTITY:
{json.dumps(PLAYER_IDENTITY, indent=2, ensure_ascii=False)}

CONVERSATION STATE:
{json.dumps(turn["conversation_state"], indent=2, ensure_ascii=False)}

COGNITION:
{json.dumps(turn["relevant_memory"], indent=2, ensure_ascii=False)}

PLAYER:
"{turn["player"]}"

Respond only with what your character would naturally say out loud.
If you need more information to answer properly, use the query_knowledge tool first.
"""


def stream_request(messages, tools=None, num_predict=150):
    """
    Stream a request. Handles one round of tool calls if the model requests them,
    then streams the final dialogue response.

    Returns:
        text          — final spoken response
        tool_calls    — list of (name, args, result) for any tools called
        tokens        — token count of the final streamed response
        ttft          — time to first token of the final response
        total_time    — wall time for the entire call (including tool round-trip)
        tps           — tokens/sec of the final response
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {"temperature": 0.7, "num_predict": num_predict},
    }
    if tools:
        payload["tools"] = tools

    def do_request(p):
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(p).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=300)
        except urllib.error.URLError as exc:
            raise SystemExit(f"\nCould not connect to Ollama: {exc}")

    tool_calls_made = []
    t_wall_start = time.perf_counter()

    # --- First pass: may be a tool call or direct dialogue ---
    accumulated_tool_calls = {}  # index -> {name, arguments_str}
    first_pass_text = ""
    is_tool_call = False

    with do_request(payload) as resp:
        for raw in resp:
            chunk = json.loads(raw.decode("utf-8").strip())
            msg = chunk.get("message", {})

            # Accumulate tool call deltas
            for tc in msg.get("tool_calls", []):
                idx = tc.get("index", 0)
                fn = tc.get("function", {})
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {"name": "", "arguments_str": ""}
                accumulated_tool_calls[idx]["name"] += fn.get("name", "")
                accumulated_tool_calls[idx]["arguments_str"] += fn.get("arguments", "")
                is_tool_call = True

            # Plain text in first pass (no tool call)
            if not is_tool_call:
                first_pass_text += msg.get("content", "")

            if chunk.get("done"):
                break

    # --- If tool calls were requested, execute them and do a second pass ---
    if is_tool_call:
        # Execute each tool call
        tool_results_messages = list(messages)
        # Add assistant message with tool calls in Ollama format
        tool_calls_for_msg = []
        for idx in sorted(accumulated_tool_calls):
            tc = accumulated_tool_calls[idx]
            try:
                args = json.loads(tc["arguments_str"])
            except json.JSONDecodeError:
                args = {}
            result = handle_tool_call(tc["name"], args)
            tool_calls_made.append((tc["name"], args, result))
            tool_calls_for_msg.append({
                "function": {"name": tc["name"], "arguments": args}
            })
            print(f"\n  [tool] {tc['name']}({args}) -> {result}")

        tool_results_messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": tool_calls_for_msg,
        })
        for name, args, result in tool_calls_made:
            tool_results_messages.append({
                "role": "tool",
                "content": result,
            })

        # Second pass: stream the actual dialogue
        payload2 = {
            "model": MODEL,
            "messages": tool_results_messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.7, "num_predict": num_predict},
        }

        final_text = ""
        token_count = 0
        ttft = None
        t_stream_start = time.perf_counter()

        with do_request(payload2) as resp:
            for raw in resp:
                chunk = json.loads(raw.decode("utf-8").strip())
                token = chunk.get("message", {}).get("content", "")
                if token:
                    if ttft is None:
                        ttft = time.perf_counter() - t_stream_start
                    print(token, end="", flush=True)
                    final_text += token
                    token_count += 1
                if chunk.get("done"):
                    break

        total_time = time.perf_counter() - t_wall_start
        stream_time = time.perf_counter() - t_stream_start
        tps = token_count / stream_time if stream_time > 0 else 0.0
        return final_text.strip(), tool_calls_made, token_count, ttft or 0.0, total_time, tps

    else:
        # No tool call — stream first_pass_text was accumulated silently,
        # but we need to redo with streaming printed.
        # Re-run streaming and print tokens this time.
        final_text = ""
        token_count = 0
        ttft = None
        t_stream_start = time.perf_counter()

        with do_request(payload) as resp:
            for raw in resp:
                chunk = json.loads(raw.decode("utf-8").strip())
                token = chunk.get("message", {}).get("content", "")
                if token:
                    if ttft is None:
                        ttft = time.perf_counter() - t_stream_start
                    print(token, end="", flush=True)
                    final_text += token
                    token_count += 1
                if chunk.get("done"):
                    break

        total_time = time.perf_counter() - t_wall_start
        stream_time = time.perf_counter() - t_stream_start
        tps = token_count / stream_time if stream_time > 0 else 0.0
        return final_text.strip(), [], token_count, ttft or 0.0, total_time, tps


def warmup_model():
    print(f"Loading {MODEL}...", end=" ", flush=True)
    t0 = time.perf_counter()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False,
        "think": False,
        "options": {"num_predict": 1},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"\nCould not connect to Ollama: {exc}")
    elapsed = time.perf_counter() - t0
    print(f"ready in {elapsed:.2f}s")
    return elapsed


def fmt(s):
    return f"{s:.2f}s"


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = MODEL.replace("/", "_").replace(":", "_")
    output_path = Path(f"corvin_direct_{safe_model}_{timestamp}.script")

    print(f"Running {len(TURNS)}-turn direct JSON→dialogue benchmark...")
    print(f"Model  : {MODEL}")
    print(f"Tools  : query_knowledge (stub)")
    print()

    load_time = warmup_model()
    print()

    transcript_lines = []
    turn_timings = []

    for turn in TURNS:
        print(f"─── TURN {turn['id']} {'─' * 60}")
        print(f"PLAYER: {turn['player']}")
        print()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_message(turn)},
        ]

        print("CORVIN: ", end="", flush=True)
        text, tool_calls, tokens, ttft, total_time, tps = stream_request(
            messages, tools=TOOLS, num_predict=150
        )
        print()
        tool_summary = ""
        if tool_calls:
            tool_summary = " | tools: " + ", ".join(
                f"{name}({args.get('name','?')})" for name, args, _ in tool_calls
            )
        print(f"        [{tokens} tok | ttft {ttft:.2f}s | {total_time:.2f}s | {tps:.1f} t/s{tool_summary}]")
        print()

        turn_timings.append({
            "id": turn["id"],
            "tokens": tokens,
            "ttft": ttft,
            "time": total_time,
            "tps": tps,
            "tool_calls": tool_calls,
        })

        tool_block = ""
        if tool_calls:
            tool_block = "\nTOOL CALLS\n" + "-" * 40 + "\n"
            for name, args, result in tool_calls:
                tool_block += f"  {name}({json.dumps(args)}) ->\n  {result}\n"

        transcript_lines.append(
            f"""
{'=' * 80}
TURN {turn['id']}  [{tokens} tok | ttft {ttft:.2f}s | {total_time:.2f}s | {tps:.1f} t/s]
{'=' * 80}

PLAYER:
{turn['player']}

COGNITION:
{json.dumps(turn['relevant_memory'], indent=2)}
{tool_block}
CORVIN:
{text}
"""
        )

    # --- Summary ---
    total_tokens = sum(t["tokens"] for t in turn_timings)
    total_time   = sum(t["time"]   for t in turn_timings)
    total_tool   = sum(len(t["tool_calls"]) for t in turn_timings)
    avg_tps      = total_tokens / total_time if total_time > 0 else 0

    summary = [
        "",
        "=" * 80,
        "TIMING SUMMARY",
        "=" * 80,
        f"  Model      : {MODEL}",
        f"  Model load : {load_time:.2f}s",
        f"  Tool calls : {total_tool} total across all turns",
        "",
        f"  {'Turn':<5} {'Tokens':>7} {'t/s':>8} {'ttft':>7} {'Time':>9}  Tools",
        f"  {'-'*5} {'-'*7} {'-'*8} {'-'*7} {'-'*9}  {'-'*20}",
    ]
    for t in turn_timings:
        tools_str = ", ".join(
            f"{n}({a.get('name','?')})" for n, a, _ in t["tool_calls"]
        ) if t["tool_calls"] else "-"
        summary.append(
            f"  {t['id']:<5} {t['tokens']:>7} {t['tps']:>7.1f}/s "
            f"{t['ttft']:>6.2f}s {t['time']:>8.2f}s  {tools_str}"
        )
    summary += [
        f"  {'-'*5} {'-'*7} {'-'*8} {'-'*7} {'-'*9}",
        f"  {'TOT':<5} {total_tokens:>7} {avg_tps:>7.1f}/s {'':>7} {total_time:>8.2f}s",
        "",
        f"  Total wall time (load + inference): {load_time + total_time:.2f}s",
        "",
    ]
    summary_str = "\n".join(summary)
    print(summary_str)

    full_output = (
        f"CORVIN HALE — DIRECT JSON→DIALOGUE BENCHMARK\n"
        f"Model: {MODEL}\n"
        f"Pipeline: raw JSON -> single model -> dialogue\n"
        f"Tools: query_knowledge (stub)\n"
        f"Streaming: YES\n"
        f"Timestamp: {timestamp}\n\n"
        f"SYSTEM PROMPT\n{'=' * 80}\n{SYSTEM_PROMPT}\n"
        f"{summary_str}\n"
        + "".join(transcript_lines)
    )

    output_path.write_text(full_output, encoding="utf-8")
    print("=" * 80)
    print(f"Transcript written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()