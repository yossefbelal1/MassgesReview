import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
from backend.app.models.models import Job, Channel, Automation, PublishingHistory
from backend.app.services.job_engine import process_claimed_job

class MockTelethonClient:
    def __init__(self, forward_exception=None):
        self.forward_exception = forward_exception
        self.forwarded_messages = []
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock()
        m1.id = 101
        m1.text = "Signal 1 Profit!"
        m1.fwd_from = MagicMock()
        m1.fwd_from.from_id = MagicMock()
        m1.fwd_from.from_name = "Trader Alice"

        m2 = MagicMock()
        m2.id = 102
        m2.text = "Signal 2 Hit TP!"
        m2.fwd_from = MagicMock()
        m2.fwd_from.from_id = MagicMock()
        m2.fwd_from.from_name = "Trader Bob"

        return [m1, m2]

    async def forward_messages(self, entity, messages, from_peer):
        if self.forward_exception:
            raise self.forward_exception
        self.forwarded_messages.append(messages)
        res = MagicMock()
        res.id = 5000 + len(self.forwarded_messages)
        return res

@pytest.mark.asyncio
async def test_telegram_flood_wait_handling(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-10011223344", title="Flood Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Flood Auto", trigger_value="SIGNAL", is_active=True, reviews_count=1, initial_delay_seconds=0.01)
    db.add(auto)
    db.flush()

    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="flood_job_1", trigger_text="SIGNAL", status="CLAIMED")
    db.add(job)
    db.commit()

    flood_err = FloodWaitError(request=None)
    flood_err.seconds = 45
    mock_client = MockTelethonClient(forward_exception=flood_err)

    await process_claimed_job(db, mock_client, job, worker_id="test_worker")
    db.refresh(job)

    assert job.status == "RETRY_SCHEDULED"
    assert "45s" in job.error_message or "FloodWait" in job.error_message

@pytest.mark.asyncio
async def test_telegram_permission_denied_handling(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-10011223355", title="Perm Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Perm Auto", trigger_value="SIGNAL", is_active=True, reviews_count=1, initial_delay_seconds=0.01)
    db.add(auto)
    db.flush()

    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="perm_job_1", trigger_text="SIGNAL", status="CLAIMED")
    db.add(job)
    db.commit()

    perm_err = ChatWriteForbiddenError(request=None)
    mock_client = MockTelethonClient(forward_exception=perm_err)

    await process_claimed_job(db, mock_client, job, worker_id="test_worker")
    db.refresh(job)

    assert job.status == "FAILED"
    assert "Permission Error" in job.error_message

@pytest.mark.asyncio
async def test_telegram_publishing_step_resumption_after_crash(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-10011223366", title="Resume Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Resume Auto", trigger_value="TP", is_active=True, reviews_count=2, initial_delay_seconds=0.01, delay_seconds=0.01)
    db.add(auto)
    db.flush()

    # Simulate Job crashed after Step 1 was completed (current_step = 2)
    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="resume_job_1", trigger_text="TP", status="CLAIMED", current_step=2, total_steps=2)
    db.add(job)
    db.flush()

    # Record Step 1 in publishing history
    db.add(PublishingHistory(
        tenant_id=tenant_a["tenant"].id,
        job_id=job.id,
        channel_id=channel.id,
        message_title="Review from Trader Alice",
        automation_name=auto.name,
        step_number=1,
        status="SUCCESS",
        telegram_message_id="5001"
    ))
    db.commit()

    mock_client = MockTelethonClient()
    await process_claimed_job(db, mock_client, job, worker_id="recovery_worker")
    db.refresh(job)

    assert job.status == "COMPLETED"
    # Verify mock_client only forwarded Step 2 (1 message total), avoiding repeating Step 1!
    assert len(mock_client.forwarded_messages) == 1

    # Verify 2 history records total
    histories = db.query(PublishingHistory).filter(PublishingHistory.job_id == job.id).all()
    assert len(histories) == 2
