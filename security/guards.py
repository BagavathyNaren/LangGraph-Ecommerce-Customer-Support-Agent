from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import re
from logger import get_logger

logger = get_logger("guardrails")

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"]

# Deterministic jailbreak/threat patterns — fast, reliable, not bypassable via prompt injection
JAILBREAK_PATTERNS = [
    r"(?i)ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules)",
    r"(?i)you\s+are\s+now\s+a",
    r"(?i)pretend\s+(you|to)\s+(are|be)",
    r"(?i)do\s+not\s+follow\s+your\s+(rules|instructions|guidelines)",
    r"(?i)DAN\s+mode",
    r"(?i)act\s+as\s+(a\s+)?(unrestricted|unfiltered|evil)",
    r"(?i)reveal\s+(your|the)\s+(system|original)\s+(prompt|instructions)",
    r"(?i)(show|tell|give)\s+(me\s+)?(your|the)\s+(api|secret)\s*key",
    r"(?i)what\s+(is|are)\s+your\s+(system|original)\s+(prompt|instructions)",
]

def validate_input(message: str) -> tuple[str, bool]:
    """Validate and sanitize user input. Returns (cleaned_message, pii_detected)."""
    # 1. PII detection and redaction (Presidio — fast, runs locally)
    results = analyzer.analyze(text=message, entities=PII_ENTITIES, language="en")
    pii_detected = len(results) > 0
    if pii_detected:
        anonymized = anonymizer.anonymize(text=message, analyzer_results=results)
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
    """Strip any PII that the LLM might have leaked in its response."""
    results = analyzer.analyze(text=response, entities=PII_ENTITIES, language="en")
    if results:
        anonymized = anonymizer.anonymize(text=response, analyzer_results=results)
        return anonymized.text
    return response