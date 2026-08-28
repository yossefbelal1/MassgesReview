import os
import sys
import time
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.models import Job, Automation, AutomationStep, Channel, MessageLibrary, PublishingHistory, Subscription
from backend.app.services.telegram_service import telegram_service

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

class ReviewFlowWorker:
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.running = True

    def recover_stuck_jobs(self):
        """Recovery: Find jobs stuck in CLAIMED/RUNNING due to unexpected crash and recover them"""
        db: Session = SessionLocal()
        try:
            stuck_jobs = db.query(Job).filter(Job.status.in_(["CLAIMED", "RUNNING"])).all()
            if stuck_jobs:
                print(f"[🔄 Recovery] Found {len(stuck_jobs)} stuck jobs from previous run. Recovering...")
                for j in stuck_jobs:
                    j.status = "PENDING"
                    j.error_message = "Recovered from worker restart"
                db.commit()
                print("[✓ Recovery] All stuck jobs reset to PENDING.")
        except Exception as e:
            print(f"[❌ Recovery Error] {e}")
        finally:
            db.close()

    async def process_job(self, job_id: str):
        db: Session = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or job.status not in ["PENDING", "RETRY_SCHEDULED"]:
                return

            # Check tenant subscription status
            tenant = job.tenant
            if not tenant or not tenant.is_active:
                job.status = "FAILED"
                job.error_message = "Tenant is inactive"
                db.commit()
                return

            sub = tenant.subscription
            now = datetime.now(timezone.utc)
            if sub:
                exp_at = sub.expires_at
                if exp_at.tzinfo is None:
                    exp_at = exp_at.replace(tzinfo=timezone.utc)
                if sub.status not in ["active", "trial", "grace_period"] or exp_at < now:
                    job.status = "FAILED"
                    job.error_message = "Customer subscription has expired or suspended"
                    db.commit()
                    return

            # Mark as RUNNING
            job.status = "RUNNING"
            job.attempts += 1
            db.commit()

            automation = job.automation
            channel = job.channel
            if not automation or not channel or not channel.is_connected:
                job.status = "FAILED"
                job.error_message = "Automation or Channel not found or disconnected"
                db.commit()
                return

            # Find current step
            steps = db.query(AutomationStep).filter(
                AutomationStep.automation_id == automation.id
            ).order_by(AutomationStep.step_order.asc()).all()

            if not steps or job.current_step > len(steps):
                job.status = "COMPLETED"
                db.commit()
                return

            current_step_obj = steps[job.current_step - 1]
            msg: MessageLibrary = current_step_obj.message

            if not msg or not msg.is_active:
                job.status = "FAILED"
                job.error_message = f"Message #{current_step_obj.message_id} is missing or inactive"
                db.commit()
                return

            print(f"\n[⚡ Worker Executing] Job: {job.id[:8]} | Tenant: {tenant.name} | Step {job.current_step}/{job.total_steps} -> Forwarding '{msg.title}' to '{channel.title}'")

            # Forward message
            res = await telegram_service.forward_message(
                source_chat_id=msg.source_chat_id,
                source_msg_id=msg.source_message_id,
                target_chat_id=channel.telegram_chat_id
            )

            if res.get("flood_wait"):
                wait_sec = res.get("wait_seconds", 60)
                print(f"[⚠️ FloodWait] Telegram requested wait of {wait_sec}s for Job {job.id[:8]}")
                job.status = "RETRY_SCHEDULED"
                job.execute_at = now + timedelta(seconds=wait_sec + 2)
                job.error_message = f"FloodWait: retry in {wait_sec}s"

                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    job_id=job.id,
                    channel_id=channel.id,
                    message_title=msg.title,
                    automation_name=automation.name,
                    step_number=job.current_step,
                    status="FLOOD_WAIT",
                    error_details=f"FloodWait: {wait_sec}s"
                ))
                db.commit()
                return

            if not res.get("success"):
                err = res.get("error", "Unknown forwarding error")
                print(f"[❌ Step Failed] {err}")
                job.status = "FAILED"
                job.error_message = err

                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    job_id=job.id,
                    channel_id=channel.id,
                    message_title=msg.title,
                    automation_name=automation.name,
                    step_number=job.current_step,
                    status="FAILED",
                    error_details=err
                ))
                db.commit()
                return

            # Log Success
            telegram_msg_id = res.get("message_id")
            db.add(PublishingHistory(
                tenant_id=tenant.id,
                job_id=job.id,
                channel_id=channel.id,
                message_title=msg.title,
                automation_name=automation.name,
                step_number=job.current_step,
                status="SUCCESS",
                telegram_message_id=telegram_msg_id
            ))

            # Schedule next step or complete
            if job.current_step < len(steps):
                next_step_obj = steps[job.current_step]
                delay = next_step_obj.delay_seconds
                job.current_step += 1
                job.status = "PENDING"
                job.execute_at = now + timedelta(seconds=delay)
                print(f"[⏳ Next Step Scheduled] Step {job.current_step}/{job.total_steps} scheduled in {delay} seconds (at {job.execute_at.strftime('%H:%M:%S')})")
            else:
                job.status = "COMPLETED"
                print(f"[🎉 Job Completed] All {job.total_steps} steps finished successfully for Job {job.id[:8]}!")

            db.commit()

        except Exception as e:
            print(f"[❌ Worker Job Error] {e}")
            db.rollback()
        finally:
            db.close()

    async def run(self):
        print("=" * 60)
        print("⚙️ [ReviewFlow Worker Engine] Started & Listening for Jobs...")
        print("=" * 60)
        self.recover_stuck_jobs()

        while self.running:
            try:
                db: Session = SessionLocal()
                now = datetime.now(timezone.utc)
                
                # Fetch pending jobs ready to execute
                jobs = db.query(Job).filter(
                    Job.status.in_(["PENDING", "RETRY_SCHEDULED"]),
                    Job.execute_at <= now
                ).order_by(Job.execute_at.asc()).limit(10).all()

                job_ids = [j.id for j in jobs]
                db.close()

                for j_id in job_ids:
                    await self.process_job(j_id)

            except Exception as e:
                print(f"[Worker Loop Error] {e}")

            await asyncio.sleep(self.poll_interval)

if __name__ == "__main__":
    worker = ReviewFlowWorker()
    asyncio.run(worker.run())
