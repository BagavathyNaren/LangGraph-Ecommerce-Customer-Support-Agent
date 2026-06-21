log_path = r"C:/Users/Bagav/.gemini/antigravity/brain/92965a64-7050-48f3-8e01-269ce37bb3c0/.system_generated/steps/10391/output.txt"

with open(log_path, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print("Searching log for ORD4904:")
for i, line in enumerate(lines):
    if "ORD4904" in line or "ORD7442" in line or "narenhifi" in line:
        print(f"Line {i + 1}: {line.strip()}")
