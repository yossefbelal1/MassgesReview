from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import Job, User
from backend.app.schemas.schemas import JobOut
from backend.app.api.deps import get_current_active_customer

router = APIRouter()

@router.get("/", response_model=List[JobOut])
def get_jobs(
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).filter(
        Job.tenant_id == current_user.tenant_id
    ).order_by(Job.execute_at.desc()).limit(100).all()
    return jobs

@router.get("/upcoming", response_model=List[JobOut])
def get_upcoming_jobs(
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).filter(
        Job.tenant_id == current_user.tenant_id,
        Job.status.in_(["PENDING", "CLAIMED", "RUNNING", "RETRY_SCHEDULED"])
    ).order_by(Job.execute_at.asc()).limit(20).all()
    return jobs
