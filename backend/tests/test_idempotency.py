import pytest
from backend.app.models.models import Job, Channel, Automation
from backend.app.services.job_engine import ingest_channel_messages

class MockMsg:
    def __init__(self, id, text):
        self.id = id
        self.text = text
        self.out = False
        self.fwd_from = None

def test_persistent_database_idempotency(db, tenant_a):
    channel = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-100777666555",
        title="Idempotency Channel",
        is_connected=True
    )
    db.add(channel)
    db.flush()

    auto = Automation(
        tenant_id=tenant_a["tenant"].id,
        channel_id=channel.id,
        name="Idempotent Trigger",
        trigger_value="TP1",
        trigger_type="exact",
        is_active=True
    )
    db.add(auto)
    db.commit()

    msg = MockMsg(id=500, text="TP1")

    # Ingest first time
    count1 = ingest_channel_messages(db, channel, [msg], [auto])
    assert count1 == 1

    # Ingest same message second time (simulating network retry or poller restart)
    count2 = ingest_channel_messages(db, channel, [msg], [auto])
    assert count2 == 0  # Deduplicated by database constraint

    # Verify total jobs in DB for this trigger is exactly 1
    jobs = db.query(Job).filter(Job.idempotency_key == f"{channel.id}:500:{auto.id}").all()
    assert len(jobs) == 1
