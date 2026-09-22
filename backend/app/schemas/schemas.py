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
    title: Optional[str] = ""
    username: Optional[str] = None

class ChannelCreate(ChannelBase):
    pass

class ChannelOut(ChannelBase):
    id: str
    tenant_id: str
    is_connected: bool
    bot_is_admin: bool
    backup_bot_is_admin: bool = False
    health_status: str = "HEALTHY"
    last_health_warning: Optional[str] = None
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
    channel_id: Optional[str] = None
    channel_ids: Optional[List[str]] = []
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
    channel_id: str
    total_executions: int
    last_executed_at: Optional[datetime]
    created_at: datetime
    channel: Optional[ChannelOut] = None
    steps: List[AutomationStepOut] = []
    class Config:
        from_attributes = True

class AutomationUpdateAdmin(BaseModel):
    name: Optional[str] = None
    channel_id: Optional[str] = None
    trigger_type: Optional[str] = "contains"
    trigger_value: Optional[str] = None
    reviews_count: Optional[int] = 2
    initial_delay_seconds: Optional[float] = 5.0
    delay_seconds: Optional[float] = 4.0
    is_active: Optional[bool] = True

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

class SubscriptionUpdateAdmin(BaseModel):
    plan_slug: Optional[str] = None
    status: Optional[str] = None
    days_to_add: Optional[int] = None
    expires_at: Optional[datetime] = None

class AdminResetPassword(BaseModel):
    new_password: str

# Retention & Win-back Schemas
class RetentionSettingBase(BaseModel):
    is_retention_enabled: bool = True
    is_welcome_enabled: bool = False
    initial_delay_seconds: int = 180
    welcome_message_template: Optional[str] = None
    recovery_first_message_template: Optional[str] = None
    invite_link: Optional[str] = None
    max_daily_contacts: int = 30

class RetentionSettingUpdate(RetentionSettingBase):
    pass

class RetentionSettingOut(RetentionSettingBase):
    id: str
    tenant_id: str
    channel_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    class Config:
        from_attributes = True

class AudienceMemberOut(BaseModel):
    id: str
    tenant_id: str
    channel_id: str
    telegram_user_id: str
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    status: str
    first_joined_at: datetime
    last_left_at: Optional[datetime]
    last_rejoined_at: Optional[datetime]
    interests: List[Any] = []
    onboarding_status: str
    notes: Optional[str]
    class Config:
        from_attributes = True

class RecoveryMessageOut(BaseModel):
    id: str
    case_id: str
    direction: str
    sender_type: str
    userbot_username: Optional[str]
    text: str
    intent_detected: Optional[str]
    sent_at: datetime
    class Config:
        from_attributes = True

class RecoveryMessageCreate(BaseModel):
    text: str

class RecoveryCaseOut(BaseModel):
    id: str
    tenant_id: str
    channel_id: str
    channel_title: Optional[str] = None
    member_id: Optional[str]
    telegram_user_id: str
    user_full_name: Optional[str] = None
    user_username: Optional[str] = None
    status: str
    contactable: bool
    uncontactable_reason: Optional[str]
    assigned_userbot: Optional[str]
    leave_reason_category: Optional[str]
    leave_reason_raw: Optional[str]
    scheduled_contact_at: Optional[datetime]
    first_contacted_at: Optional[datetime]
    last_response_at: Optional[datetime]
    link_sent_at: Optional[datetime]
    rejoined_at: Optional[datetime]
    time_to_rejoin_seconds: Optional[int]
    created_at: datetime
    direct_telegram_link: Optional[str] = None
    queue_delay_reason: Optional[str] = None
    class Config:
        from_attributes = True

class RecoveryCaseDetailOut(RecoveryCaseOut):
    messages: List[RecoveryMessageOut] = []

class RetentionSummaryOut(BaseModel):
    total_left_detected: int
    total_contact_attempted: int
    total_contacted: int
    total_in_conversation: int
    total_rejoined: int
    total_scheduled_pending: int = 0
    total_opt_out: int = 0
    win_back_rate_percent: float
    uncontactable_count: int
    average_rejoin_hours: float
    reasons_breakdown: List[dict] = []
    daily_trend: List[dict] = []
    funnel_reconciled: bool = True
    funnel_stages: List[dict] = []
    status_distribution: List[dict] = []
    hourly_distribution: List[dict] = []
    response_rate_percent: float = 0.0
    conversion_on_response_percent: float = 0.0

# Dedicated Channel Userbot Schemas
class UserbotSendCodeRequest(BaseModel):
    channel_id: str
    phone: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None

class UserbotSendCodeResponse(BaseModel):
    success: bool
    login_attempt_id: str
    phone_code_hash: str
    message: str

class UserbotVerifyCodeRequest(BaseModel):
    login_attempt_id: str
    code: str
    password: Optional[str] = None

class ChannelUserbotProfile(BaseModel):
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    phone: Optional[str] = None

class UserbotVerifyCodeResponse(BaseModel):
    success: bool
    needs_2fa: bool = False
    message: str
    userbot: Optional[ChannelUserbotProfile] = None

class ChannelUserbotOut(BaseModel):
    id: str
    channel_id: str
    phone: str
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_active: bool
    status: str
    daily_contacts_count: int
    last_error: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True



