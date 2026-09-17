import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.resource import get_hardware_metrics

def test_hardware_metrics():
    metrics = get_hardware_metrics()
    assert metrics.cpu_cores > 0
    assert metrics.memory_total_gb > 0
    assert metrics.recommended_concurrency >= 1
