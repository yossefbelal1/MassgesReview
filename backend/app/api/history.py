from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import PublishingHistory, User
from backend.app.schemas.schemas import PublishingHistoryOut
from backend.app.api.deps import get_current_active_customer

router = APIRouter()

@router.get("/", response_model=List[PublishingHistoryOut])
def get_publishing_history(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    query = db.query(PublishingHistory).filter(
        PublishingHistory.tenant_id == current_user.tenant_id
    )
    if status:
        query = query.filter(PublishingHistory.status == status)
    
    history = query.order_by(PublishingHistory.published_at.desc()).limit(150).all()
    return history
