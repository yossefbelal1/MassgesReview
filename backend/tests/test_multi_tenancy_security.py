import pytest
from backend.app.models.models import Channel, Automation, Job, PublishingHistory

def test_full_cross_tenant_isolation_matrix(client, db, tenant_a, tenant_b):
    # Setup Tenant B resources
    ch_b = Channel(tenant_id=tenant_b["tenant"].id, telegram_chat_id="-100999000111", title="Tenant B Private Channel", is_connected=True)
    db.add(ch_b)
    db.flush()

    auto_b = Automation(tenant_id=tenant_b["tenant"].id, channel_id=ch_b.id, name="Tenant B Auto", trigger_value="SECRET", is_active=True)
    db.add(auto_b)
    db.flush()

    job_b = Job(tenant_id=tenant_b["tenant"].id, automation_id=auto_b.id, channel_id=ch_b.id, idempotency_key="t_b_job_key_1", trigger_text="SECRET", status="PENDING")
    db.add(job_b)
    db.flush()

    hist_b = PublishingHistory(tenant_id=tenant_b["tenant"].id, channel_id=ch_b.id, job_id=job_b.id, message_title="Secret Review", status="SUCCESS")
    db.add(hist_b)
    db.commit()

    headers_a = {"Authorization": f"Bearer {tenant_a['token']}"}

    # 1. Tenant A cannot GET Tenant B channel
    res = client.get(f"/api/v1/channels/{ch_b.id}", headers=headers_a)
    assert res.status_code in [404, 403]

    # 2. Tenant A cannot DELETE Tenant B channel
    res = client.delete(f"/api/v1/channels/{ch_b.id}", headers=headers_a)
    assert res.status_code in [404, 403]

    # 3. Tenant A cannot GET Tenant B automation
    res = client.get(f"/api/v1/automations/{auto_b.id}", headers=headers_a)
    assert res.status_code in [404, 403]

    # 4. Tenant A cannot PUT/modify Tenant B automation
    res = client.put(f"/api/v1/automations/{auto_b.id}", json={"name": "Hacked", "trigger_value": "HACK"}, headers=headers_a)
    assert res.status_code in [404, 403]

    # 5. Tenant A cannot DELETE Tenant B automation
    res = client.delete(f"/api/v1/automations/{auto_b.id}", headers=headers_a)
    assert res.status_code in [404, 403]

    # 6. Tenant A cannot execute Tenant B automation run-now
    res = client.post(f"/api/v1/automations/{auto_b.id}/run-now", headers=headers_a)
    assert res.status_code in [404, 403]

    # 7. Tenant A cannot create an automation attached to Tenant B's channel
    res = client.post("/api/v1/automations/", json={
        "channel_id": ch_b.id,
        "name": "Cross Tenant Auto",
        "trigger_value": "EXPLOIT"
    }, headers=headers_a)
    assert res.status_code in [404, 403]

    # 8. Tenant A history list contains 0 items from Tenant B
    res = client.get("/api/v1/history/", headers=headers_a)
    assert res.status_code == 200
    assert len(res.json()) == 0
