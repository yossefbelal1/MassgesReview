import pytest

def test_admin_stats_protected_from_customer(client, tenant_a):
    res = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {tenant_a['token']}"})
    assert res.status_code == 403
    assert "Admin privileges required" in res.json()["detail"]

def test_admin_stats_accessible_by_admin(client, admin_user):
    res = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {admin_user['token']}"})
    assert res.status_code == 200
    data = res.json()
    assert "total_customers" in data
    assert "active_subscriptions" in data
