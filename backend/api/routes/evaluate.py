import os
from fastapi import APIRouter, Header, HTTPException
from agent.graph_builder import get_graph
from evaluation.evaluator import run_evaluation
from infra.logger import get_logger

logger = get_logger("evaluate-route")
router = APIRouter()


@router.post("/evaluate")
def run_agent_evaluation(x_api_key: str = Header(None)):
    expected_key = os.environ.get("EVAL_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing API key.")
    graph = get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready.")
    try:
        logger.info("Evaluation started", extra={"event": "eval_start"})
        results = run_evaluation(graph)
        return results
    except Exception as e:
        logger.error("Evaluation failed", extra={"event": "eval_error", "error": str(e)})
        raise HTTPException(status_code=500, detail="Evaluation failed.")
