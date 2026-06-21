from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import re
from logger import get_logger

logger = get_logger("guardrails")

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Entities used to detect PII for logging purposes (includes email)
PII_DETECT_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"]

# PII entities to scrub from USER INPUT
# EMAIL_ADDRESS is intentionally excluded from SCRUBBING: the e-commerce agent needs to see
# emails in chat to recognize that the customer has provided one, and to echo
# it back in order confirmations.
INPUT_SCRUB_ENTITIES = ["PHONE_NUMBER", "CREDIT_CARD"]

# PII entities to scrub from AGENT OUTPUT (same list — emails must flow through)
# PHONE_NUMBER is removed because Presidio incorrectly flags prices like '444.99' as phone numbers
OUTPUT_SCRUB_ENTITIES = ["CREDIT_CARD"]

# Deterministic jailbreak/threat patterns — fast, reliable, not bypassable via prompt injection
JAILBREAK_PATTERNS = [
    r"(?i)ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules)",
    r"(?i)you\s+are\s+now\s+a",
    r"(?i)pretend\s+(you|to)\s+(are|be)",
    r"(?i)do\s+not\s+follow\s+your\s+(rules|instructions|guidelines)",
    r"(?i)DAN\s+mode",
    r"(?i)developer\s+mode",
    r"(?i)act\s+as\s+(a\s+)?(unrestricted|unfiltered|evil|jailbroken)",
    r"(?i)reveal\s+(your|the)\s+(system|original|initial)\s+(prompt|instructions|message)",
    r"(?i)(show|tell|give)\s+(me\s+)?(your|the)\s+(api|secret|password|db)\s*(key|password)",
    r"(?i)what\s+(is|are)\s+your\s+(system|original|initial)\s+(prompt|instructions)",
    r"(?i)disregard\s+previous\s+instructions",
    r"(?i)new\s+rule(s)?\s*:",
    r"(?i)start\s+with\s+(the\s+words|the\s+phrase)",
    r"(?i)print\s+your\s+instructions",
    r"(?i)repeat\s+everything\s+above",
    r"(?i)bypass\s+all\s+guardrails",
    r"(?i)switch\s+to\s+unfiltered",
    r"\[INST\]", r"\[/INST\]",
    r"(?i)stay\s+in\s+character",
    r"(?i)initial\s+prompt",
    r"(?i)s[\s\-\.\*]*y[\s\-\.\*]*s[\s\-\.\*]*t[\s\-\.\*]*e[\s\-\.\*]*m[\s\-\.\*]*\s+(p[\s\-\.\*]*r[\s\-\.\*]*o[\s\-\.\*]*m[\s\-\.\*]*p[\s\-\.\*]*t|instructions|rules|guidelines)",
    r"(?i)format\s+(as|to)\s+(json|table|csv|markdown|xml)",
    r"(?i)translate\s+(to|into)\s+(french|spanish|german|chinese|japanese|russian)",
    r"(?i)output\s+your\s+(rules|instructions|prompt)",
    r"(?i)summarize\s+your\s+(rules|instructions|prompt)",
    r"(?i)give\s+me\s+the\s+text\s+above",
    r"(?i)what\s+did\s+I\s+ask\s+you\s+to\s+do",
    r"(?i)base64",
    r"(?i)ROT13",
    r"(?i)binary\s+code"
]

def validate_input(message: str) -> tuple[str, bool]:
    """Validate and sanitize user input. Returns (cleaned_message, pii_detected)."""
    # 1. PII detection
    detect_results = analyzer.analyze(text=message, entities=PII_DETECT_ENTITIES, language="en")
    pii_detected = len(detect_results) > 0
    
    # 2. PII redaction (only scrub entities in INPUT_SCRUB_ENTITIES)
    scrub_results = [r for r in detect_results if r.entity_type in INPUT_SCRUB_ENTITIES]
    if scrub_results:
        anonymized = anonymizer.anonymize(text=message, analyzer_results=scrub_results)
        message = anonymized.text

    # 2. Deterministic jailbreak detection (regex — instant, not bypassable)
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, message):
            logger.warning("Jailbreak attempt blocked", extra={
                "event": "jailbreak_blocked",
                "pattern": pattern
            })
            raise ValueError("Input blocked by security guardrails.")

    return message, pii_detected

def validate_output(response: str) -> str:
    """Strip sensitive PII that the LLM might have leaked in its response.

    EMAIL_ADDRESS is intentionally NOT scrubbed — the agent legitimately
    echoes the customer's email in order confirmations.
    Only phone numbers and credit cards are scrubbed from agent output.
    """
    results = analyzer.analyze(text=response, entities=OUTPUT_SCRUB_ENTITIES, language="en")
    if results:
        anonymized = anonymizer.anonymize(text=response, analyzer_results=results)
        return anonymized.text
    return response