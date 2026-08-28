import pytest
from backend.app.models.models import Channel

def test_starter_plan_channel_limit_enforcement(client, db, tenant_a):
    # Tenant A has Starter plan (max_channels = 1)
    ch1 = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-1001112223334",
        title="Channel 1",
        is_connected=True
    )
    db.add(ch1)
    db.commit()

    # Attempting to join/add a 2nd channel must be rejected by server with 403 Forbidden
    response = client.post(
        "/api/v1/channels/join",
        json={"telegram_chat_id": "https://t.me/second_channel"},
        headers={"Authorization": f"Bearer {tenant_a['token']}"}
    )
    assert response.status_code == 403
    assert "أقصى" in response.json()["detail"] or "limit" in response.json()["detail"].lower()

    # Attempting verify on 2nd channel must also be rejected with 403 Forbidden
    resp_verify = client.post(
        "/api/v1/channels/verify",
        json={"telegram_chat_id": "https://t.me/second_channel"},
        headers={"Authorization": f"Bearer {tenant_a['token']}"}
    )
    assert resp_verify.status_code == 403
    assert "أقصى" in resp_verify.json()["detail"] or "limit" in resp_verify.json()["detail"].lower()

