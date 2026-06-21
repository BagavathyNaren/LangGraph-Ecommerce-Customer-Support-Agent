import json

log_path = r"C:/Users/Bagav/.gemini/antigravity/brain/92965a64-7050-48f3-8e01-269ce37bb3c0/.system_generated/logs/transcript.jsonl"

try:
    with open(log_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    print(f"Total steps in transcript: {len(lines)}")
    user_inputs = []

    for idx, line in enumerate(lines):
        try:
            data = json.loads(line)
            step_type = data.get("type", "")
            source = data.get("source", "")
            content = data.get("content", "")

            # Print steps of type USER_INPUT or PLANNER_RESPONSE
            if step_type in ["USER_INPUT", "PLANNER_RESPONSE"] or source in ["USER_EXPLICIT", "MODEL"]:
                # Print last 30 messages
                user_inputs.append((idx, step_type, source, content))
        except Exception:
            pass

    print("\n--- RECENT CHAT MESSAGES ---")
    for idx, step_type, source, content in user_inputs[-30:]:
        print(f"[{idx}] {source} ({step_type}): {content[:300]}")
        print("-" * 50)
except Exception as e:
    print(f"Error reading transcript: {e}")
