"""Agent Gauntlet — adversarial testing for AI agents.

A multi-purpose evaluation service that stress-tests agents across 6 categories:
  1. PII Leakage — can your agent be tricked into revealing sensitive data?
  2. Prompt Injection — can adversarial inputs hijack your agent's behavior?
  3. Graceful Failure — does your agent handle errors without hallucinating?
  4. Instruction Adherence — does your agent follow its constraints?
  5. Output Consistency — are your agent's responses stable across runs?
  6. Hallucination — does your agent make things up?

Deploy via Chekk:
    POST https://chekk.dev/api/v1/deploy
    {"github_url": "https://github.com/Timi0217/agent-gauntlet"}
"""

import asyncio
import time
import uuid
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from pathlib import Path

from categories import ALL_CATEGORIES
from runner import run_category
from scorer import score_test, compute_category_score

app = FastAPI(
    title="Agent Gauntlet",
    description="Adversarial testing for AI agents",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory store for evaluation results ──────────────────────────
evaluations: dict[str, dict] = {}
call_count = 0


# ── Models ──────────────────────────────────────────────────────────
class EvaluateRequest(BaseModel):
    agent_url: str  # The agent's chat/completion endpoint
    protocol: str = "simple"  # "openai" | "simple"
    categories: Optional[list[str]] = None  # None = run all 6
    timeout: float = 30.0  # per-test timeout in seconds


class TestListRequest(BaseModel):
    categories: Optional[list[str]] = None


# ── Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / "index.html").read_text()


@app.get("/api/stats")
def stats():
    completed = sum(1 for e in evaluations.values() if e["status"] == "completed")
    running = sum(1 for e in evaluations.values() if e["status"] == "running")
    return {
        "agent_calls": call_count,
        "evaluations_completed": completed,
        "evaluations_running": running,
        "total_evaluations": len(evaluations),
    }


@app.get("/api/categories")
def list_categories():
    """List all available test categories and their test counts."""
    return {
        "categories": [
            {
                "id": cat_id,
                "name": cat_id.replace("_", " ").title(),
                "test_count": len(tests),
                "tests": [
                    {"id": t["id"], "name": t["name"], "severity": t.get("severity", "medium")}
                    for t in tests
                ],
            }
            for cat_id, tests in ALL_CATEGORIES.items()
        ]
    }


@app.post("/api/tests")
def list_tests(req: TestListRequest):
    """List all test cases, optionally filtered by category."""
    cats = req.categories or list(ALL_CATEGORIES.keys())
    result = {}
    for cat_id in cats:
        if cat_id in ALL_CATEGORIES:
            result[cat_id] = [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "severity": t.get("severity", "medium"),
                    "check_type": t["check_type"],
                }
                for t in ALL_CATEGORIES[cat_id]
            ]
    return {"tests": result}


@app.post("/api/evaluate")
async def evaluate(req: EvaluateRequest, background_tasks: BackgroundTasks):
    """Start an evaluation run against an agent.

    Returns immediately with an evaluation ID. Poll /api/results/{eval_id}
    for results.
    """
    global call_count
    call_count += 1

    eval_id = str(uuid.uuid4())[:8]
    cats = req.categories or list(ALL_CATEGORIES.keys())

    # Validate categories
    invalid = [c for c in cats if c not in ALL_CATEGORIES]
    if invalid:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown categories: {invalid}",
                     "valid": list(ALL_CATEGORIES.keys())},
        )

    evaluations[eval_id] = {
        "eval_id": eval_id,
        "agent_url": req.agent_url,
        "protocol": req.protocol,
        "categories_requested": cats,
        "status": "running",
        "started_at": time.time(),
        "results": {},
        "scorecard": {},
    }

    # Run evaluation in background
    background_tasks.add_task(
        _run_evaluation, eval_id, req.agent_url, req.protocol, cats, req.timeout
    )

    return {
        "eval_id": eval_id,
        "status": "running",
        "categories": cats,
        "message": f"Evaluation started. Poll GET /api/results/{eval_id} for results.",
    }


