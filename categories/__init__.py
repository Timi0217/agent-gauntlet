from .pii import PII_TESTS
from .injection import INJECTION_TESTS
from .failure import FAILURE_TESTS
from .adherence import ADHERENCE_TESTS
from .consistency import CONSISTENCY_TESTS
from .hallucination import HALLUCINATION_TESTS

ALL_CATEGORIES = {
    "pii_leakage": PII_TESTS,
    "injection_resistance": INJECTION_TESTS,
    "graceful_failure": FAILURE_TESTS,
    "instruction_adherence": ADHERENCE_TESTS,
    "output_consistency": CONSISTENCY_TESTS,
    "hallucination": HALLUCINATION_TESTS,
}
