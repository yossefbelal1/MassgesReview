from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Auth & User
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class TokenData(BaseModel):
    user_id: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    company_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(UserBase):
    id: str
    tenant_id: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

# Plan & Subscription
class PlanBase(BaseModel):
    name: str
    slug: str
    price_monthly: float
    max_channels: int
    max_automations: int
    max_messages: int
    max_daily_executions: int
    features: List[str] = []
    is_active: bool = True

class PlanCreate(PlanBase):
    pass

class PlanOut(PlanBase):
    id: str
    class Config:
        from_attributes = True

class SubscriptionOut(BaseModel):
    id: str
    tenant_id: str
    plan: PlanOut
    status: str
    starts_at: datetime
    expires_at: datetime
    grace_period_until: Optional[datetime]
    class Config:
        from_attributes = True

# Channel
class ChannelBase(BaseModel):
    telegram_chat_id: str
    title: str
    username: Optional[str] = None

class ChannelCreate(ChannelBase):
    pass

class ChannelOut(ChannelBase):
    id: str
    tenant_id: str
    is_connected: bool
    bot_is_admin: bool
    can_post: bool
    can_forward: bool
    verified_at: Optional[datetime]
    created_at: datetime
    class Config:
        from_attributes = True

# Message Library
class MessageLibraryBase(BaseModel):
    title: str
    source_chat_id: str
    source_message_id: int
    text_preview: Optional[str] = None
    media_type: str = "text"
    category: str = "Results"
    is_active: bool = True

class MessageLibraryCreate(MessageLibraryBase):
    pass

class MessageLibraryOut(MessageLibraryBase):
    id: str
    tenant_id: str
    created_at: datetime
    class Config:
        from_attributes = True

# Automation Steps & Automation
class AutomationStepBase(BaseModel):
    message_id: str
    step_order: int
    delay_seconds: int = 30

class AutomationStepCreate(AutomationStepBase):
    pass

class AutomationStepOut(AutomationStepBase):
    id: str
    message: Optional[MessageLibraryOut] = None
    class Config:
        from_attributes = True

class AutomationBase(BaseModel):
    channel_id: str
    name: str
    trigger_type: str = "contains"
    trigger_value: str
    reviews_count: int = 2
    initial_delay_seconds: float = 5.0
    delay_seconds: float = 4.0
    is_active: bool = True

class AutomationCreate(AutomationBase):
    steps: Optional[List[AutomationStepCreate]] = []

class AutomationOut(AutomationBase):
    id: str
    tenant_id: str
    total_executions: int
    last_executed_at: Optional[datetime]
    created_at: datetime
    channel: Optional[ChannelOut] = None
    steps: List[AutomationStepOut] = []
    class Config:
        from_attributes = True

# Jobs & History
class JobOut(BaseModel):
    id: str
    tenant_id: str
    automation_id: str
    channel_id: str
    idempotency_key: str
    trigger_text: Optional[str]
    current_step: int
    total_steps: int
    status: str
    execute_at: datetime
    attempts: int
    error_message: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class PublishingHistoryOut(BaseModel):
    id: str
    tenant_id: str
    channel_id: Optional[str]
    message_title: Optional[str]
    automation_name: Optional[str]
    step_number: int
    status: str
    telegram_message_id: Optional[str]
    error_details: Optional[str]
    published_at: datetime
    class Config:
        from_attributes = True

# Dashboard Stats
class AdminStats(BaseModel):
    total_customers: int
    active_subscriptions: int
    expiring_soon: int
    expired_subscriptions: int
    connected_channels: int
    active_automations: int
    jobs_today: int
    successful_jobs_today: int
    failed_jobs_today: int
    services_status: dict

class CustomerStats(BaseModel):
    subscription_status: str
    days_remaining: int
    plan_name: str
    connected_channels: int
    active_automations: int
    total_messages: int
    published_today: int
    failed_today: int
    upcoming_jobs: List[JobOut] = []
