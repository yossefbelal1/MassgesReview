import time
import os
import psutil
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.core.database import get_db
from backend.app.services.telegram_service import telegram_service

router = APIRouter()
START_TIME = time.time()

@router.get("/live")
def liveness():
    """Liveness probe: returns 200 OK if the API process is alive."""
    return {"status": "alive", "timestamp": time.time()}

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
        "status": "ready" if is_ready else "unhealthy",
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

    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    overall_healthy = (db_status == "healthy") and (tg_health["status"] != "unhealthy")
    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if overall_healthy else "degraded",
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
            "telegram_engine": tg_health
        }
    }
