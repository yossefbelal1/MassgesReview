import pytest
import importlib

def test_listener_module_imports_cleanly():
    import telegram_engine.listener as listener
    assert hasattr(listener, "WORKER_ID")
    assert hasattr(listener, "ingest_channel_messages")
    assert hasattr(listener, "claim_next_job")
    assert hasattr(listener, "recover_expired_leases")
    assert hasattr(listener, "update_worker_heartbeat")
    assert hasattr(listener, "process_claimed_job")
    assert hasattr(listener, "active_channel_watcher")
    assert hasattr(listener, "worker_job_executor")
    assert listener.WORKER_ID.startswith("listener-")

def test_worker_module_imports_cleanly():
    import worker.worker as worker_module
    assert hasattr(worker_module, "ReviewFlowWorker")
    assert hasattr(worker_module, "WORKER_ID")
    w = worker_module.ReviewFlowWorker(poll_interval=0.1)
    assert w.running is True
    assert w.worker_id.startswith("worker-")

def test_job_engine_functions_are_callable():
    from backend.app.services.job_engine import (
        ingest_channel_messages,
        claim_next_job,
        recover_expired_leases,
        update_worker_heartbeat,
        process_claimed_job,
        is_valid_member_review
    )
    assert callable(ingest_channel_messages)
    assert callable(claim_next_job)
    assert callable(recover_expired_leases)
    assert callable(update_worker_heartbeat)
    assert callable(process_claimed_job)
    assert callable(is_valid_member_review)
