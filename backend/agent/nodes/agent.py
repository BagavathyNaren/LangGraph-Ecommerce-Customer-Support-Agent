import ast as _ast
import json
import re as _re
import uuid
from datetime import date, datetime

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from agent.nodes.guardrails.helpers import (
    _create_ticket_sync,
    _get_order_delivery_date_from_history,
    extract_customer_name,
)
from agent.nodes.guardrails.prompts import AGENT_SYSTEM_PROMPT
from agent.state import AgentState
from infra.logger import get_logger
from tools.agent_tools import AGENT_TOOLS
from tools.real_tools import create_support_ticket as _real_create_support_ticket

logger = get_logger("ecommerce-agent")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True, request_timeout=30)
agent_llm = llm.bind_tools(AGENT_TOOLS)

MAX_REACT_ITERATIONS = 15  # Hard safety cap to prevent infinite loops


def agent_node(state: AgentState) -> AgentState:
    """The agent LLM decides what to do — call tools or respond directly with pruning."""
    # Reset intent and order_id at the start of a new user turn
    new_intent = None
    new_order_id = None
    react_iterations = state.get("react_iterations", 0)

    is_new_user_turn = isinstance(state["messages"][-1], HumanMessage)

    # If we are NOT in a new turn (e.g. still in a tool loop), keep existing values
    if not is_new_user_turn:
        new_intent = state.get("intent")
        new_order_id = state.get("order_id")
        react_iterations += 1
    else:
        # New user message — reset the counter
        react_iterations = 0
        new_order_id = state.get("order_id")
        
    # Always try to extract order ID from the most recent human message
    import re as _re_tmp
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            match = _re_tmp.search(r"ORD\d{3,10}", m.content.upper())
            if match:
                new_order_id = match.group(0)
            break

    # ═══ SAFETY CAP: Prevent infinite ReAct loops ═══
    if react_iterations >= MAX_REACT_ITERATIONS:
        logger.warning(
            "ReAct loop cap reached", extra={"event": "react_loop_cap_reached", "iterations": react_iterations}
        )
        fallback = AIMessage(
            content="I'm sorry, I encountered an issue while processing your request. I am escalating your case to a human support representative immediately."
        )
        return {
            "messages": [fallback],
            "intent": new_intent,
            "order_id": new_order_id,
            "react_iterations": 0,
            "escalated": True,  # Force immediate escalation routing
        }

    # PERSISTENCE OPTIMIZATION: Keep only the last 15 messages in the DB state
    # We use a "Safe Cut" approach to ensure we don't break tool-call chains.
    messages_to_remove = []
    if len(state["messages"]) > 15:
        # Determine the cutoff point
        cutoff = len(state["messages"]) - 15

        # Find the nearest HumanMessage at or after the cutoff to ensure a clean start
        safe_cutoff = 0
        for i in range(cutoff, len(state["messages"])):
            if isinstance(state["messages"][i], HumanMessage):
                safe_cutoff = i
                break

        if safe_cutoff > 0:
            for i in range(safe_cutoff):
                m = state["messages"][i]
                messages_to_remove.append(RemoveMessage(id=m.id))

    from datetime import datetime
    dynamic_prompt = AGENT_SYSTEM_PROMPT + f"\n\nCRITICAL CONTEXT: Today's current date is {datetime.now().strftime('%B %d, %Y')}."
    messages = [SystemMessage(content=dynamic_prompt)] + state["messages"]
    response = agent_llm.invoke(messages)

    # ── Always resolve last_msg and current_customer_name first ──
    # These must be initialized before ANY guardrail runs, including Guardrail D
    # which fires on plain-text responses (no tool_calls) and would otherwise crash.
    last_msg = None
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            last_msg = m
            break

    countries = [
        "japan",
        "india",
        "uae",
        "uk",
        "usa",
        "us",
        "united arab emirates",
        "united kingdom",
        "united states",
        "china",
        "canada",
        "germany",
        "france",
        "australia",
        "singapore",
        "spain",
        "italy",
        "brazil",
        "mexico",
    ]

    # ── Strict Country Constraints Programmatic Reject Guardrail ──
    # Check if the user mentions an unsupported country in their last message
    if isinstance(last_msg, HumanMessage):
        last_msg_lower = last_msg.content.lower()
        supported_map = {
            "uae": ["uae", "united arab emirates", "emirates"],
            "japan": ["japan", "jp"],
            "us": ["us", "usa", "united states", "america"],
            "uk": ["uk", "united kingdom", "britain", "gb"],
            "india": ["india", "in"],
        }
        unsupported_countries = [
            "china",
            "canada",
            "germany",
            "france",
            "australia",
            "singapore",
            "spain",
            "italy",
            "brazil",
            "mexico",
            "russia",
            "netherlands",
            "sweden",
            "switzerland",
            "belgium",
            "norway",
            "denmark",
            "finland",
            "ireland",
            "austria",
            "new zealand",
            "south africa",
            "korea",
        ]
        detected_unsupported = None
        for uc in unsupported_countries:
            if _re.search(r"\b" + _re.escape(uc) + r"\b", last_msg_lower):
                has_supported = False
                for _sc, keywords in supported_map.items():
                    for kw in keywords:
                        if _re.search(r"\b" + _re.escape(kw) + r"\b", last_msg_lower):
                            has_supported = True
                            break
                    if has_supported:
                        break
                if not has_supported:
                    detected_unsupported = uc.title()
                    break
        if detected_unsupported:
            logger.info(
                "Programmatically rejecting unsupported country",
                extra={"event": "country_rejected", "country": detected_unsupported},
            )
            response.tool_calls = []
            response.content = f"We only support ordering, customer registration, and checking product catalogs for UAE, Japan, US, UK, and India. Unfortunately, {detected_unsupported} is not supported."
            return {
                "messages": [response] + messages_to_remove,
                "intent": new_intent,
                "order_id": new_order_id,
                "react_iterations": react_iterations,
            }

    # ═══ GUARDRAIL A: Extract the CURRENT customer's name from the latest introduction ═══
    # This prevents the LLM from using a stale name (e.g. "Chan") when "Mumtaj" just introduced herself.
    current_customer_name = None
    if isinstance(last_msg, HumanMessage):
        current_customer_name = extract_customer_name(last_msg.content)
    # If the latest HumanMessage isn't an introduction, check the most recent introduction in history
    if not current_customer_name:
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                name = extract_customer_name(m.content)
                if name:
                    current_customer_name = name
                    break

    # Programmatic Guardrails for First-Turn Country and Customer Lookup
    if response.tool_calls:
        # 0. Guard against location lookups!
        # If the LLM incorrectly calls lookup_customer_orders with a location statement, strip it and inject search_retailer_platform
        # (last_msg, countries, current_customer_name already initialized above)
        # ═══ GUARDRAIL B: Correct stale customer names in lookup_customer_orders calls ═══
        # If the user just introduced as "Mumtaj" but the LLM calls lookup("Chan"), fix it.
        if current_customer_name and isinstance(last_msg, HumanMessage) and "my name is" in last_msg.content.lower():
            for tc in response.tool_calls:
                if tc["name"] == "lookup_customer_orders":
                    called_name = tc.get("args", {}).get("customer_name", "").strip()
                    if called_name.lower() != current_customer_name.lower():
                        logger.warning(
                            "Correcting stale customer name in lookup",
                            extra={
                                "event": "stale_name_corrected",
                                "stale_name": called_name,
                                "correct_name": current_customer_name,
                            },
                        )
                        tc["args"]["customer_name"] = current_customer_name

        # ═══ GUARDRAIL C: Deduplicate tool calls already executed in this turn ═══
        # Prevents the same tool+args from firing repeatedly (e.g. lookup_customer_orders("Chan") x50)
        already_executed = set()
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                break  # Only look within the current turn (since last user message)
            if isinstance(m, ToolMessage):
                # Find the matching AIMessage tool call to get the name+args
                pass  # We'll match by checking AIMessage tool_calls below
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    key = f"{tc['name']}:{json.dumps(tc.get('args', {}), sort_keys=True)}"
                    already_executed.add(key)

        if already_executed:
            deduped_tool_calls = []
            for tc in response.tool_calls:
                key = f"{tc['name']}:{json.dumps(tc.get('args', {}), sort_keys=True)}"
                if key in already_executed:
                    logger.info(
                        "Stripping duplicate tool call",
                        extra={"event": "tool_call_deduped", "tool": tc["name"], "tool_args": tc.get("args", {})},
                    )
                else:
                    deduped_tool_calls.append(tc)
            response.tool_calls = deduped_tool_calls

        for tc in list(response.tool_calls):
            if tc["name"] == "lookup_customer_orders":
                customer_name = tc.get("args", {}).get("customer_name", "").strip().lower()
                is_location = False
                if customer_name in countries:
                    is_location = True
                elif any(customer_name.startswith(p) for p in ["in ", "from "]):
                    is_location = True
                elif any(c in customer_name for c in countries):
                    is_location = True

                if is_location:
                    response.tool_calls.remove(tc)

                    # Extract the query/product they wanted from the conversation history
                    query = None
                    for m in reversed(state["messages"]):
                        if isinstance(m, HumanMessage):
                            content_lower = m.content.lower()
                            if "buy" in content_lower or "purchase" in content_lower or "order" in content_lower:
                                match = _re.search(
                                    r"(?:buy|purchase|order|want|get)\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\.|$)",
                                    content_lower,
                                )
                                if match:
                                    query = match.group(1).strip()
                                    break

                    # Extract the country
                    country = "Japan"  # default fallback
                    for c in countries:
                        if c in customer_name or (isinstance(last_msg, HumanMessage) and c in last_msg.content.lower()):
                            country = c.title()
                            break
                    if country == "Uae":
                        country = "UAE"
                    elif country == "Uk":
                        country = "UK"
                    elif country == "Usa":
                        country = "USA"

                    if query:
                        # Inject product search tool call
                        response.tool_calls.append(
                            {
                                "name": "search_retailer_platform",
                                "args": {"platform": "amazon", "query": query, "country": country},
                                "id": tc["id"],  # reuse tool call ID to keep graph happy
                                "type": "tool_call",
                            }
                        )
                    else:
                        response.content = f"Thank you for letting me know you are from {country}. How can I assist you with your e-commerce needs today?"

        # 1. Check if the user is introducing themselves in the last message
        is_introduction = False
        if isinstance(last_msg, HumanMessage):
            content_lower = last_msg.content.lower()
            if "my name is" in content_lower:
                is_introduction = True
            elif any(p in content_lower for p in ["i am", "i'm", "this is"]):
                # Exclude location statements like "I am in Japan" or "I am from India"
                if not any(loc in content_lower for loc in ["in ", "from "]):
                    is_introduction = True

        # 2. Check if a country is explicitly provided in the last message
        has_country_in_last_msg = False
        if isinstance(last_msg, HumanMessage):
            content_lower = last_msg.content.lower()
            if any(_re.search(r"\b" + _re.escape(c) + r"\b", content_lower) for c in countries):
                has_country_in_last_msg = True

        # If it is an introduction turn, we STRICTLY forbid parallel search tool calls before lookup runs
        if is_introduction:
            lookup_already_done = False
            for m in reversed(state["messages"]):
                if isinstance(m, HumanMessage):
                    break  # Current turn boundary — stop here
                if isinstance(m, AIMessage) and m.tool_calls:
                    for tc in m.tool_calls:
                        if tc["name"] == "lookup_customer_orders":
                            lookup_already_done = True
                            break
                if lookup_already_done:
                    break

            if not lookup_already_done:
                # Strip any premature search calls and ensure lookup is queued.
                original_tool_calls = list(response.tool_calls)
                filtered_tool_calls = [
                    tc for tc in response.tool_calls if tc["name"] not in ["search_catalog", "search_retailer_platform"]
                ]

                has_lookup = any(tc["name"] == "lookup_customer_orders" for tc in filtered_tool_calls)
                if not has_lookup:
                    intro_name = current_customer_name
                    if not intro_name:
                        intro_name = extract_customer_name(last_msg.content)
                    if intro_name:
                        filtered_tool_calls.append(
                            {
                                "name": "lookup_customer_orders",
                                "args": {"customer_name": intro_name},
                                "id": f"call_{uuid.uuid4().hex[:12]}",
                                "type": "tool_call",
                            }
                        )
                response.tool_calls = filtered_tool_calls

        # Unified Guardrail: Check search tool calls for missing country
        has_search = any(tc["name"] in ["search_catalog", "search_retailer_platform"] for tc in response.tool_calls)
        logger.info(
            "Unified country guardrail status",
            extra={
                "has_search": has_search,
                "has_country_in_last_msg": has_country_in_last_msg,
                "last_msg": last_msg.content if last_msg else None,
            },
        )
        if has_search:
            profile_country = None
            # Check if a previous successful customer lookup established the country
            for m in reversed(state["messages"]):
                if isinstance(m, ToolMessage) and m.name == "lookup_customer_orders" and m.content:
                    c_lower = m.content.lower()
                    if "not found" in c_lower or "not_found" in c_lower:
                        continue  # Skip failed lookups
                    # Primary: parse as JSON (tool returns json.dumps output with double quotes)
                    try:
                        parsed = json.loads(m.content)
                        customer = parsed.get("customer", parsed) if isinstance(parsed, dict) else {}
                        if isinstance(customer, dict):
                            raw_country = customer.get("country")
                            if raw_country and str(raw_country).strip().lower() not in ["none", "null", ""]:
                                profile_country = str(raw_country).strip()
                                logger.info(
                                    "Profile country extracted from lookup",
                                    extra={"event": "profile_country_found", "profile_country": profile_country},
                                )
                                break
                            else:
                                logger.info(
                                    "Customer profile found but country is null/empty",
                                    extra={"event": "profile_country_null", "customer_name": customer.get("name")},
                                )
                    except Exception as parse_err:
                        logger.warning(
                            f"Failed to parse lookup response as JSON: {parse_err}",
                            extra={"event": "profile_country_parse_error"},
                        )
                    # Fallback: regex matching both single and double quote formats
                    if not profile_country:
                        match = _re.search(r'["\']country["\']\s*:\s*["\']([^"\',]+)["\']', m.content, _re.IGNORECASE)
                        if match and match.group(1).lower() not in ["none", "null"]:
                            profile_country = match.group(1).strip()
                            logger.info(
                                "Profile country extracted via regex fallback",
                                extra={"event": "profile_country_regex", "profile_country": profile_country},
                            )
                            break

            if profile_country:
                # OVERRIDE the LLM's chosen country with the profile country.
                # IMPORTANT: ToolCall objects are TypedDicts in langchain-core >= 0.3.
                # In-place mutation (tc["args"]["country"] = ...) does NOT propagate
                # when the message is serialised into LangGraph state. We MUST create
                # a brand-new AIMessage with corrected tool_calls.
                llm_requested_country = None
                new_tool_calls = []
                for tc in response.tool_calls:
                    if tc["name"] in ["search_catalog", "search_retailer_platform"]:
                        llm_requested_country = tc.get("args", {}).get("country", "Unknown")
                        # Build a fresh dict — never mutate the original TypedDict
                        new_tc = {
                            "name": tc["name"],
                            "args": {**tc.get("args", {}), "country": profile_country},
                            "id": tc["id"],
                            "type": tc.get("type", "tool_call"),
                        }
                        new_tool_calls.append(new_tc)
                        logger.info(
                            "Profile country override applied",
                            extra={
                                "event": "country_override_applied",
                                "profile_country": profile_country,
                                "llm_requested_country": llm_requested_country,
                                "query": tc.get("args", {}).get("query", ""),
                            },
                        )
                    else:
                        new_tool_calls.append(tc)
                # Replace response with a new AIMessage carrying the corrected tool_calls
                response = AIMessage(content=response.content, tool_calls=new_tool_calls, id=response.id)
            elif not has_country_in_last_msg:

                # Strip all search tool calls and ask for the country directly if no profile and no msg country
                original_tool_calls = list(response.tool_calls)
                response.tool_calls = [
                    tc for tc in response.tool_calls if tc["name"] not in ["search_catalog", "search_retailer_platform"]
                ]

                if not response.tool_calls:
                    original_query = "the items you are looking for"
                    for tc in original_tool_calls:
                        if "query" in tc.get("args", {}):
                            original_query = tc["args"]["query"]
                            break
                    response.content = f"It looks like you're a new customer. Could you please let me know which country you are in so I can check the local catalogs for the {original_query}?"

    # ── Strict Unregistered Customer Checkout Guardrail ──
    # If the user selected a product via Checkout ('I choose the ... option: "..." at price "..."')
    # and we do NOT have a registered email in the history, and they have not provided an email in the last message,
    # then we MUST ask for their email address and strip any tool calls.
    last_human_content = last_msg.content if isinstance(last_msg, HumanMessage) else ""
    is_checkout_message = bool(
        _re.search(r'I choose the \w+\s+option:\s*"([^"]+)"\s+at price\s*"([^"]+)"', last_human_content, _re.IGNORECASE)
    )

    if is_checkout_message:
        # Search history for a registered customer's email
        has_registered = False
        for m in state["messages"]:
            if isinstance(m, ToolMessage):
                try:
                    tool_data = json.loads(m.content) if isinstance(m.content, str) else {}
                except Exception:
                    try:
                        import ast as _ast

                        tool_data = _ast.literal_eval(m.content) if isinstance(m.content, str) else {}
                    except Exception:
                        tool_data = {}
                customer_data = tool_data.get("customer", tool_data) if isinstance(tool_data, dict) else {}
                if (
                    isinstance(tool_data, dict)
                    and customer_data.get("email")
                    and "not found" not in str(tool_data).lower()
                    and "not_found" not in str(tool_data).lower()
                ):
                    has_registered = True
                    break
                if isinstance(m.content, str):
                    email_match = _re.search(r'["\']email["\']\s*:\s*["\']([^"\'@\s]+@[^"\']+)["\']', m.content)
                    if email_match and "not found" not in m.content.lower() and "not_found" not in m.content.lower():
                        has_registered = True
                        break

        has_email_in_last_msg = "@" in last_human_content

        if not has_registered and not has_email_in_last_msg:
            logger.info(
                "Unregistered customer checkout: prompting for name and email address",
                extra={"event": "unregistered_checkout_prompt"},
            )
            # Strip all tool calls and ask for email and name
            response.tool_calls = []
            response.content = "Could you please provide your full name and email address so I can register your account and place your order?"

    # ═══ GUARDRAIL D: Registered Customer Email-Ask Bypass (CRITICAL) ═══
    # If the LLM generates a text response asking for email, but we already know the
    # customer is registered (found in a previous lookup_customer_orders ToolMessage),
    # AND the user's last message contains a product selection — inject create_new_order directly.
    EMAIL_ASK_PATTERNS = [
        "email address",
        "provide your email",
        "your email",
        "register your account",
        "register your email",
    ]
    is_asking_for_email = (
        not response.tool_calls
        and bool(response.content)
        and any(p in response.content.lower() for p in EMAIL_ASK_PATTERNS)
    )

    if is_asking_for_email:
        # Search history for a registered customer's email
        registered_email = None
        registered_name = None
        for m in state["messages"]:
            if isinstance(m, ToolMessage):
                try:
                    tool_data = json.loads(m.content) if isinstance(m.content, str) else {}
                except Exception:
                    # Fallback: handle Python str(dict) format which uses single quotes (not valid JSON)
                    try:
                        import ast as _ast

                        tool_data = _ast.literal_eval(m.content) if isinstance(m.content, str) else {}
                    except Exception:
                        tool_data = {}
                # Support both flat format {"email": "..."} and nested format {"customer": {"email": "..."}}
                # get_customer_orders() returns {"customer": {"email": ...}, "orders": [...]}
                customer_data = tool_data.get("customer", tool_data) if isinstance(tool_data, dict) else {}
                # A valid registered customer lookup contains 'email' and NOT 'not_found'
                if (
                    isinstance(tool_data, dict)
                    and customer_data.get("email")
                    and "not found" not in str(tool_data).lower()
                    and "not_found" not in str(tool_data).lower()
                ):
                    registered_email = customer_data["email"]
                    registered_name = customer_data.get("name", current_customer_name or "Customer")
                    break
                # Also try regex fallback that handles BOTH single and double quote formats
                if not registered_email and isinstance(m.content, str):
                    email_match = _re.search(r'["\']email["\']\s*:\s*["\']([^"\'@\s]+@[^"\']+)["\']', m.content)
                    name_match_t = _re.search(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']', m.content)
                    if email_match and "not found" not in m.content.lower() and "not_found" not in m.content.lower():
                        registered_email = email_match.group(1)
                        registered_name = (
                            name_match_t.group(1) if name_match_t else (current_customer_name or "Customer")
                        )
                        break

        if registered_email:
            # Parse product selection from the last HumanMessage
            # Format: 'I choose the PLATFORM option: "PRODUCT NAME" at price "PRICE"'
            last_human_content = last_msg.content if isinstance(last_msg, HumanMessage) else ""
            selection_match = _re.search(
                r'I choose the \w+\s+option:\s*"([^"]+)"\s+at price\s*"([^"]+)"', last_human_content, _re.IGNORECASE
            )
            if selection_match:
                product_name = selection_match.group(1).strip()
                price_str = selection_match.group(2).strip()

                # Detect currency from the price string
                if "￥" in price_str:
                    currency_code = "JPY"
                elif "¥" in price_str:
                    currency_code = "CNY"
                elif "₹" in price_str or "INR" in price_str.upper():
                    currency_code = "INR"
                elif "$" in price_str or "USD" in price_str.upper():
                    currency_code = "USD"
                elif "£" in price_str or "GBP" in price_str.upper():
                    currency_code = "GBP"
                elif "AED" in price_str.upper():
                    currency_code = "AED"
                else:
                    currency_code = "INR"

                # Strip currency symbols to get numeric price
                price_numeric = _re.sub(r"[^\d,\.]", "", price_str).replace(",", "")
                if not price_numeric:
                    price_numeric = "0"

                logger.info(
                    "GUARDRAIL D: Injecting create_new_order for registered customer",
                    extra={
                        "event": "registered_customer_bypass",
                        "email": registered_email,
                        "product": product_name,
                        "price": price_numeric,
                        "currency": currency_code,
                    },
                )

                # Inject the create_new_order tool call, clear the email-asking text
                response.content = ""
                response.tool_calls = [
                    {
                        "name": "create_new_order",
                        "args": {
                            "customer_name": registered_name,
                            "item": product_name,
                            "customer_email": registered_email,
                            "price": price_numeric,
                            "currency": currency_code,
                        },
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "tool_call",
                    }
                ]

    # ═══ GUARDRAIL E: Intercept hallucinated ticket creation claims ═══
    # The LLM sometimes claims to have created a support ticket (with or without
    # a TKT- ID) in its plain text WITHOUT actually calling create_support_ticket.
    # Detect both patterns:
    #   A) Response contains "TKT-" but no real ticket exists in tool history
    #   B) Response claims to have created/submitted a ticket without calling the tool
    _TICKET_CLAIM_PHRASES = [
        "created a support ticket",
        "created a ticket",
        "submitted a support ticket",
        "submitted a ticket",
        "opened a support ticket",
        "raised a support ticket",
        "escalated your case",
        "support ticket to address",
        "support ticket for",
    ]
    if not response.tool_calls and response.content:
        _content_lower = response.content.lower()
        _has_tkt_pattern = "TKT-" in response.content
        _has_ticket_claim = any(phrase in _content_lower for phrase in _TICKET_CLAIM_PHRASES)

        # Check whether a REAL ticket was already created in this conversation
        real_ticket_in_history = any(
            isinstance(m, ToolMessage)
            and m.name == "create_support_ticket"
            for m in state["messages"]
        )

        if not real_ticket_in_history:
            support_order_id = new_order_id or state.get("order_id")
            _delivery_complaint_keywords = [
                "never arrived", "not arrived", "hasn't arrived", "hasn't been delivered",
                "not delivered", "didn't arrive", "didn't receive", "never received",
                "missing", "delayed", "been weeks", "been days", "waiting for",
                "where is my", "still waiting", "not here yet",
            ]
            _is_delivery_complaint = any(
                kw in (last_msg.content.lower() if isinstance(last_msg, HumanMessage) else "")
                for kw in _delivery_complaint_keywords
            )
            
            delivery_date = None
            today = date.today()
            if _is_delivery_complaint:
                delivery_date = _get_order_delivery_date_from_history(state["messages"], support_order_id)

            # 1. If it's a delivery complaint AND the date has passed -> FORCE TICKET (even if LLM didn't claim one)
            if _is_delivery_complaint and delivery_date and delivery_date < today:
                logger.warning(
                    "Guardrail E: Delivery date has passed — forcing ticket creation directly",
                    extra={
                        "event": "forced_overdue_delivery_ticket_sync",
                        "order_id": support_order_id,
                    },
                )
                support_customer_name = current_customer_name or "Customer"
                ticket_resp = _create_ticket_sync(
                    order_id=support_order_id or "",
                    issue_type="Complaint",
                    message=last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation",
                    customer_name=support_customer_name
                )
                import re as _re_tmp
                ticket_match = _re_tmp.search(r"TKT-[0-9A-F]+", str(ticket_resp))
                ticket_id = ticket_match.group(0) if ticket_match else "a new ticket"
                
                tc_id = f"call_{uuid.uuid4().hex[:12]}"
                ai_msg_call = AIMessage(
                    content="",
                    tool_calls=[{"name": "create_support_ticket", "args": {"order_id": support_order_id or "", "issue_type": "Complaint", "message": last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation", "customer_name": support_customer_name}, "id": tc_id, "type": "tool_call"}]
                )
                tool_msg = ToolMessage(content=str(ticket_resp), name="create_support_ticket", tool_call_id=tc_id)
                final_msg = AIMessage(
                    content=f"I deeply apologize for the delay. Since your expected delivery date has passed, I have immediately escalated this to our human support team. Your ticket ID is **{ticket_id}**. A representative will reach out to you shortly."
                )
                return {
                    "messages": [ai_msg_call, tool_msg, final_msg] + messages_to_remove,
                    "intent": new_intent,
                    "order_id": new_order_id,
                    "react_iterations": react_iterations,
                }
            
            # 2. If it's a delivery complaint AND date has NOT passed BUT LLM claimed a ticket -> BLOCK TICKET
            elif _is_delivery_complaint and delivery_date and delivery_date >= today and (_has_tkt_pattern or _has_ticket_claim):
                logger.info(
                    "Guardrail E: blocked ticket creation — delivery date not yet passed",
                    extra={
                        "event": "delivery_date_not_passed",
                        "order_id": support_order_id,
                        "expected_delivery": str(delivery_date),
                        "today": str(today),
                    },
                )
                response = AIMessage(
                    content=(
                        f"I understand your concern! However, after checking your order details, "
                        f"your order {support_order_id or ''} is still within its expected delivery window. "
                        f"The expected delivery date is **{delivery_date.strftime('%B %d, %Y')}**, "
                        f"which {'is today' if delivery_date == today else 'has not passed yet'}. "
                        f"Your order status is currently being processed and is on track. "
                        f"If your order has not arrived after the expected delivery date, "
                        f"please reach out and we will immediately create a support ticket for you."
                    ),
                    id=response.id,
                )

            # 3. If it's NOT a delivery complaint (or missing date) BUT LLM claimed a ticket -> INJECT TICKET
            elif (_has_tkt_pattern or _has_ticket_claim):
                logger.warning(
                    "Intercepted hallucinated ticket claim — injecting create_support_ticket call synchronously",
                    extra={
                        "event": "hallucinated_ticket_intercepted_sync",
                    },
                )
                support_customer_name = current_customer_name or "Customer"
                ticket_resp = _create_ticket_sync(
                    order_id=support_order_id or "",
                    issue_type="Complaint",
                    message=last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation",
                    customer_name=support_customer_name
                )
                import re as _re_tmp
                ticket_match = _re_tmp.search(r"TKT-[0-9A-F]+", str(ticket_resp))
                ticket_id = ticket_match.group(0) if ticket_match else "a new ticket"
                
                tc_id = f"call_{uuid.uuid4().hex[:12]}"
                ai_msg_call = AIMessage(
                    content="",
                    tool_calls=[{"name": "create_support_ticket", "args": {"order_id": support_order_id or "", "issue_type": "Complaint", "message": last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation", "customer_name": support_customer_name}, "id": tc_id, "type": "tool_call"}]
                )
                tool_msg = ToolMessage(content=str(ticket_resp), name="create_support_ticket", tool_call_id=tc_id)
                final_msg = AIMessage(
                    content=f"I have created a support ticket for your issue. Your ticket ID is **{ticket_id}**. A human agent will contact you soon."
                )
                return {
                    "messages": [ai_msg_call, tool_msg, final_msg] + messages_to_remove,
                    "intent": new_intent,
                    "order_id": new_order_id,
                    "react_iterations": react_iterations,
                }

    # ABSOLUTE FINAL ENFORCER: Overdue Delivery Complaint
    # Catches cases where Guardrails skipped due to unexpected LLM tool_calls or missing TKT patterns
    support_order_id = new_order_id or state.get("order_id")
    _delivery_complaint_keywords = [
        "never arrived", "not arrived", "hasn't arrived", "hasn't been delivered",
        "not delivered", "didn't arrive", "didn't receive", "never received",
        "missing", "delayed", "been weeks", "been days", "waiting for",
        "where is my", "still waiting", "not here yet",
    ]
    _is_delivery_complaint = any(
        kw in (last_msg.content.lower() if isinstance(last_msg, HumanMessage) else "")
        for kw in _delivery_complaint_keywords
    )
    
    if _is_delivery_complaint:
        delivery_date = _get_order_delivery_date_from_history(state["messages"], support_order_id)
        today = date.today()
        
        if delivery_date and delivery_date < today:
            _has_tool = any(tc["name"] == "create_support_ticket" for tc in response.tool_calls)
            _has_ticket_in_history = False
            _ticket_id = "a new ticket"
            import re as _re_tmp
            for m in state["messages"]:
                if isinstance(m, ToolMessage) and m.name == "create_support_ticket":
                    _has_ticket_in_history = True
                    match = _re_tmp.search(r"TKT-[0-9A-F]+", str(m.content))
                    if match:
                        _ticket_id = match.group(0)
                        
            _has_tkt_in_response = _re_tmp.search(r"TKT-[0-9A-F]+", response.content or "")
            
            if not _has_tool and not _has_tkt_in_response:
                logger.warning("ABSOLUTE FINAL ENFORCER: Forcing overdue ticket response")
                if not _has_ticket_in_history:
                    support_customer_name = current_customer_name or "Customer"
                    ticket_resp = _create_ticket_sync(
                        order_id=support_order_id or "",
                        issue_type="Complaint",
                        message=last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation",
                        customer_name=support_customer_name
                    )
                    match = _re_tmp.search(r"TKT-[0-9A-F]+", str(ticket_resp))
                    if match:
                        _ticket_id = match.group(0)
                        
                    tc_id = f"call_{uuid.uuid4().hex[:12]}"
                    ai_msg_call = AIMessage(content="", tool_calls=[{"name": "create_support_ticket", "args": {"order_id": support_order_id or "", "issue_type": "Complaint", "message": last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation", "customer_name": support_customer_name}, "id": tc_id, "type": "tool_call"}])
                    tool_msg = ToolMessage(content=str(ticket_resp), name="create_support_ticket", tool_call_id=tc_id)
                    final_msg = AIMessage(
                        content=f"I deeply apologize for the delay. Since your expected delivery date has passed, I have immediately escalated this to our human support team. Your ticket ID is **{_ticket_id}**. A representative will reach out to you shortly."
                    )
                    return {
                        "messages": [ai_msg_call, tool_msg, final_msg] + messages_to_remove,
                        "intent": new_intent,
                        "order_id": new_order_id,
                        "react_iterations": react_iterations,
                    }
                else:
                    final_msg = AIMessage(
                        content=f"I deeply apologize for the delay. Since your expected delivery date has passed, I have immediately escalated this to our human support team. Your ticket ID is **{_ticket_id}**. A representative will reach out to you shortly."
                    )
                    return {
                        "messages": [final_msg] + messages_to_remove,
                        "intent": new_intent,
                        "order_id": new_order_id,
                        "react_iterations": react_iterations,
                    }

    logger.info(
        "Agent node response details",
        extra={"tool_calls": response.tool_calls, "content_len": len(response.content) if response.content else 0},
    )

    # Return the AI response, removal instructions, and reset state
    return {
        "messages": [response] + messages_to_remove,
        "intent": new_intent,
        "order_id": new_order_id,
        "react_iterations": react_iterations,
    }


