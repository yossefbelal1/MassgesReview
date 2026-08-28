from datetime import datetime, timezone
import time
import os
import psutil
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.core.database import get_db
from backend.app.models.models import WorkerHeartbeat
from backend.app.services.telegram_service import telegram_service

router = APIRouter()
START_TIME = time.time()

@router.get("/live")
def liveness():
    """Liveness probe: returns 200 OK if the API process is alive."""
    return {"status": "LIVE", "timestamp": time.time()}

@router.get("/ready")
async def readiness(response: Response, db: Session = Depends(get_db)):
    """Readiness probe: returns 200 only if DB and core dependencies can serve traffic."""
    is_ready = True
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        is_ready = False

    tg_health = await telegram_service.get_health_status()
    if tg_health["status"] == "unhealthy":
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "READY" if is_ready else "UNHEALTHY",
        "database": "connected" if db_ok else "unreachable",
        "telegram": tg_health["status"]
    }

@router.get("/")
@router.get("/deps")
async def full_health(response: Response, db: Session = Depends(get_db)):
    """Comprehensive dependency and health inspection endpoint."""
    t0 = time.time()
    db_status = "healthy"
    db_latency_ms = 0.0
    try:
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - t0) * 1000, 2)
    except Exception as e:
        db_status = f"unhealthy: {e}"

    tg_health = await telegram_service.get_health_status()

    # Check worker heartbeat
    now_utc = datetime.now(timezone.utc)
    latest_hb = db.query(WorkerHeartbeat).order_by(WorkerHeartbeat.last_heartbeat_at.desc()).first()
    worker_status = "offline"
    worker_age = None
    if latest_hb and latest_hb.last_heartbeat_at:
        hb_dt = latest_hb.last_heartbeat_at if latest_hb.last_heartbeat_at.tzinfo else latest_hb.last_heartbeat_at.replace(tzinfo=timezone.utc)
        worker_age = round((now_utc - hb_dt).total_seconds(), 1)
        if worker_age < 60:
            worker_status = "healthy"
        elif worker_age < 180:
            worker_status = "degraded"
        else:
            worker_status = "unhealthy"

    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    overall_status = "LIVE"
    if db_status != "healthy":
        overall_status = "UNHEALTHY"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif tg_health["status"] == "unhealthy" or worker_status in ["unhealthy", "offline"]:
        overall_status = "DEGRADED"
    else:
        overall_status = "READY"

    return {
        "status": overall_status,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "services": {
            "api": {
                "status": "healthy",
                "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "cpu_percent": process.cpu_percent()
            },
            "database": {
                "status": "healthy" if db_status == "healthy" else "unhealthy",
                "latency_ms": db_latency_ms,
                "error": db_status if db_status != "healthy" else None
            },
            "worker": {
                "status": worker_status,
                "last_heartbeat_age_seconds": worker_age,
                "worker_id": latest_hb.worker_id if latest_hb else None
            },
            "telegram_engine": tg_health
        }
    }
