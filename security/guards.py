import os
from guardrails import Guard
from guardrails.hub import ToxicLanguage, DetectJailbreak

os.environ["GUARDRAILS_AI_API_KEY"] = os.environ.get("GUARDRAILS_AI_API_KEY", "")

input_guard = Guard().use_many(
    DetectJailbreak(on_fail="exception"),
    ToxicLanguage(threshold=0.5, validation_method="sentence", on_fail="exception"),
)

output_guard = Guard().use_many(
    ToxicLanguage(threshold=0.5, validation_method="sentence", on_fail="exception"),
)

def validate_input(message: str) -> str:
    try:
        result = input_guard.validate(message)
        return result.validated_output
    except Exception as e:
        raise ValueError(f"Input blocked by guardrails: {str(e)}")

def validate_output(response: str) -> str:
    try:
        result = output_guard.validate(response)
        return result.validated_output
    except Exception as e:
        raise ValueError(f"Output blocked by guardrails: {str(e)}")