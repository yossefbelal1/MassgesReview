import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, patch

from backend.app.models.models import (
    Tenant, User, Channel, AudienceMember, RecoveryCase, InviteLink,
    MembershipEvent, RejoinAttempt, RetentionMetric
)
from backend.app.services.retention_engine import retention_engine


def test_invite_link_creation_and_primary_flag(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100111222333",
        title="SaaS Retention Test Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # 1. Create first primary invite link via API
    payload1 = {
        "name": "VIP Campaign Link",
        "is_primary": True,
        "member_limit": 100,
        "expires_in_days": 7
    }
    res1 = client.post(f"/api/v1/retention/channels/{channel.id}/invite-links", json=payload1, headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["name"] == "VIP Campaign Link"
    assert data1["is_primary"] is True
    assert data1["member_limit"] == 100
    assert "t.me" in data1["invite_link"]
    link1_id = data1["id"]

    # 2. Create second primary invite link - first one should be demoted from primary
    payload2 = {
        "name": "Secondary Promo Link",
        "is_primary": True,
        "member_limit": 50,
        "expires_in_days": 14
    }
    res2 = client.post(f"/api/v1/retention/channels/{channel.id}/invite-links", json=payload2, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_primary"] is True

    # Verify link1 is no longer primary in DB
    db_link1 = db.query(InviteLink).filter(InviteLink.id == link1_id).first()
    assert db_link1.is_primary is False

    # 3. List all links for this channel
    res_list = client.get(f"/api/v1/retention/channels/{channel.id}/invite-links", headers=headers)
    assert res_list.status_code == 200
    links = res_list.json()
    assert len(links) == 2


def test_membership_events_and_rejoin_confidence(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100222333444",
        title="Event & Winback Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Create an invite link for this channel
    invite = InviteLink(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        invite_link="https://t.me/+confirmedlink",
        name="Winback Test Link",
        is_primary=True
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # 1. Member leaves channel
    now = datetime.now(timezone.utc)
    leave_event = MembershipEvent(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        telegram_user_id="99887766",
        event_type="LEAVE",
        source="ADMIN_LOG",
        timestamp=now - timedelta(hours=2)
    )
    db.add(leave_event)

    member = AudienceMember(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        telegram_user_id="99887766",
        username="leaver_user",
        status="LEFT"
    )
    db.add(member)

    case = RecoveryCase(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        telegram_user_id="99887766",
        status="CONTACTED",
        first_contacted_at=now - timedelta(hours=1),
        created_at=now - timedelta(hours=2)
    )
    db.add(case)
    db.commit()

    # 2. Member rejoins using the tracked invite link -> CONFIRMED confidence
    rejoin_time = now
    duration = int((rejoin_time - (now - timedelta(hours=2))).total_seconds())

    rejoin_record = RejoinAttempt(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        telegram_user_id="99887766",
        leave_time=now - timedelta(hours=2),
        rejoin_time=rejoin_time,
        time_to_rejoin_seconds=duration,
        invite_id=invite.id,
        recovery_case_id=case.id,
        confidence="CONFIRMED"
    )
    db.add(rejoin_record)

    join_event = MembershipEvent(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        telegram_user_id="99887766",
        event_type="JOIN",
        invite_id=invite.id,
        source="ADMIN_LOG",
        timestamp=rejoin_time
    )
    db.add(join_event)
    db.commit()

    # Test API for events
    res_events = client.get(f"/api/v1/retention/channels/{channel.id}/events", headers=headers)
    assert res_events.status_code == 200
    events_data = res_events.json()
    assert len(events_data) == 2
    types = [e["event_type"] for e in events_data]
    assert "LEAVE" in types
    assert "JOIN" in types

    # Test API for rejoins
    res_rejoins = client.get(f"/api/v1/retention/channels/{channel.id}/rejoins", headers=headers)
    assert res_rejoins.status_code == 200
    rejoins_data = res_rejoins.json()
    assert len(rejoins_data) == 1
    assert rejoins_data[0]["confidence"] == "CONFIRMED"
    assert rejoins_data[0]["invite_id"] == invite.id


def test_daily_metrics_computation(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100333444555",
        title="Metrics Test Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    now = datetime.now(timezone.utc)
    today = now.date()

    # Create 4 leaves and 2 returns for today
    for i in range(4):
        db.add(MembershipEvent(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            telegram_user_id=f"user_{i}",
            event_type="LEAVE",
            timestamp=now - timedelta(seconds=i * 5)
        ))
    for j in range(2):
        db.add(RejoinAttempt(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            telegram_user_id=f"user_{j}",
            leave_time=now - timedelta(seconds=120),
            rejoin_time=now,
            time_to_rejoin_seconds=3600,
            confidence="ATTRIBUTED"
        ))
    db.commit()

    # Trigger metric computation via endpoint
    res = client.post(f"/api/v1/retention/channels/{channel.id}/metrics/compute", headers=headers)
    assert res.status_code == 200
    metric_data = res.json()
    assert metric_data["total_leaves"] == 4
    assert metric_data["total_returns"] == 2
    assert metric_data["winback_rate"] == 50.0  # 2 / 4 * 100%
    assert metric_data["avg_return_time_seconds"] == 3600.0

    # Retrieve metrics list
    res_list = client.get(f"/api/v1/retention/channels/{channel.id}/metrics?days=7", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) == 1
    assert list_data[0]["winback_rate"] == 50.0


def test_reconciliation_audit(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100444555666",
        title="Reconciliation Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Add 10 active audience members
    for i in range(10):
        db.add(AudienceMember(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            telegram_user_id=f"active_{i}",
            status="ACTIVE"
        ))
    db.commit()

    # Call reconciliation endpoint
    res = client.post(f"/api/v1/retention/channels/{channel.id}/reconcile", headers=headers)
    assert res.status_code == 200
    rec_data = res.json()
    assert rec_data["channel_id"] == channel.id
    assert rec_data["db_active_members"] == 10
    assert "status" in rec_data
    assert "reconciled_at" in rec_data


def test_multi_tenant_isolation_retention(client: TestClient, db: Session, tenant_a: dict, tenant_b: dict):
    # Channel belongs to tenant A
    user_a = tenant_a["user"]
    token_a = tenant_a["token"]

    user_b = tenant_b["user"]
    token_b = tenant_b["token"]

    channel_a = Channel(
        tenant_id=user_a.tenant_id,
        telegram_chat_id="-100777888999",
        title="Tenant A Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel_a)
    db.commit()
    db.refresh(channel_a)

    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant B attempts to access Tenant A's invite links -> 404
    res1 = client.get(f"/api/v1/retention/channels/{channel_a.id}/invite-links", headers=headers_b)
    assert res1.status_code == 404

    # Tenant B attempts to create invite link on Tenant A's channel -> 404
    res2 = client.post(f"/api/v1/retention/channels/{channel_a.id}/invite-links", json={"name": "Hacked"}, headers=headers_b)
    assert res2.status_code == 404

    # Tenant B attempts to view Tenant A's events -> 404
    res3 = client.get(f"/api/v1/retention/channels/{channel_a.id}/events", headers=headers_b)
    assert res3.status_code == 404

    # Tenant B attempts to view Tenant A's rejoins -> 404
    res4 = client.get(f"/api/v1/retention/channels/{channel_a.id}/rejoins", headers=headers_b)
    assert res4.status_code == 404

    # Tenant B attempts to view Tenant A's metrics -> 404
    res5 = client.get(f"/api/v1/retention/channels/{channel_a.id}/metrics", headers=headers_b)
    assert res5.status_code == 404
