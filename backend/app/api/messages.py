from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import MessageLibrary, User, AuditLog
from backend.app.schemas.schemas import MessageLibraryCreate, MessageLibraryOut
from backend.app.api.deps import get_current_active_customer

router = APIRouter()

@router.get("/", response_model=List[MessageLibraryOut])
def get_message_library(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    query = db.query(MessageLibrary).filter(MessageLibrary.tenant_id == current_user.tenant_id)
    if category:
        query = query.filter(MessageLibrary.category == category)
    return query.order_by(MessageLibrary.created_at.desc()).all()

@router.post("/", response_model=MessageLibraryOut)
def add_message_to_library(
    data: MessageLibraryCreate,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    # Check plan limits
    tenant = current_user.tenant
    if tenant and tenant.subscription and tenant.subscription.plan:
        max_allowed = tenant.subscription.plan.max_messages
        current_count = db.query(MessageLibrary).filter(MessageLibrary.tenant_id == tenant.id).count()
        if current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Message library limit reached ({max_allowed} max). Please upgrade your plan."
            )

    msg = MessageLibrary(
        tenant_id=current_user.tenant_id,
        title=data.title,
        source_chat_id=data.source_chat_id,
        source_message_id=data.source_message_id,
        text_preview=data.text_preview,
        media_type=data.media_type,
        category=data.category,
        is_active=data.is_active
    )
    db.add(msg)
    
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="MESSAGE_ADDED_TO_LIBRARY",
        entity_type="MessageLibrary",
        entity_id=msg.id,
        details={"title": msg.title, "source_chat": msg.source_chat_id, "source_id": msg.source_message_id}
    ))

    db.commit()
    db.refresh(msg)
    return msg

@router.delete("/{message_id}")
def delete_message_from_library(
    message_id: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    msg = db.query(MessageLibrary).filter(
        MessageLibrary.id == message_id,
        MessageLibrary.tenant_id == current_user.tenant_id
    ).first()

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    db.delete(msg)
    db.commit()
    return {"message": "Message deleted successfully"}
