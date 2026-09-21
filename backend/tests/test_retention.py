import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Tenant, User, Channel, RetentionSetting, AudienceMember, RecoveryCase, RecoveryMessage
)
from backend.app.services.retention_engine import classify_user_reply
from backend.app.services.userbot_pool import UserbotSession

def test_intent_classifier():
    # 1. Mistake or lost link
    cat, code = classify_user_reply("مسحتها بالغلط وعايز الرابط ارجع")
    assert cat == "MISTAKE_OR_LOST_LINK"

    cat, code = classify_user_reply("I accidentally left, can you send the link?")
    assert cat == "MISTAKE_OR_LOST_LINK"

    # 2. Too many messages / noise
    cat, code = classify_user_reply("الرسائل كتير جداً وعاملالي ازعاج")
    assert cat == "TOO_MANY_MESSAGES"

    # 3. Content critique
    cat, code = classify_user_reply("الصفقات خسرانة وبطلت تداول")
    assert cat == "CONTENT_CRITIQUE"

    # 4. Opt out
    cat, code = classify_user_reply("فكك مني ومتبعتليش رسايل تاني خالص stop")
    assert cat == "OPT_OUT"

    # 5. Other / Neutral
    cat, code = classify_user_reply("سلام عليكم مين معايا؟")
    assert cat == "OTHER"


def test_userbot_session_limits():
    async def dummy_client():
        return None

    session = UserbotSession("test_bot", dummy_client, max_daily_contacts=2)
    
    # Ready initially
    ok, reason = session.can_send_contact()
    assert ok is True
    
    # Increment count
    session.daily_contacts_count = 2
    ok, reason = session.can_send_contact()
    assert ok is False
    assert "Daily contact limit reached" in reason

    # Cooldown test
    session.daily_contacts_count = 0
    session.cooldown_until = datetime.now(timezone.utc).timestamp() + 500
    ok, reason = session.can_send_contact()
    assert ok is False
    assert "cooldown" in reason


def test_retention_api_flow(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100999888777",
        title="Test Retention Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get Retention Settings
    res = client.get(f"/api/v1/retention/settings/{channel.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_retention_enabled"] is True
    assert data["channel_id"] == channel.id

    # 2. Update Retention Settings
    update_payload = {
        "is_retention_enabled": True,
        "is_welcome_enabled": True,
        "initial_delay_seconds": 120,
        "welcome_message_template": "أهلاً بك يا {name} في {channel}!",
        "recovery_first_message_template": "مرحباً يا غالي، رأيك يهمنا!",
        "invite_link": "https://t.me/+testlink123",
        "max_daily_contacts": 40
    }
    res = client.put(f"/api/v1/retention/settings/{channel.id}", json=update_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["invite_link"] == "https://t.me/+testlink123"
    assert res.json()["initial_delay_seconds"] == 120

    # 3. Create a member and a recovery case
    member = AudienceMember(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        telegram_user_id="12345678",
        first_name="Ahmed",
        username="ahmed_trader",
        status="LEFT",
        first_joined_at=datetime.now(timezone.utc) - timedelta(days=5),
        last_left_at=datetime.now(timezone.utc)
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    case = RecoveryCase(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        member_id=member.id,
        telegram_user_id="12345678",
        leave_event_id="999001",
        status="CONVERSATION_ACTIVE",
        leave_reason_category="MISTAKE_OR_LOST_LINK",
        leave_reason_raw="مسحت القناة بالغلط وعايز ارجع",
        first_contacted_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=15)
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # 4. List cases
    res = client.get(f"/api/v1/retention/cases?channel_id={channel.id}", headers=headers)
    assert res.status_code == 200
    cases = res.json()
    assert len(cases) >= 1
    assert cases[0]["telegram_user_id"] == "12345678"
    assert cases[0]["user_full_name"] == "Ahmed"

    # 5. Get case details
    res = client.get(f"/api/v1/retention/cases/{case.id}", headers=headers)
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == case.id
    assert detail["status"] == "CONVERSATION_ACTIVE"

    # 6. Check summary stats
    res = client.get(f"/api/v1/retention/summary?channel_id={channel.id}", headers=headers)
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_left_detected"] >= 1
    assert summary["total_in_conversation"] >= 1


@pytest.mark.asyncio
async def test_rejoin_attribution(db: Session, tenant_a: dict):
    from backend.app.services.retention_engine import retention_engine
    user = tenant_a["user"]

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100555444333",
        title="Winback Test Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    settings = RetentionSetting(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        is_retention_enabled=True,
        initial_delay_seconds=60
    )
    db.add(settings)
    db.commit()

    # 1. Simulate member leave
    leave_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    await retention_engine._handle_member_leave(
        db=db,
        channel=channel,
        settings=settings,
        telegram_user_id="888777666",
        leave_event_id="ev_leave_101",
        event_date=leave_time,
        first_name="Sami",
        last_name="Trader",
        username="sami_fx"
    )

    case = db.query(RecoveryCase).filter(
        RecoveryCase.channel_id == channel.id,
        RecoveryCase.telegram_user_id == "888777666"
    ).first()
    assert case is not None
    assert case.status == "SCHEDULED"

    # 2. Simulate member rejoin
    rejoin_time = datetime.now(timezone.utc)
    await retention_engine._handle_member_join(
        db=db,
        channel=channel,
        settings=settings,
        telegram_user_id="888777666",
        event_date=rejoin_time,
        first_name="Sami",
        last_name="Trader",
        username="sami_fx"
    )

    db.refresh(case)
    assert case.status == "RECOVERED"
    assert case.rejoined_at is not None
    assert case.time_to_rejoin_seconds is not None
    assert case.time_to_rejoin_seconds >= 2600  # ~45 minutes

    member = db.query(AudienceMember).filter(
        AudienceMember.channel_id == channel.id,
        AudienceMember.telegram_user_id == "888777666"
    ).first()
    assert member.status == "RECOVERED"

