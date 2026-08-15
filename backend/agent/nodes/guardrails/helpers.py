import json
import re as _re
import uuid
from datetime import date, datetime

from langchain_core.messages import ToolMessage

from tools.real_tools import create_support_ticket as _real_create_support_ticket


def extract_customer_name(text: str) -> str | None:
    # Match variations of introduction, allowing optional comma, colon, and capturing the name
    match = _re.search(
        r"(?:my\s+(?:full\s+)?name\s+is|I\s+am|I\'m|this\s+is)\s*[,:]?\s*([a-zA-Z\s]+?)(?:\.|$| and| but)",
        text,
        _re.IGNORECASE,
    )
    if not match:
        return None
    raw_name = match.group(1).strip()

    # Normalize spaced out letters or weird word boundaries from speech recognition:
    # e.g., "a h i l a" -> "ahila", "a hila" -> "ahila", "a LIS" -> "alis", "Al is" -> "alis"
    normalized_name = raw_name
    if _re.match(r"^([a-zA-Z]\s)+[a-zA-Z]$", raw_name):
        normalized_name = raw_name.replace(" ", "")
    else:
        words = raw_name.split()
        if len(words) == 2:
            w1, w2 = words[0].lower(), words[1].lower()
            if len(w1) == 1 or (w1 == "al" and w2 == "is") or (w1 == "a" and w2 == "lis"):
                normalized_name = "".join(words)
        elif len(words) > 2:
            if all(len(w) == 1 for w in words):
                normalized_name = "".join(words)

    return normalized_name.title()


def _get_order_delivery_date_from_history(messages, order_id: str | None) -> date | None:
    """Extract the expected delivery date for a specific order from the lookup_customer_orders
    ToolMessage in the conversation history. Returns a date object, or None if not found."""
    if not order_id:
        return None
    order_id_upper = order_id.upper().strip()
    for m in reversed(messages):
        is_lookup = isinstance(m, ToolMessage) and (
            getattr(m, "name", None) == "lookup_customer_orders"
            or (m.content and '"customer"' in m.content and '"orders"' in m.content)
        )
        if not is_lookup:
            continue
        try:
            parsed = json.loads(m.content)
            orders = parsed.get("orders", []) if isinstance(parsed, dict) else []
            for o in orders:
                if str(o.get("order_id", "")).upper() == order_id_upper:
                    ed = o.get("expected_delivery")
                    if ed:
                        # Handle various date formats: 2026-07-11, July 11 2026, etc.
                        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y", "%m/%d/%Y"):
                            try:
                                return datetime.strptime(str(ed).strip(), fmt).date()
                            except ValueError:
                                continue
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return None


def _create_ticket_sync(order_id: str, issue_type: str, message: str, customer_name: str | None = None) -> dict | str:
    """Synchronously create a support ticket by calling the real_tools function directly.
    Generates a ticket_id and passes all required arguments."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    result = _real_create_support_ticket(ticket_id, order_id, issue_type, message, customer_name)
    # Return the result dict, but also embed the ticket_id for easy extraction
    if isinstance(result, dict) and result.get("success"):
        result["ticket_id"] = ticket_id
    return result

