import pytest
from backend.app.models.models import Channel, Automation, PublishingHistory

def test_tenant_isolation_channels(client, db, tenant_a, tenant_b):
    # 1. Create a channel for Tenant A
    ch_a = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-1001111111111",
        title="Tenant A Channel",
        username="tenant_a_channel",
        is_connected=True
    )
    db.add(ch_a)
    db.commit()

    # 2. Query channels as Tenant A -> should see 1 channel
    res_a = client.get("/api/v1/channels/", headers={"Authorization": f"Bearer {tenant_a['token']}"})
    assert res_a.status_code == 200
    channels_a = res_a.json()
    assert len(channels_a) == 1
    assert channels_a[0]["title"] == "Tenant A Channel"

    # 3. Query channels as Tenant B -> should see 0 channels (strict isolation!)
    res_b = client.get("/api/v1/channels/", headers={"Authorization": f"Bearer {tenant_b['token']}"})
    assert res_b.status_code == 200
    channels_b = res_b.json()
    assert len(channels_b) == 0

    # 4. Tenant B tries to delete Tenant A's channel -> must return 404
    res_delete = client.delete(f"/api/v1/channels/{ch_a.id}", headers={"Authorization": f"Bearer {tenant_b['token']}"})
    assert res_delete.status_code == 404

def test_tenant_isolation_automations(client, db, tenant_a, tenant_b):
    # 1. Setup channel and automation for Tenant A
    ch_a = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-1001111111112",
        title="Tenant A Auto Channel",
        is_connected=True
    )
    db.add(ch_a)
    db.flush()

    auto_a = Automation(
        tenant_id=tenant_a["tenant"].id,
        channel_id=ch_a.id,
        name="Tenant A TP1 Trigger",
        trigger_type="contains",
        trigger_value="TP1",
        reviews_count=2,
        is_active=True
    )
    db.add(auto_a)
    db.commit()

    # 2. Tenant B listing automations -> cannot see Tenant A's automation
    res_b = client.get("/api/v1/automations/", headers={"Authorization": f"Bearer {tenant_b['token']}"})
    assert res_b.status_code == 200
    assert len(res_b.json()) == 0

    # 3. Tenant B tries to modify Tenant A's automation -> 404 Not Found
    res_update = client.put(
        f"/api/v1/automations/{auto_a.id}",
        json={"name": "Hacked by B"},
        headers={"Authorization": f"Bearer {tenant_b['token']}"}
    )
    assert res_update.status_code == 404

    # 4. Tenant B tries to create an automation attached to Tenant A's channel -> 404 Channel not found
    res_cross_create = client.post(
        "/api/v1/automations/",
        json={
            "channel_id": ch_a.id,
            "name": "Malicious Auto",
            "trigger_type": "contains",
            "trigger_value": "ATTACK",
            "reviews_count": 2
        },
        headers={"Authorization": f"Bearer {tenant_b['token']}"}
    )
    assert res_cross_create.status_code == 404

def test_tenant_isolation_publishing_history(client, db, tenant_a, tenant_b):
    hist_a = PublishingHistory(
        tenant_id=tenant_a["tenant"].id,
        message_title="Review for A",
        automation_name="Auto A",
        status="SUCCESS"
    )
    db.add(hist_a)
    db.commit()

    # Tenant B queries history -> receives empty list
    res = client.get("/api/v1/history/", headers={"Authorization": f"Bearer {tenant_b['token']}"})
    assert res.status_code == 200
    assert len(res.json()) == 0
