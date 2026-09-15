import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.resource import get_hardware_metrics
from app.core.batch_queue import batch_manager

def test_hardware_metrics():
    metrics = get_hardware_metrics()
    assert metrics.cpu_cores > 0
    assert metrics.memory_total_gb > 0
    assert metrics.recommended_concurrency >= 1

@pytest.mark.asyncio
async def test_batch_queue_simulation():
    job = batch_manager.create_job(total_count=3, user_concurrency=2)
    assert job.total_count == 3
    assert job.completed_count == 0

    await batch_manager.run_batch_simulation(job.id)
    updated = batch_manager.get_job(job.id)
    assert updated.status.value == "finished"
    assert updated.completed_count == 3
