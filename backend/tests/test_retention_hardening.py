import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Tenant, User, Channel, AudienceMember, RecoveryCase, InviteLink,
    MembershipEvent, MembershipState, RejoinAttempt, RetentionMetric
)
from backend.app.services.retention_engine import retention_engine
from backend.app.services.sse_service import sse_broadcaster


@pytest.mark.asyncio
async def test_voluntary_leave_and_rejoin_tracked_link(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888777",
        title="Hardened Test Channel",
        is_connected=True,
        bot_is_admin=True,
        health_state="HEALTHY"
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # 1. Create a tracked invite link
    invite = InviteLink(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        invite_link="https://t.me/+TrackedLink123",
        name="Winback Special Promo",
        is_primary=True
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # 2. Simulate voluntary leave
    leave_time = datetime.now(timezone.utc) - timedelta(hours=2)
    await retention_engine._handle_member_leave(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="12345678",
        leave_event_id="leave_evt_001",
        event_date=leave_time,
        first_name="Bob",
        last_name="Smith",
        username="leaver_bob"
    )

    # Verify recovery case created
    case = db.query(RecoveryCase).filter(
        RecoveryCase.channel_id == channel.id,
        RecoveryCase.telegram_user_id == "12345678"
    ).first()
    assert case is not None
    assert case.status == "SCHEDULED"

    # Verify membership_state projection
    m_state = db.query(MembershipState).filter(
        MembershipState.channel_id == channel.id,
        MembershipState.telegram_user_id == "12345678"
    ).first()
    assert m_state is not None
    assert m_state.status == "left"
    assert m_state.last_leave is not None

    # Verify immutable event log
    evt = db.query(MembershipEvent).filter(
        MembershipEvent.channel_id == channel.id,
        MembershipEvent.telegram_user_id == "12345678",
        MembershipEvent.event_type == "LEAVE"
    ).first()
    assert evt is not None

    # 3. Simulate rejoin via tracked invite link
    join_time = datetime.now(timezone.utc)
    await retention_engine._handle_member_join(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="12345678",
        event_date=join_time,
        first_name="Bob",
        last_name="Smith",
        username="leaver_bob",
        invite_link_str="https://t.me/+TrackedLink123"
    )

    # Verify rejoin attempt
    rejoin = db.query(RejoinAttempt).filter(
        RejoinAttempt.channel_id == channel.id,
        RejoinAttempt.telegram_user_id == "12345678"
    ).first()
    assert rejoin is not None
    assert rejoin.confidence == "CONFIRMED"
    assert rejoin.invite_id == invite.id

    # Verify case marked RECOVERED
    db.refresh(case)
    assert case.status == "RECOVERED"
    assert case.rejoined_at is not None

    # Verify membership_state projection status = member
    db.refresh(m_state)
    assert m_state.status == "member"
    assert m_state.last_join is not None


@pytest.mark.asyncio
async def test_kicked_banned_vs_churn(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888666",
        title="Ban Kick Filter Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # First, let's create a pending case
    case = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="999888",
        status="SCHEDULED"
    )
    db.add(case)
    db.commit()

    # User is banned by admin (involuntary)
    await retention_engine._handle_member_kick_or_ban(
        db=db,
        channel=channel,
        telegram_user_id="999888",
        event_date=datetime.now(timezone.utc),
        action_type="BAN",
        first_name="Bad",
        username="bad_user"
    )

    # Verify event logged
    evt = db.query(MembershipEvent).filter(
        MembershipEvent.channel_id == channel.id,
        MembershipEvent.telegram_user_id == "999888",
        MembershipEvent.event_type == "BAN"
    ).first()
    assert evt is not None

    # Verify state projection is 'banned'
    m_state = db.query(MembershipState).filter(
        MembershipState.channel_id == channel.id,
        MembershipState.telegram_user_id == "999888"
    ).first()
    assert m_state is not None
    assert m_state.status == "banned"

    # Verify case cancelled/opted-out with INVOLUNTARY_BAN
    db.refresh(case)
    assert case.status == "OPT_OUT"
    assert case.uncontactable_reason == "INVOLUNTARY_BAN"


@pytest.mark.asyncio
async def test_direct_rejoin(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888555",
        title="Direct Rejoin Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Leave voluntary
    await retention_engine._handle_member_leave(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="555444",
        leave_event_id="leave_evt_direct",
        event_date=datetime.now(timezone.utc) - timedelta(hours=1),
        first_name="Direct",
        last_name="User",
        username="direct_user"
    )

    case = db.query(RecoveryCase).filter(
        RecoveryCase.channel_id == channel.id,
        RecoveryCase.telegram_user_id == "555444"
    ).first()
    assert case is not None

    # Rejoin without invite link (DIRECT)
    await retention_engine._handle_member_join(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="555444",
        event_date=datetime.now(timezone.utc),
        first_name="Direct",
        last_name="User",
        username="direct_user",
        invite_link_str=None
    )

    rejoin = db.query(RejoinAttempt).filter(
        RejoinAttempt.channel_id == channel.id,
        RejoinAttempt.telegram_user_id == "555444"
    ).first()
    assert rejoin is not None
    assert rejoin.confidence in ["ATTRIBUTED", "UNKNOWN"]

    # Case should be RECOVERED
    db.refresh(case)
    assert case.status == "RECOVERED"


@pytest.mark.asyncio
async def test_join_request_flow(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888444",
        title="Join Request Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Member joins via join request
    join_time = datetime.now(timezone.utc)
    await retention_engine._handle_member_join(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="777666",
        event_date=join_time,
        first_name="Req",
        last_name="User",
        username="request_user",
        via_join_request=True
    )

    evt = db.query(MembershipEvent).filter(
        MembershipEvent.channel_id == channel.id,
        MembershipEvent.telegram_user_id == "777666"
    ).first()
    assert evt is not None
    assert evt.via_join_request is True
    assert evt.source == "JOIN_REQUEST"


@pytest.mark.asyncio
async def test_idempotent_event_handling(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888333",
        title="Idempotency Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    same_time = datetime.now(timezone.utc)

    # First leave event
    await retention_engine._handle_member_leave(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="111222",
        leave_event_id="idem_evt_1",
        event_date=same_time,
        first_name="Idem",
        last_name="User",
        username="idem_user"
    )

    # Duplicate leave event at same timestamp
    await retention_engine._handle_member_leave(
        db=db,
        channel=channel,
        settings=None,
        telegram_user_id="111222",
        leave_event_id="idem_evt_1",
        event_date=same_time,
        first_name="Idem",
        last_name="User",
        username="idem_user"
    )

    # Must not duplicate case or event
    cases = db.query(RecoveryCase).filter(
        RecoveryCase.channel_id == channel.id,
        RecoveryCase.telegram_user_id == "111222"
    ).all()
    assert len(cases) == 1

    events = db.query(MembershipEvent).filter(
        MembershipEvent.channel_id == channel.id,
        MembershipEvent.telegram_user_id == "111222",
        MembershipEvent.event_type == "LEAVE"
    ).all()
    assert len(events) == 1


def test_cohort_winback_calculation(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888222",
        title="Cohort Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    now = datetime.now(timezone.utc)
    cohort_start = now - timedelta(days=5)
    cohort_end = now

    # User 1: churned 3 days ago, rejoined 2 days ago
    e1_leave = MembershipEvent(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="user_c1",
        event_type="LEAVE",
        timestamp=now - timedelta(days=3)
    )
    e1_join = MembershipEvent(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="user_c1",
        event_type="JOIN",
        timestamp=now - timedelta(days=2)
    )

    # User 2: churned 4 days ago, did not rejoin
    e2_leave = MembershipEvent(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="user_c2",
        event_type="LEAVE",
        timestamp=now - timedelta(days=4)
    )
    db.add_all([e1_leave, e1_join, e2_leave])
    db.commit()

    stats = retention_engine.calculate_cohort_winback(
        db=db,
        channel_id=channel.id,
        cohort_start=cohort_start,
        cohort_end=cohort_end,
        window_days=7
    )

    assert stats["total_leavers"] == 2
    assert stats["total_returned"] == 1
    assert stats["winback_rate_percent"] == 50.0


def test_channel_health_and_api(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888111",
        title="Health Status Channel",
        is_connected=True,
        bot_is_admin=True,
        health_state="HEALTHY",
        consecutive_errors=0,
        last_event_at=datetime.now(timezone.utc)
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Query health endpoint
    res = client.get(f"/api/v1/retention/channels/{channel.id}/health", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["health_state"] == "HEALTHY"
    assert data["consecutive_errors"] == 0
    assert data["title"] == "Health Status Channel"

    # Query membership state endpoint
    res_m = client.get(f"/api/v1/retention/channels/{channel.id}/membership-state", headers=headers)
    assert res_m.status_code == 200
    assert isinstance(res_m.json(), list)


def test_multi_tenant_isolation(client: TestClient, db: Session, tenant_a: dict, tenant_b: dict):
    user_a = tenant_a["user"]
    token_b = tenant_b["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Channel belongs to Tenant A
    channel_a = Channel(
        tenant_id=user_a.tenant_id,
        telegram_chat_id="-100999888000",
        title="Private A Channel",
        is_connected=True
    )
    db.add(channel_a)
    db.commit()
    db.refresh(channel_a)

    # Tenant B tries to access Tenant A's channel health -> 404
    res_health = client.get(f"/api/v1/retention/channels/{channel_a.id}/health", headers=headers_b)
    assert res_health.status_code == 404

    # Tenant B tries to access Tenant A's membership state -> 404
    res_state = client.get(f"/api/v1/retention/channels/{channel_a.id}/membership-state", headers=headers_b)
    assert res_state.status_code == 404


@pytest.mark.asyncio
async def test_sse_broadcaster():
    test_channel_id = "test-channel-sse-1"
    q = asyncio.Queue()
    await sse_broadcaster.subscribe(test_channel_id, q)

    # Broadcast test event
    sse_broadcaster.broadcast(test_channel_id, "TEST_EVENT", {"foo": "bar"})

    # Read from queue
    msg = await asyncio.wait_for(q.get(), timeout=2.0)
    assert msg["type"] == "TEST_EVENT"
    assert msg["data"]["foo"] == "bar"

    await sse_broadcaster.unsubscribe(test_channel_id, q)
    assert test_channel_id not in sse_broadcaster._subscribers or len(sse_broadcaster._subscribers[test_channel_id]) == 0
