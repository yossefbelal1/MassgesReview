import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.models import Channel, AudienceMember, RecoveryCase

def test_retention_summary_funnel_and_status_distribution(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    now = datetime.now(timezone.utc)

    channel = Channel(
        tenant_id=user.tenant_id,
        title="Analytics Channel",
        is_connected=True,
        telegram_chat_id="-100998877"
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Create 5 test cases with distinct statuses and hours
    # Case 1: RECOVERED (responded, link delivered, won back)
    c1 = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="1111",
        status="RECOVERED",
        contactable=True,
        first_contacted_at=now - timedelta(hours=2),
        last_response_at=now - timedelta(hours=1, minutes=50),
        link_sent_at=now - timedelta(hours=1, minutes=40),
        rejoined_at=now - timedelta(hours=1),
        leave_reason_category="MISTAKE_OR_LOST_LINK",
        created_at=now - timedelta(hours=2)
    )
    # Case 2: CONVERSATION_ACTIVE (responded, link delivered)
    c2 = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="2222",
        status="CONVERSATION_ACTIVE",
        contactable=True,
        first_contacted_at=now - timedelta(hours=1),
        last_response_at=now - timedelta(minutes=45),
        link_sent_at=now - timedelta(minutes=30),
        leave_reason_category="CONTENT_CRITIQUE",
        created_at=now - timedelta(hours=1)
    )
    # Case 3: CONTACTED (contacted, awaiting response)
    c3 = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="3333",
        status="CONTACTED",
        contactable=True,
        first_contacted_at=now - timedelta(minutes=20),
        created_at=now - timedelta(hours=1)
    )
    # Case 4: SCHEDULED (in queue)
    c4 = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="4444",
        status="SCHEDULED",
        contactable=True,
        scheduled_contact_at=now + timedelta(seconds=25),
        created_at=now - timedelta(minutes=30)
    )
    # Case 5: UNCONTACTABLE (privacy restriction)
    c5 = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="5555",
        status="UNCONTACTABLE",
        contactable=False,
        uncontactable_reason="PRIVACY_RESTRICTED",
        created_at=now - timedelta(minutes=10)
    )
    db.add_all([c1, c2, c3, c4, c5])
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/retention/summary?channel_id={channel.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_left_detected"] == 5
    assert data["total_contacted"] == 3  # c1, c2, c3
    assert data["total_in_conversation"] == 1  # c2
    assert data["total_rejoined"] == 1  # c1
    assert data["uncontactable_count"] == 1  # c5
    assert data["total_scheduled_pending"] == 1  # c4
    assert data["win_back_rate_percent"] == 20.0  # 1 / 5 = 20%

    # Response rate: 2 responded out of 3 contacted = 66.7%
    assert data["response_rate_percent"] == 66.7
    # Conversion on response: 1 rejoined out of 2 responded = 50.0%
    assert data["conversion_on_response_percent"] == 50.0

    # Funnel stages: 5 stages present
    stages = data["funnel_stages"]
    assert len(stages) == 5
    assert stages[0]["id"] == "detected" and stages[0]["count"] == 5
    assert stages[1]["id"] == "contacted" and stages[1]["count"] == 3
    assert stages[2]["id"] == "responded" and stages[2]["count"] == 2
    assert stages[3]["id"] == "link_delivered" and stages[3]["count"] == 2
    assert stages[4]["id"] == "rejoined" and stages[4]["count"] == 1

    # Status distribution accounts for all 5 cases
    status_dist = data["status_distribution"]
    total_dist_count = sum(s["count"] for s in status_dist)
    assert total_dist_count == 5

    # Hourly distribution has 24 hours
    hourly = data["hourly_distribution"]
    assert len(hourly) == 24
    total_hourly_count = sum(h["count"] for h in hourly)
    assert total_hourly_count == 5


def test_turbo_dispatch_staggers_scheduled_cases(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    now = datetime.now(timezone.utc)

    channel = Channel(
        tenant_id=user.tenant_id,
        title="Turbo Channel",
        is_connected=True,
        telegram_chat_id="-10099887766"
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Create 3 scheduled cases
    cases = []
    for i in range(3):
        c = RecoveryCase(
            tenant_id=user.tenant_id,
            channel_id=channel.id,
            telegram_user_id=f"user_{i}",
            status="SCHEDULED",
            contactable=True,
            scheduled_contact_at=now - timedelta(hours=1), # Past time
            created_at=now - timedelta(hours=1, minutes=i*10)
        )
        cases.append(c)
    db.add_all(cases)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/retention/cases/turbo-dispatch?channel_id={channel.id}", headers=headers)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["dispatched_count"] == 3

    # Verify that in database, scheduled_contact_at are staggered
    db.expire_all()
    updated_cases = db.query(RecoveryCase).filter(RecoveryCase.channel_id == channel.id).order_by(RecoveryCase.created_at.desc()).all()
    assert len(updated_cases) == 3
    
    t0 = updated_cases[0].scheduled_contact_at
    t1 = updated_cases[1].scheduled_contact_at
    t2 = updated_cases[2].scheduled_contact_at
    
    # Delta should be roughly 15 seconds between each
    diff_1_0 = (t1 - t0).total_seconds()
    diff_2_1 = (t2 - t1).total_seconds()
    assert 14 <= diff_1_0 <= 16
    assert 14 <= diff_2_1 <= 16
