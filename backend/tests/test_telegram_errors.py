import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
from backend.app.models.models import Job, Channel, Automation
from backend.app.services.job_engine import process_claimed_job

class MockTelethonClient:
    def __init__(self, forward_exception=None):
        self.forward_exception = forward_exception
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        # Return a mock message
        msg = MagicMock()
        msg.id = 1234
        msg.text = "Great trading signals!"
        msg.fwd_from = MagicMock()
        msg.fwd_from.from_id = MagicMock()
        msg.fwd_from.from_name = "Trader Joe"
        return [msg]

    async def forward_messages(self, entity, messages, from_peer):
        if self.forward_exception:
            raise self.forward_exception
        res = MagicMock()
        res.id = 5678
        return res

@pytest.mark.asyncio
async def test_telegram_flood_wait_handling(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-10011223344", title="Flood Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Flood Auto", trigger_value="SIGNAL", is_active=True, reviews_count=1, initial_delay_seconds=0.1)
    db.add(auto)
    db.flush()

    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="flood_job_1", trigger_text="SIGNAL", status="CLAIMED")
    db.add(job)
    db.commit()

    # Client raises FloodWait of 45 seconds
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

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Perm Auto", trigger_value="SIGNAL", is_active=True, reviews_count=1, initial_delay_seconds=0.1)
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