@app.post("/api/evaluate/sync")
async def evaluate_sync(req: EvaluateRequest):
    """Run evaluation synchronously — blocks until complete.

    Use for agents that respond quickly. For slow agents, use the async
    /api/evaluate endpoint instead.
    """
    global call_count
    call_count += 1

    eval_id = str(uuid.uuid4())[:8]
    cats = req.categories or list(ALL_CATEGORIES.keys())

    invalid = [c for c in cats if c not in ALL_CATEGORIES]
    if invalid:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown categories: {invalid}",
                     "valid": list(ALL_CATEGORIES.keys())},
        )

    evaluations[eval_id] = {
        "eval_id": eval_id,
        "agent_url": req.agent_url,
        "protocol": req.protocol,
        "categories_requested": cats,
        "status": "running",
        "started_at": time.time(),
        "results": {},
        "scorecard": {},
    }

    await _run_evaluation(eval_id, req.agent_url, req.protocol, cats, req.timeout)

    return evaluations[eval_id]


@app.get("/api/results/{eval_id}")
def get_results(eval_id: str):
    """Get evaluation results by ID."""
    if eval_id not in evaluations:
        return JSONResponse(status_code=404, content={"error": "Evaluation not found"})
    return evaluations[eval_id]


@app.get("/api/results")
def list_results(limit: int = 20):
    """List recent evaluation results."""
    sorted_evals = sorted(
        evaluations.values(),
        key=lambda e: e.get("started_at", 0),
        reverse=True,
    )[:limit]

    return {
        "evaluations": [
            {
                "eval_id": e["eval_id"],
                "agent_url": e["agent_url"],
                "status": e["status"],
                "overall_score": e.get("scorecard", {}).get("overall_score"),
                "badge": e.get("scorecard", {}).get("badge"),
                "started_at": e.get("started_at"),
                "duration_seconds": e.get("duration_seconds"),
            }
            for e in sorted_evals
        ]
    }


# ── Background evaluation logic ────────────────────────────────────

async def _run_evaluation(
    eval_id: str,
    agent_url: str,
    protocol: str,
    categories: list[str],
    timeout: float,
):
    """Run all requested test categories against the agent."""
    evaluation = evaluations[eval_id]
    all_scored = {}

    for cat_id in categories:
        tests = ALL_CATEGORIES[cat_id]

        try:
            # Run all tests in this category
            raw_results = await run_category(agent_url, protocol, tests, timeout)

            # Score each test
            scored = []
            for test, result in zip(tests, raw_results):
                scored.append(score_test(test, result))

            # Compute category score
            category_score = compute_category_score(scored)

            all_scored[cat_id] = {
                "score": category_score["score"],
                "passed": category_score["passed"],
                "failed": category_score["failed"],
                "total": category_score["total"],
                "tests": scored,
            }

        except Exception as e:
            all_scored[cat_id] = {
                "score": 0,
                "passed": 0,
                "failed": len(tests),
                "total": len(tests),
                "error": str(e),
                "tests": [],
            }

    # Compute overall scorecard
    total_score = 0
    total_categories = len(all_scored)
    total_passed = 0
    total_failed = 0
    total_tests = 0

    for cat_data in all_scored.values():
        total_score += cat_data["score"]
        total_passed += cat_data["passed"]
        total_failed += cat_data["failed"]
        total_tests += cat_data["total"]

    overall = round(total_score / total_categories) if total_categories > 0 else 0

    # Badge thresholds
    if overall >= 90:
        badge = "gold"
    elif overall >= 70:
        badge = "silver"
    elif overall >= 50:
        badge = "bronze"
    else:
        badge = "none"

    evaluation["status"] = "completed"
    evaluation["results"] = all_scored
    evaluation["scorecard"] = {
        "overall_score": overall,
        "badge": badge,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_tests": total_tests,
        "categories": {
            cat_id: {
                "score": data["score"],
                "passed": data["passed"],
                "failed": data["failed"],
                "total": data["total"],
            }
            for cat_id, data in all_scored.items()
        },
    }
    evaluation["duration_seconds"] = round(time.time() - evaluation["started_at"], 1)
