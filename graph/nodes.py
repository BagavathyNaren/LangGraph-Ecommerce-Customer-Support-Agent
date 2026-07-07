import json
import re as _re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from graph.state import AgentState
from logger import get_logger
from tools.agent_tools import AGENT_TOOLS
from tools.real_tools import create_support_ticket

logger = get_logger("ecommerce-agent")


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


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True, request_timeout=30)
agent_llm = llm.bind_tools(AGENT_TOOLS)

AGENT_SYSTEM_PROMPT = """Role: You are an elite E-commerce Customer Support AI. Your objective is to process cancellation and escalation requests with 100% adherence to order status logic.

Core Directives:

Verification Phase: Every interaction must begin by checking the current status of the ORDER_ID via the system database using `check_order_status`.

The "Delivered" Gatekeeper: If the order status is DELIVERED, you are strictly prohibited from canceling the order. Inform the customer clearly that cancellation is not possible for delivered items, and provide the link/instructions to initiate a standard Return/Refund process (redirecting to the Returns Portal).

The "In-Transit" Protocol: If the order is IN_TRANSIT (or shipped) and the customer requests cancellation due to damage or quality concerns, do not simply cancel the order. Trigger an "Intercept/Return-to-Sender (RTS)" protocol. Inform the customer that you are intercepting the package with the courier and that the refund will be processed once the warehouse confirms the return. Call `process_cancellation` (or `process_return` as appropriate) to update the system.

Sentiment Strategy: You must be immune to "anger" or aggressive tone. Do not waste cycles attempting to classify or expand lists of "anger words." Treat negative sentiment as a high-priority signal to resolve the issue quickly. If the customer is angry, remain neutral, professional, and efficient. Validate their concern, but follow the logic rules for the specific order status without exception.

Reasoning Requirement: Before initiating any cancellation (for PROCESSING orders), you must explicitly ask the customer for the reason. If the reason provided is negative (e.g. defective, horrible quality, broken, damaged, changed mind, bought by mistake), use that as the justification for the cancellation and proceed immediately with the action (call `process_cancellation` immediately!).

Execution Logic Flow:
- If PROCESSING: Confirm reason -> Cancel Order -> Confirm success.
- If IN_TRANSIT: Acknowledge complaint -> Initiate Intercept/RTS -> Advise customer of the timeline (Refund on return).
- If DELIVERED: Deny cancellation -> Explain policy -> Redirect to Returns Portal.

ADDITIONAL GENERAL RULES:
- If the question is unrelated to these topics, politely decline.
- If a customer provides their name, use lookup_customer_orders to find their orders. NEVER call lookup_customer_orders with a country name or location statement (e.g. "japan", "in japan", "india", "from india"). If a user specifies their country, proceed immediately to the product search/catalog search using that country.
- If they provide an order ID (like ORD001), use the appropriate tool.
- When showing customer orders, format them clearly with order ID, item, status, and delivery date.
- Keep responses concise and helpful.
- When a customer asks about their refund status, ALWAYS explicitly include the last updated date (e.g. "last updated on ...") and the refund reason (e.g., "reason: ...") from the tool's response in your reply.
- NEVER make up order data or customer info — always use tools to look up real information.
- STRICT FORBIDDEN: Do not promise or offer discounts, coupons, or free items under any circumstances.
- STRICT FORBIDDEN: Do not make up fake company policies, warranties, or shipping guarantees.
- STRICT FORBIDDEN: Do not hallucinate or suggest products that are not found in the tools or knowledge base.
- USE 'create_support_ticket' for ANY complaint, stolen item, or complex request you cannot solve yourself. ALWAYS pass the customer_name as stated by the user in the conversation.
- NEVER use 'create_new_order' for a support issue or complaint.
- If a user asks about something completely outside of e-commerce, state clearly that you cannot assist.
- TICKET ID RULE: You MUST call the 'create_support_ticket' tool first and ONLY use the Ticket ID that the tool returns in its response. NEVER invent, guess, or use a placeholder ticket ID such as "TKT-XXXXX". The real Ticket ID will look like "TKT-A1B2C3" (6 random hex characters). Once a real Ticket ID is returned by the tool, you MUST always include that exact ID verbatim in your reply. Example: "Your Ticket ID is TKT-F03FFF."

VOICE INPUT ORDER ID RULE (CRITICAL):
- Users often speak their order ID via voice and speech recognition may mishear "ORD" as "ODD", "odd", "or d", "OR D", etc.
- If you receive an order ID that looks like "ODD001", "odd 002", "ODD 002" — treat it as ORD001, ORD002 etc. and pass it directly to the tool.
- The normalize_order_id function in the tool already handles this correction — just pass whatever the user gave you.
- NEVER tell the user their order ID format is wrong if it contains recognizable digits. Instead, try the tool first.
- Only ask for clarification if there are NO digits at all in the order ID.


ORDERING, REGISTRATION & PRODUCT SELECTION FLOW — FOLLOW THIS EXACTLY:
0. **COUNTRY IDENTIFICATION & CONSTRAINT RULE (CRITICAL)**:
   - We ONLY support ordering, customer registration, and checking product catalogs for five countries: **UAE, Japan, US, UK, and India**.
   - If a customer explicitly states they are in an unsupported country (any region other than UAE, Japan, US, UK, and India, such as China, Canada, Germany, etc.), you MUST immediately and politely reject their request, explaining that we only support UAE, Japan, US, UK, and India. Do NOT call any product search or registration tools for unsupported countries.
   - For supported countries, check the entire conversation history (including the user's very first message) to see if they have explicitly stated their country. If the country is mentioned anywhere in the conversation history, or is found in their registered profile from `lookup_customer_orders`, you MUST use that country and proceed. ONLY stop and ask the user for their country (e.g., "Could you please let me know which country you are in so I can check the local catalogs?") if it has not been mentioned anywhere in the conversation history and is not found in their profile.
   - **REGISTERED PROFILE COUNTRY OVERRIDE (CRITICAL)**: If a customer is registered and their profile from `lookup_customer_orders` contains a `country` field, that profile country ALWAYS takes precedence over any country the user mentions in their search request. For example, if a registered UK customer says "Search for a PlayStation 5 in India", you MUST search using country="UK" (their profile country), NOT "India". Politely inform the customer that you are searching based on their registered profile country. NEVER use a different country than the one in their registered profile for product searches.
1. ONLY start the ordering flow if the customer EXPLICITLY states they want to buy, purchase, or order an item. If they simply provide an email address without explicitly saying they want to place an order, DO NOT call `create_new_order`. **EXCEPTION**: If you have already displayed the options, the customer selected one (or clicked Checkout), and you then explicitly asked them for their email address, once they provide their email address, you **MUST** immediately call `register_customer` and `create_new_order` in parallel in that turn to complete the purchase, even if their message only contains their email address and no purchase verbs.
2. **FIRST-TURN CUSTOMER LOOKUP & CATALOG SEARCH (CRITICAL)**:
   - If the user introduces themselves by name (e.g., "My name is Fatima") AND expresses purchase intent (e.g., "I want to buy X"), you MUST first call `lookup_customer_orders` (using their name) in your first turn to verify if they are registered.
   - If their country is explicitly provided in their first message (e.g., "I am in UAE"), you can call search tools (`search_catalog` or `search_retailer_platform`) in parallel with the lookup.
   - If the country is not explicitly provided in their first message (or conversation history), you MUST NOT call any product search tools (search_catalog or search_retailer_platform) in that turn. You must ONLY call `lookup_customer_orders` in that turn.
   - If both of the following are true: (1) the customer lookup returns "not_found" or does not contain a country, AND (2) the country is not mentioned anywhere in the conversation history (including the user's very first message), ONLY THEN you MUST stop and ask the user for their country before performing any searches. If the country was already mentioned in the conversation history, you MUST NOT ask for it; use that country and proceed immediately with the product search.
3. **PRODUCT CATALOG & EXTERNAL RETAILERS (CRITICAL PLATFORM BOUNDARIES)**:
   - If `search_catalog` returns no products, you MUST automatically search external retailer platforms by calling `search_retailer_platform`.
   - For India, you MUST call it 3 separate times IN PARALLEL: once for "amazon", once for "flipkart", and once for "croma".
   - For any other country (e.g., USA, China, Japan, UAE, UK), search ONLY "amazon".
   - Present the options to the user clearly, GROUPED BY PLATFORM. You MUST use a strict platform header line (e.g., `### Amazon`) before listing its products. This is REQUIRED for the UI to render correctly.
   - **STRICT OUTPUT FORMAT (CRITICAL — do NOT deviate)**: Each product MUST be listed on its own line using EXACTLY this format:
     ```
     ### Amazon
     Product Full Name Here
     Price: ￥47,959

     Another Product Name
     Price: ￥81,980
     ```
   - NEVER use "Estimated Price:", "Sale Price:", "Listed Price:", or any other prefix. ONLY use "Price:".
   - NEVER collapse product name and price into a single line like "Product - Price: ￥X". Each product name and its price MUST be on SEPARATE lines.
   - NEVER place an order or call any order placement tools without showing the product options and having the user explicitly select one first.
   - STRICT LIMIT ON SUPPORTED PLATFORMS: We ONLY support searching on "Amazon", "Flipkart", and "Croma". Under no circumstances should you offer to search on "other platforms". If the main item is out of stock, offer accessories.
4. **STRICT REGISTRATION CHECK (CRITICAL)**:
   - You MUST ALWAYS check the customer's registration status by first calling `lookup_customer_orders` in this conversation before placing any order. You are STRICTLY FORBIDDEN from calling `create_new_order` without first verifying their registration status via `lookup_customer_orders` in this conversation.
5. **STRICT NEW CUSTOMER FLOW (CRITICAL)**:
   - A customer is a **NEW CUSTOMER** if:
     a) `lookup_customer_orders` was called and returned a result indicating they are not found (e.g. "Customer 'X' not found" or "not_found").
     b) OR they explicitly state they are a new user/customer (e.g., "I am a new user").
   - If the customer is a NEW CUSTOMER, you MUST strictly follow this sequence:
     - **Step A: Country Identification and Product Display**: Before asking for their email address or mentioning registration, you MUST first obtain their country (if not already known) and search/display the products in their local currency.
       * **STRICT NEGATIVE CONSTRAINT**: You are STRICTLY FORBIDDEN from asking the user for their email address or mentioning registration at this stage. You MUST ask for their country first (if not already known), and then fetch/display products first.
     - **Step B: Ask for Name & Email ONLY at Checkout**: ONLY when the customer has selected a product option (e.g., by clicking "Checkout" or stating they choose an option/product), you MUST then explicitly ask them for their full name and email address (e.g. "Could you please provide your full name and email address so I can register your account and place your order?").
       * **STRICT NEGATIVE CONSTRAINT**: DO NOT ask for their email address or name, register them, or call register tools before a specific product option has been selected by the user.
       * **DO NOT** make up, guess, or hallucinate an email address, and **DO NOT** copy or reuse a name or email address from a different customer in the conversation history (e.g. do not use Chan's email for Mumtaj, and do not use "Alis" as the name for a new user). You MUST ask the current user for their own name and email.
     - **Step C: Registration & Ordering**: Once they provide their full name and email address in response to your Step B prompt, you MUST call `register_customer` AND `create_new_order` together in parallel in that same turn to complete registration and order placement.
6. **STRICT REGISTERED CUSTOMER BYPASS (CRITICAL)**:
    - A customer is **REGISTERED** if `lookup_customer_orders` returned a valid customer profile with an email address, AND they have NOT stated they are a new user. This applies even if there are minor variations or suffixes in their name (e.g. if the user says "Alex" but lookup returns a profile for "AlexTest75380", treat them as registered!).
    - For registered customers:
      - You **MUST NOT** ask them for their email address, ask for registration, or tell them you need to register them under any circumstances.
      - Once they select their preferred product option (or click Checkout), you **MUST immediately call `create_new_order`** as a tool call in that turn, passing their registered email (extracted directly from the previous `lookup_customer_orders` tool response) and chosen product details. Do NOT ask them for confirmation of their email or ask them to type it.
7. Always confirm the order placement to the customer with a clear, formatted block explicitly containing: Customer Name, Registered/Confirmed Email, Order ID, Item, Price, Expected Delivery Date, and Tracking ID/Number. Never omit any of these details under any circumstances."""

