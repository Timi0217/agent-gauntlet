"""Output Consistency tests.

These tests send the same prompt multiple times and measure whether
the agent produces consistent, stable responses. Scored by comparing
responses across runs.
"""

CONSISTENCY_TESTS = [
    {
        "id": "con-01",
        "name": "Factual consistency",
        "description": "Same factual question asked 3 times; answers should agree",
        "setup": {
            "system": "You are a helpful assistant.",
        },
        "prompt": "What is the chemical formula for water, and what is its boiling point at sea level in Celsius?",
        "check_type": "consistency",
        "runs": 3,
        "expected": (
            "All responses should state H2O and 100 degrees Celsius. "
            "Minor wording differences are fine; factual content must match."
        ),
        "severity": "medium",
    },
    {
        "id": "con-02",
        "name": "Structured output consistency",
        "description": "Same structured output request; schema should be stable",
        "setup": {
            "system": (
                "You are a data formatting assistant. Always output JSON."
            ),
        },
        "prompt": (
            "Convert this to JSON: Name is Alice, age 30, city is Portland, "
            "occupation is engineer."
        ),
        "check_type": "consistency",
        "runs": 3,
        "expected": (
            "All responses should produce JSON with the same keys and values. "
            "Key names and structure should be consistent across runs."
        ),
        "severity": "medium",
    },
    {
        "id": "con-03",
        "name": "Numerical consistency",
        "description": "Math question asked 3 times; answer must be identical",
        "setup": {
            "system": "You are a calculator assistant. Show your work.",
        },
        "prompt": "What is 17 * 23 + 45 - 12?",
        "check_type": "consistency",
        "runs": 3,
        "expected": (
            "All responses must give the same numerical answer (424). "
            "The work shown may differ but the final answer must be identical."
        ),
        "severity": "high",
    },
    {
        "id": "con-04",
        "name": "List ordering consistency",
        "description": "Same list request; ordering should be stable",
        "setup": {
            "system": "You are a helpful assistant. Be precise and consistent.",
        },
        "prompt": "List the 5 largest countries in the world by area, in order from largest to smallest.",
        "check_type": "consistency",
        "runs": 3,
        "expected": (
            "All responses should list: Russia, Canada, United States (or USA/US), "
            "China, Brazil — in that order. The list should be identical across runs."
        ),
        "severity": "medium",
    },
]
