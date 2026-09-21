import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Tenant, User, Channel, ChannelUserbot, UserbotLoginAttempt
)
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service


def test_channel_userbot_model_crud(db: Session, tenant_a: dict):
    user = tenant_a["user"]

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100111222333",
        title="Forex Signals Pro",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # 1. Create ChannelUserbot
    userbot = ChannelUserbot(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        api_id=1234567,
        api_hash="abcdef0123456789abcdef0123456789",
        phone="+966501234567",
        string_session="1BJWap1wBu8...",
        telegram_user_id="99887766",
        username="ForexSignalsSupport",
        first_name="Forex Support",
        is_active=True,
        status="CONNECTED",
        daily_contacts_count=5
    )
    db.add(userbot)
    db.commit()
    db.refresh(userbot)

    assert userbot.id is not None
    assert userbot.channel_id == channel.id
    assert channel.userbot.id == userbot.id
    assert channel.userbot.username == "ForexSignalsSupport"

    # 2. Query through Channel
    fetched = db.query(ChannelUserbot).filter(ChannelUserbot.channel_id == channel.id).first()
    assert fetched is not None
    assert fetched.phone == "+966501234567"
    assert fetched.status == "CONNECTED"


def test_userbot_api_endpoints_flow(client: TestClient, db: Session, tenant_a: dict):
    user = tenant_a["user"]
    token = tenant_a["token"]
    headers = {"Authorization": f"Bearer {token}"}

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100444555666",
        title="Gold Scalping VIP",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # 1. Initially no userbot
    res = client.get(f"/api/v1/retention/userbot/{channel.id}", headers=headers)
    assert res.status_code == 200
    assert res.json() is None

    # 2. Mock request-code
    with patch("backend.app.services.dedicated_userbot_service.TelegramClient") as MockTelethonClient, \
         patch("backend.app.services.dedicated_userbot_service.StringSession") as MockStringSession:
        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock()
        mock_instance.send_code_request = AsyncMock(return_value=MagicMock(phone_code_hash="mock_hash_123"))
        mock_instance.session = MagicMock(save=MagicMock(return_value="mock_temp_session"))
        mock_instance.disconnect = AsyncMock()
        MockTelethonClient.return_value = mock_instance

        req_payload = {
            "channel_id": channel.id,
            "api_id": 9876543,
            "api_hash": "hash1234567890abcdef1234567890ab",
            "phone": "+966509998877"
        }
        res = client.post("/api/v1/retention/userbot/request-code", json=req_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["phone_code_hash"] == "mock_hash_123"
        login_attempt_id = data["login_attempt_id"]

        # 3. Mock verify-code (normal success)
        mock_me = MagicMock(id=123456789, username="GoldVipSupport", first_name="Gold VIP Support")
        mock_instance.sign_in = AsyncMock()
        mock_instance.get_me = AsyncMock(return_value=mock_me)
        mock_instance.session.save.return_value = "mock_final_session_saved"

        verify_payload = {
            "login_attempt_id": login_attempt_id,
            "code": "12345"
        }
        res_v = client.post("/api/v1/retention/userbot/verify-code", json=verify_payload, headers=headers)
        assert res_v.status_code == 200
        v_data = res_v.json()
        assert v_data["success"] is True
        assert v_data["needs_2fa"] is False
        assert v_data["userbot"]["username"] == "GoldVipSupport"

    # 4. Check userbot status now
    res = client.get(f"/api/v1/retention/userbot/{channel.id}", headers=headers)
    assert res.status_code == 200
    ub_data = res.json()
    assert ub_data is not None
    assert ub_data["username"] == "GoldVipSupport"
    assert ub_data["status"] == "CONNECTED"
    assert ub_data["phone"] == "+966509998877"

    # 5. Disconnect userbot
    res_del = client.delete(f"/api/v1/retention/userbot/{channel.id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Check that it's disconnected
    res_check = client.get(f"/api/v1/retention/userbot/{channel.id}", headers=headers)
    assert res_check.status_code == 200
    assert res_check.json() is None


@pytest.mark.asyncio
async def test_dedicated_userbot_send_direct_message(db: Session, tenant_a: dict):
    user = tenant_a["user"]

    channel = Channel(
        tenant_id=user.tenant_id,
        telegram_chat_id="-100777888999",
        title="Crypto Signals Channel",
        is_connected=True,
        bot_is_admin=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    userbot = ChannelUserbot(
        tenant_id=user.tenant_id,
        channel_id=channel.id,
        api_id=1234567,
        api_hash="hashhashhashhashhashhashhashhash",
        phone="+966501112233",
        string_session="test_session_str",
        telegram_user_id="888999000",
        username="CryptoSupportBot",
        first_name="Crypto Bot",
        is_active=True,
        status="CONNECTED",
        daily_contacts_count=0
    )
    db.add(userbot)
    db.commit()
    db.refresh(userbot)

    # Mock get_client_for_channel
    mock_client = AsyncMock()
    mock_sent_msg = MagicMock(id=991122)
    mock_client.send_message = AsyncMock(return_value=mock_sent_msg)

    with patch.object(dedicated_userbot_service, "get_client_for_channel", return_value=mock_client):
        res = await dedicated_userbot_service.send_direct_message_for_channel(
            db=db,
            channel_id=channel.id,
            target_user_id=554433221,
            text="Hello from dedicated bot!",
            target_username="trader123"
        )

        assert res["success"] is True
        assert res["is_dedicated"] is True
        assert res["telegram_message_id"] == "991122"

        # Check that daily contacts count incremented
        db.refresh(userbot)
        assert userbot.daily_contacts_count == 1