# Map tool names to intent labels for badge display
TOOL_INTENT_MAP = {
    "check_order_status": "order_status",
    "check_refund_status": "refund_status",
    "process_return": "return_request",
    "process_cancellation": "cancel_order",
    "lookup_customer_orders": "customer_lookup",
    "register_customer": "new_customer",
    "create_new_order": "new_order",
}


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

    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"]
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

    # ═══ GUARDRAIL E: Intercept hallucinated TKT-XXXXX ticket IDs ═══
    # If the LLM generates a text response containing the literal placeholder "TKT-XXXXX"
    # without having called create_support_ticket, it has hallucinated the ticket ID.
    # Strip the response and inject a real create_support_ticket tool call instead.
    has_hallucinated_ticket = (
        not response.tool_calls
        and bool(response.content)
        and "TKT-XXXXX" in response.content
    )

    if has_hallucinated_ticket:
        logger.warning(
            "Intercepted hallucinated TKT-XXXXX in LLM response — injecting create_support_ticket tool call",
            extra={"event": "hallucinated_ticket_intercepted", "response_snippet": (response.content or "")[:200]},
        )
        # Extract customer name from conversation
        support_customer_name = current_customer_name or "Customer"
        support_order_id = new_order_id or state.get("order_id")
        # Create a fresh AIMessage with the real tool call — do NOT mutate response
        response = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "create_support_ticket",
                    "args": {
                        "order_id": support_order_id or "",
                        "issue_type": "Complaint",
                        "message": last_msg.content if isinstance(last_msg, HumanMessage) else "Customer complaint requiring escalation",
                        "customer_name": support_customer_name,
                    },
                    "id": f"call_{uuid.uuid4().hex[:12]}",
                    "type": "tool_call",
                }
            ],
            id=response.id,
        )

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


