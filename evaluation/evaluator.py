from langchain_core.messages import HumanMessage
from logger import get_logger

logger = get_logger("evaluator")

TEST_CASES = [
    {
        "id": "eval-001",
        "input": "What is the status of my order ORD001?",
        "thread_id": "eval-thread-001",
        "expected_intent": "order_status",
        "expected_escalated": False
    },
    {
        "id": "eval-002",
        "input": "What is my refund status for order ORD001?",
        "thread_id": "eval-thread-002",
        "expected_intent": "refund_status",
        "expected_escalated": False
    },
    {
        "id": "eval-003",
        "input": "I want to return my order ORD002",
        "thread_id": "eval-thread-003",
        "expected_intent": "return_request",
        "expected_escalated": False
    },
    {
        "id": "eval-004",
        "input": "Cancel my order ORD003",
        "thread_id": "eval-thread-004",
        "expected_intent": "cancel_order",
        "expected_escalated": False
    },
    {
        "id": "eval-005",
        "input": "My email is test@example.com and I need help",
        "thread_id": "eval-thread-005",
        "expected_intent": None,
        "expected_escalated": False,
        "expected_pii": True
    }
]

def run_evaluation(graph):
    results = []
    passed = 0
    failed = 0

    for case in TEST_CASES:
        try:
            from security.guards import validate_input, validate_output
            validated_message, pii_detected = validate_input(case["input"])

            config = {"configurable": {"thread_id": case["thread_id"]}}
            result = graph.invoke(
                {"messages": [HumanMessage(content=validated_message)]},
                config=config
            )

            actual_intent = result.get("intent")
            actual_escalated = result.get("escalated", False)
            response = result["messages"][-1].content

            checks = []

            if case.get("expected_intent"):
                intent_pass = actual_intent == case["expected_intent"]
                checks.append({"check": "intent", "expected": case["expected_intent"], "actual": actual_intent, "passed": intent_pass})

            escalation_pass = actual_escalated == case["expected_escalated"]
            checks.append({"check": "escalated", "expected": case["expected_escalated"], "actual": actual_escalated, "passed": escalation_pass})

            if case.get("expected_pii"):
                checks.append({"check": "pii_detected", "expected": True, "actual": pii_detected, "passed": pii_detected})

            case_passed = all(c["passed"] for c in checks)
            if case_passed:
                passed += 1
            else:
                failed += 1

            results.append({
                "id": case["id"],
                "input": case["input"],
                "response": response,
                "checks": checks,
                "passed": case_passed
            })

            logger.info("Eval case completed", extra={
                "event": "eval_case",
                "id": case["id"],
                "passed": case_passed
            })

        except Exception as e:
            failed += 1
            results.append({
                "id": case["id"],
                "input": case["input"],
                "response": None,
                "checks": [],
                "passed": False,
                "error": str(e)
            })

    summary = {
        "total": len(TEST_CASES),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(TEST_CASES) * 100, 1)
    }

    logger.info("Evaluation complete", extra={"event": "eval_complete", **summary})
    return {"summary": summary, "results": results}