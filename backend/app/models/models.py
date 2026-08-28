import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Float, Enum, JSON, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    channels = relationship("Channel", back_populates="tenant", cascade="all, delete-orphan")
    messages = relationship("MessageLibrary", back_populates="tenant", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="tenant", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="tenant", cascade="all, delete-orphan")
    history = relationship("PublishingHistory", back_populates="tenant", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="customer")  # "admin" or "customer"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="users")

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    price_monthly = Column(Float, default=0.0)
    max_channels = Column(Integer, default=1)
    max_automations = Column(Integer, default=10)
    max_messages = Column(Integer, default=100)
    max_daily_executions = Column(Integer, default=500)
    features = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="plan")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    status = Column(String, default="active")  # trial, active, expiring, grace_period, expired, suspended
    starts_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    grace_period_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")

class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    telegram_chat_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    username = Column(String, nullable=True)
    is_connected = Column(Boolean, default=True)
    bot_is_admin = Column(Boolean, default=True)
    can_post = Column(Boolean, default=True)
    can_forward = Column(Boolean, default=True)
    verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_message_id = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_channel_tenant_chat", "tenant_id", "telegram_chat_id"),
    )

    tenant = relationship("Tenant", back_populates="channels")
    automations = relationship("Automation", back_populates="channel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="channel", cascade="all, delete-orphan")

class MessageLibrary(Base):
    __tablename__ = "message_library"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    source_chat_id = Column(String, nullable=False)
    source_message_id = Column(Integer, nullable=False)
    text_preview = Column(Text, nullable=True)
    media_type = Column(String, default="text")  # text, photo, video, document
    category = Column(String, default="Results")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="messages")
    steps = relationship("AutomationStep", back_populates="message")

class Automation(Base):
    __tablename__ = "automations"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    trigger_type = Column(String, default="contains")  # contains, exact, prefix, regex
    trigger_value = Column(String, nullable=False)
    reviews_count = Column(Integer, default=2)  # Number of reviews to forward (e.g. 1 to 5)
    initial_delay_seconds = Column(Float, default=5.0)  # Delay before the first review starts
    delay_seconds = Column(Float, default=4.0)  # Base delay between subsequent reviews
    is_active = Column(Boolean, default=True)
    total_executions = Column(Integer, default=0)
    last_executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_auto_tenant_channel", "tenant_id", "channel_id", "is_active"),
    )

    tenant = relationship("Tenant", back_populates="automations")
    channel = relationship("Channel", back_populates="automations")
    steps = relationship("AutomationStep", back_populates="automation", cascade="all, delete-orphan", order_by="AutomationStep.step_order")
    jobs = relationship("Job", back_populates="automation", cascade="all, delete-orphan")

class AutomationStep(Base):
    __tablename__ = "automation_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    automation_id = Column(String, ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String, ForeignKey("message_library.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    delay_seconds = Column(Integer, default=30)  # Delay before sending this message

    automation = relationship("Automation", back_populates="steps")
    message = relationship("MessageLibrary", back_populates="steps")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    automation_id = Column(String, ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    trigger_message_id = Column(String, nullable=True)
    trigger_text = Column(String, nullable=True)
    current_step = Column(Integer, default=1)
    total_steps = Column(Integer, default=1)
    status = Column(String, default="PENDING")  # PENDING, CLAIMED, RUNNING, COMPLETED, FAILED, RETRY_SCHEDULED
    execute_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    attempts = Column(Integer, default=0)
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_job_tenant_status", "tenant_id", "status"),
        Index("idx_job_status_execute", "status", "execute_at"),
        Index("idx_job_lease", "status", "lease_expires_at"),
    )

    tenant = relationship("Tenant", back_populates="jobs")
    automation = relationship("Automation", back_populates="jobs")
    channel = relationship("Channel", back_populates="jobs")
    history = relationship("PublishingHistory", back_populates="job")

class PublishingHistory(Base):
    __tablename__ = "publishing_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    channel_id = Column(String, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    message_title = Column(String, nullable=True)
    automation_name = Column(String, nullable=True)
    step_number = Column(Integer, default=1)
    status = Column(String, default="SUCCESS")  # PUBLISHING, SUCCESS, ASSUMED_DELIVERED, FAILED, FLOOD_WAIT
    telegram_message_id = Column(String, nullable=True)
    error_details = Column(Text, nullable=True)
    published_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_history_tenant_published", "tenant_id", "published_at"),
        Index("idx_history_job_step", "job_id", "step_number"),
    )

    tenant = relationship("Tenant", back_populates="history")
    job = relationship("Job", back_populates="history")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_audit_tenant_created", "tenant_id", "created_at"),
    )

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id = Column(String, primary_key=True, default=generate_uuid)
    worker_id = Column(String, unique=True, index=True, nullable=False)
    hostname = Column(String, nullable=True)
    status = Column(String, default="active")  # active, stopping, dead
    last_heartbeat_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(JSON, default=dict)