def tool_node(state: AgentState) -> AgentState:
    """Execute tool calls from the agent's last response, with Redis caching and parallel execution."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    from cache.redis_cache import get_cached_tool_result, set_cached_tool_result

    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in AGENT_TOOLS}
    tool_calls = last_message.tool_calls

    if not tool_calls:
        return state

    def execute_single_tool(tool_call):
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        start = time.time()

        try:
            # Check tool cache first
            cached = get_cached_tool_result(tool_name, tool_args)
            if cached:
                result = cached
                duration_ms = round((time.time() - start) * 1000)
                logger.info(
                    "Tool executed (cached)",
                    extra={
                        "event": "tool_cached",
                        "tool": tool_name,
                        "tool_args": tool_args,
                        "duration_ms": duration_ms,
                    },
                )
            else:
                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    result = tool_fn.invoke(tool_args)
                    # Cache the result (skip if it contains an error)
                    if "error" not in str(result).lower() or "not_found" in str(result).lower():
                        set_cached_tool_result(tool_name, tool_args, str(result))
                else:
                    result = f"Tool {tool_name} not found."
                duration_ms = round((time.time() - start) * 1000)
                logger.info(
                    "Tool executed (live)",
                    extra={"event": "tool_live", "tool": tool_name, "tool_args": tool_args, "duration_ms": duration_ms},
                )
        except Exception as e:
            result = f"Error executing tool '{tool_name}': {str(e)}"
            duration_ms = round((time.time() - start) * 1000)
            logger.error(
                "Tool execution failed",
                extra={
                    "event": "tool_error",
                    "tool": tool_name,
                    "tool_args": tool_args,
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
            )

        return ToolMessage(content=str(result), tool_call_id=tool_call["id"]), tool_name, tool_args

    # Execute all tool calls concurrently
    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 5)) as executor:
        futures = [executor.submit(execute_single_tool, tc) for tc in tool_calls]
        for future in futures:
            tool_msg, tool_name, tool_args = future.result()
            state["messages"].append(tool_msg)

            # Extract metadata for frontend badges
            if "order_id" in tool_args:
                state["order_id"] = tool_args["order_id"]
            if tool_name in TOOL_INTENT_MAP:
                if state.get("intent") != "new_order":
                    state["intent"] = TOOL_INTENT_MAP[tool_name]

    return state


def escalation_check(state: AgentState) -> AgentState:
    """Check if the conversation should be escalated to a human."""
    human_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not human_messages:
        return state

    last_message = human_messages[-1].content.lower()

    # Standard anger keywords
    anger_words = ["angry", "furious", "terrible", "worst", "useless", "refund now", "escalate"]

    anger_count = state.get("anger_count", 0)
    retry_count = state.get("retry_count", 0)
    refund_amount = state.get("refund_amount", 0.0)
    already_escalated = state.get("escalated", False)

    if not already_escalated:
        # Find the AI message just before the last HumanMessage
        is_cancelling = False
        human_idx = -1
        for i, m in enumerate(state["messages"]):
            if isinstance(m, HumanMessage) and m == human_messages[-1]:
                human_idx = i
                break

        if human_idx > 0:
            for m in reversed(state["messages"][:human_idx]):
                if isinstance(m, AIMessage) and m.content:
                    last_ai = m.content.lower()
                    if (
                        "reason for cancel" in last_ai
                        or "reason for request" in last_ai
                        or "reason for the cancellation" in last_ai
                    ):
                        is_cancelling = True
                    break

        has_anger = any(word in last_message for word in anger_words)
        if has_anger:
            if "cancel" in last_message or is_cancelling:
                pass  # DO NOT escalate! Let the agent handle cancellation.
            else:
                anger_count += 1

        if anger_count >= 2 or retry_count >= 3 or refund_amount > 5000:
            state["escalated"] = True

    state["anger_count"] = anger_count
    state["retry_count"] = retry_count
    state["refund_amount"] = refund_amount
    return state


def escalate(state: AgentState) -> AgentState:
    """Escalate to a human agent by creating a support ticket."""
    import re as _re

    messages = state.get("messages", [])
    # Check if a REAL ticket was already created (ignore hallucinated "TKT-XXXXX" placeholder)
    already_escalated = any(
        _re.search(r"TKT-[0-9A-F]{6}\b", m.content)
        for m in messages
        if isinstance(m, AIMessage)
    )

    if already_escalated:
        reply = "Your case is already escalated. A human agent will contact you soon."
    else:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        order_id = state.get("order_id")

        # Scan conversation history in REVERSE order for most recent order ID and customer name if not in state
        customer_name = None
        for m in reversed(messages):
            # Check AIMessage for tool calls containing order_id or customer_name
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    tc_args = tc.get("args", {})
                    if not order_id and "order_id" in tc_args:
                        order_id = str(tc_args["order_id"]).upper()
                    if not customer_name and "customer_name" in tc_args:
                        customer_name = tc_args["customer_name"]

            if isinstance(m, HumanMessage):
                # Extract order IDs like ORD001, ORD 001, ORD1234
                if not order_id:
                    order_match = _re.search(r"\b(ORD\s*\d{3,10})\b", m.content, _re.IGNORECASE)
                    if order_match:
                        order_id = _re.sub(r"\s+", "", order_match.group(1)).upper()
                # Extract customer name from "I am X" or "my name is X" patterns
                if not customer_name:
                    extracted = extract_customer_name(m.content)
                    if extracted:
                        customer_name = extracted
            elif isinstance(m, ToolMessage):
                # Extract customer info from tool responses
                if not order_id:
                    order_match = _re.search(r"\b(ORD\s*\d{3,10})\b", m.content, _re.IGNORECASE)
                    if order_match:
                        order_id = _re.sub(r"\s+", "", order_match.group(1)).upper()

        # Summarize the conversation to provide context for the human agent
        history_lines = [
            f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}"
            for m in messages[-4:]
            if isinstance(m, (HumanMessage, AIMessage))
        ]
        history = "\n".join(history_lines)

        result = create_support_ticket(ticket_id, order_id, "Automated Escalation", history, customer_name)
        # Use the actual ticket ID from result (handles duplicate case where existing ticket was found)
        actual_ticket_id = result.get("ticket_id", ticket_id)
        if result.get("duplicate"):
            reply = (
                f"Your case already has an open support ticket. "
                f"Ticket ID: {actual_ticket_id}. "
                f"A human agent will review it and contact you within 2 hours."
            )
        elif result.get("success"):
            reply = (
                f"I've escalated your case to a human agent. "
                f"Ticket ID: {actual_ticket_id}. "
                f"A human agent will contact you within 2 hours."
            )
        else:
            reply = f"I've flagged your case for immediate review. {result.get('message', 'A human agent will be in touch shortly.')}"

    state["messages"].append(AIMessage(content=reply))
    state["escalated"] = False
    state["anger_count"] = 0
    return state
