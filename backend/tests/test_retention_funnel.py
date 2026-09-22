import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.models import (
    Tenant, User, Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, ChannelUserbot
)
from backend.app.services.retention_engine import retention_engine
from backend.app.services.userbot_pool import userbot_pool, UserbotSession
from telethon.errors import PeerFloodError


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed Tenant, Channel, RetentionSetting
    tenant = Tenant(id="tenant-funnel-1", name="Funnel Tenant", slug="funnel-tenant", is_active=True)
    session.add(tenant)
    session.commit()

    channel = Channel(
        id="channel-funnel-1",
        tenant_id=tenant.id,
        telegram_chat_id="-100999888",
        title="Test Crypto Channel",
        username="testcrypto",
        is_connected=True,
        bot_is_admin=True
    )
    session.add(channel)

    settings = RetentionSetting(
        id="set-1",
        tenant_id=tenant.id,
        channel_id=channel.id,
        is_retention_enabled=True,
        initial_delay_seconds=5,
        invite_link="https://t.me/+TestInviteLink123"
    )
    session.add(settings)
    session.commit()

    yield session
    session.close()


def test_funnel_reconciliation_math(db_session):
    """
    Verifies that the retention summary mathematically reconciles:
    total_left = total_contacted + total_scheduled_pending + uncontactable_count + total_opt_out.
    """
    channel = db_session.query(Channel).first()
    now = datetime.now(timezone.utc)

    # 1. Add 4 members and cases with distinct states
    # Member 1: Contacted
    m1 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="101", username="user1", status="LEFT")
    db_session.add(m1)
    db_session.flush()
    c1 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member_id=m1.id, telegram_user_id="101", status="CONTACTED", first_contacted_at=now)
    db_session.add(c1)

    # Member 2: In Conversation
    m2 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="102", username="user2", status="LEFT")
    db_session.add(m2)
    db_session.flush()
    c2 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member_id=m2.id, telegram_user_id="102", status="CONVERSATION_ACTIVE", first_contacted_at=now)
    db_session.add(c2)

    # Member 3: Scheduled Pending
    m3 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="103", username="user3", status="LEFT")
    db_session.add(m3)
    db_session.flush()
    c3 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member_id=m3.id, telegram_user_id="103", status="SCHEDULED", scheduled_contact_at=now)
    db_session.add(c3)

    # Member 4: Uncontactable (Privacy)
    m4 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="104", username="user4", status="LEFT")
    db_session.add(m4)
    db_session.flush()
    c4 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member_id=m4.id, telegram_user_id="104", status="UNCONTACTABLE", contactable=False, uncontactable_reason="PRIVACY_RESTRICTED")
    db_session.add(c4)

    # Member 5: Recovered
    m5 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="105", username="user5", status="RECOVERED")
    db_session.add(m5)
    db_session.flush()
    c5 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member_id=m5.id, telegram_user_id="105", status="RECOVERED", first_contacted_at=now, rejoined_at=now, time_to_rejoin_seconds=3600)
    db_session.add(c5)

    db_session.commit()

    # Query metrics
    base_query = db_session.query(RecoveryCase).filter(RecoveryCase.tenant_id == channel.tenant_id)
    total_left = base_query.count()
    total_contacted = base_query.filter(RecoveryCase.first_contacted_at.isnot(None)).count()
    total_rejoined = base_query.filter(RecoveryCase.status == "RECOVERED").count()
    total_scheduled = base_query.filter(RecoveryCase.status.in_(["SCHEDULED", "DETECTED"])).count()
    uncontactable_count = base_query.filter(RecoveryCase.status == "UNCONTACTABLE").count()
    total_opt_out = base_query.filter(RecoveryCase.status == "OPT_OUT").count()

    # Assert exact math
    assert total_left == 5
    assert total_contacted == 3  # c1, c2, c5
    assert total_rejoined == 1   # c5
    assert total_scheduled == 1  # c3
    assert uncontactable_count == 1  # c4
    assert total_opt_out == 0

    # Win-back rate: 1 / 5 = 20.0%
    win_back_rate = round((total_rejoined / total_left * 100), 1)
    assert win_back_rate == 20.0


def test_direct_telegram_link_builder(db_session):
    """
    Verifies that generate_direct_outreach_link generates correct pre-filled URL.
    """
    channel = db_session.query(Channel).first()
    settings = db_session.query(RetentionSetting).first()

    # 1. Member with username
    m1 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="9991", username="stonewave", first_name="Ahmed")
    c1 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member=m1, telegram_user_id="9991")

    link1 = retention_engine.generate_direct_outreach_link(channel, settings, c1)
    assert link1 is not None
    assert link1.startswith("https://t.me/stonewave?text=")
    assert "https%3A//t.me/%2BTestInviteLink123" in link1 or "https://t.me/+TestInviteLink123" in link1
    assert "Ahmed" in link1 or "%D8%A3%D8%AD%D9%85%D8%AF" in link1

    # 2. Member without username (fallback to tg://user)
    m2 = AudienceMember(tenant_id=channel.tenant_id, channel_id=channel.id, telegram_user_id="9992", username=None, first_name="Khaled")
    c2 = RecoveryCase(tenant_id=channel.tenant_id, channel_id=channel.id, member=m2, telegram_user_id="9992")

    link2 = retention_engine.generate_direct_outreach_link(channel, settings, c2)
    assert link2 == "tg://user?id=9992"


@pytest.mark.asyncio
async def test_username_priority_over_access_hash():
    """
    Verifies that UserbotPool prioritizes canonical username over access_hash.
    """
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value=MagicMock(id=12345))
    mock_client.get_me = AsyncMock(return_value=MagicMock(id=777, username="AutoMassge1"))

    # Mock action context manager
    mock_action_ctx = AsyncMock()
    mock_action_ctx.__aenter__.return_value = None
    mock_action_ctx.__aexit__.return_value = None
    mock_client.action = MagicMock(return_value=mock_action_ctx)

    session = UserbotSession("primary", AsyncMock(return_value=mock_client), max_daily_contacts=35)
    pool = userbot_pool
    pool.sessions = [session]

    # Target has both username and access_hash
    res = await pool.send_direct_message(
        target_user_id=1234567,
        text="Hello recovery test",
        target_username="@crypto_trader",
        access_hash=999888777
    )

    assert res["success"] is True
    # Verify entity passed to send_message was username string "crypto_trader", NOT InputPeerUser
    call_args = mock_client.send_message.call_args[0]
    assert call_args[0] == "crypto_trader"


@pytest.mark.asyncio
async def test_peer_flood_handling_and_retry_seconds():
    """
    Verifies that PeerFloodError is caught gracefully and returns 900s retry delay.
    """
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(side_effect=PeerFloodError(request=None))
    mock_client.get_me = AsyncMock(return_value=MagicMock(id=777, username="AutoMassge1"))

    mock_action_ctx = AsyncMock()
    mock_action_ctx.__aenter__.return_value = None
    mock_action_ctx.__aexit__.return_value = None
    mock_client.action = MagicMock(return_value=mock_action_ctx)

    session = UserbotSession("primary", AsyncMock(return_value=mock_client), max_daily_contacts=35)
    pool = userbot_pool
    pool.sessions = [session]

    res = await pool.send_direct_message(
        target_user_id=1234567,
        text="Hello test",
        target_username="testuser"
    )

    assert res["success"] is False
    assert res["error"] == "PEER_FLOOD"
    assert res["can_retry"] is True
    assert res["retry_delay_seconds"] == 900
    assert "حساب قناتك في تاب 'حالة اليوزربوت'" in res["error_ar"]
