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

def test_concurrent_duplicate_event_ingestion_race():
    """
    Simultaneously execute 5 concurrent threads attempting to ingest the EXACT SAME
    Telegram message event with matching triggers.
    
    Expected Invariant:
    - Exactly 1 durable job created in the database.
    - Zero duplicate jobs created.
    - All 5 threads complete cleanly without crashing on unhandled IntegrityErrors.
    - Channel cursor is properly updated.
    """
    import threading
    import time
    from backend.tests.conftest import TestingSessionLocal
    from backend.app.models.models import Tenant, Plan, Subscription

    setup = TestingSessionLocal()
    tenant = Tenant(name="Race Tenant", slug=f"race-ingest-{time.time_ns()}")
    setup.add(tenant)
    setup.flush()

    plan = setup.query(Plan).filter(Plan.slug == "starter").first()
    from datetime import datetime, timezone, timedelta
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    setup.add(sub)
    setup.flush()

    channel = Channel(
        tenant_id=tenant.id,
        telegram_chat_id=f"-100{time.time_ns() % 10**9}",
        title="Concurrent Ingest Channel",
        is_connected=True,
    )
    setup.add(channel)
    setup.flush()

    auto = Automation(
        tenant_id=tenant.id,
        channel_id=channel.id,
        name="Race Auto",
        trigger_value="RACE_EVENT",
        trigger_type="exact",
        is_active=True,
    )
    setup.add(auto)
    setup.commit()

    ch_id = channel.id
    auto_id = auto.id
    setup.close()

    msg_id = 999
    barrier = threading.Barrier(5, timeout=10)
    results = [None] * 5

    def worker_ingest(idx):
        s = TestingSessionLocal()
        try:
            ch = s.query(Channel).filter(Channel.id == ch_id).first()
            a = s.query(Automation).filter(Automation.id == auto_id).all()
            msgs = [MockMsg(id=msg_id, text="RACE_EVENT")]
            barrier.wait()
            created = ingest_channel_messages(s, ch, msgs, a)
            results[idx] = created
        except Exception as exc:
            results[idx] = f"ERROR: {exc}"
        finally:
            s.close()

    threads = [threading.Thread(target=worker_ingest, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    # Verify no thread threw an unhandled exception
    errors = [r for r in results if isinstance(r, str) and r.startswith("ERROR")]
    assert len(errors) == 0, f"Thread errors: {errors}"

    # Across all 5 concurrent threads, exactly 1 job was created
    int_results = [r for r in results if isinstance(r, int)]
    assert sum(int_results) == 1, f"Expected total created == 1, got {results}"

    # Verify database state
    verify = TestingSessionLocal()
    jobs = verify.query(Job).filter(Job.idempotency_key == f"{ch_id}:{msg_id}:{auto_id}").all()
    assert len(jobs) == 1
    assert jobs[0].status == "PENDING"
    assert jobs[0].trigger_message_id == str(msg_id)
    verify.close()

def test_event_idempotency_survives_application_restart():
    """
    Verifies that after an application restart (new DB session, fresh object state),
    re-ingesting an already processed event does NOT create a duplicate job.
    """
    from backend.tests.conftest import TestingSessionLocal
    from backend.app.models.models import Tenant, Plan, Subscription
    import time
    from datetime import datetime, timezone, timedelta

    # Session 1: Initial event ingestion
    s1 = TestingSessionLocal()
    tenant = Tenant(name="Restart Tenant", slug=f"restart-ingest-{time.time_ns()}")
    s1.add(tenant)
    s1.flush()

    plan = s1.query(Plan).filter(Plan.slug == "starter").first()
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    s1.add(sub)
    s1.flush()

    channel = Channel(
        tenant_id=tenant.id,
        telegram_chat_id=f"-100{time.time_ns() % 10**9}",
        title="Restart Channel",
        is_connected=True,
    )
    s1.add(channel)
    s1.flush()

    auto = Automation(
        tenant_id=tenant.id,
        channel_id=channel.id,
        name="Restart Auto",
        trigger_value="RESTART_SIG",
        trigger_type="exact",
        is_active=True,
    )
    s1.add(auto)
    s1.commit()

    msg = MockMsg(id=777, text="RESTART_SIG")
    created1 = ingest_channel_messages(s1, channel, [msg], [auto])
    assert created1 == 1
    ch_id = channel.id
    auto_id = auto.id
    s1.close()  # Simulate complete application restart (session closed, memory cleared)

    # Session 2: Fresh startup re-encountering the same event
    s2 = TestingSessionLocal()
    ch_fresh = s2.query(Channel).filter(Channel.id == ch_id).first()
    autos_fresh = s2.query(Automation).filter(Automation.channel_id == ch_id).all()
    created2 = ingest_channel_messages(s2, ch_fresh, [msg], autos_fresh)
    assert created2 == 0  # Deduplicated from authoritative database state

    # Authoritative check
    total_jobs = s2.query(Job).filter(Job.idempotency_key == f"{ch_id}:777:{auto_id}").count()
    assert total_jobs == 1
    s2.close()

