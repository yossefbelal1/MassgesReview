import os
import sys
import uuid
import time
import asyncio
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.services.job_engine import (
    claim_next_job,
    recover_expired_leases,
    update_worker_heartbeat,
    process_claimed_job
)
from backend.app.services.telegram_service import telegram_service

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"

class ReviewFlowWorker:
    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self.running = True
        self.worker_id = WORKER_ID
        self.last_recovery_time = 0

    async def run(self):
        print("=" * 65)
        print(f"⚙️ [ReviewFlow Authoritative Worker] Started as {self.worker_id}")
        print("=" * 65)

        # Initialize MTProto client
        client = await telegram_service.get_client()

        while self.running:
            try:
                db: Session = SessionLocal()

                # 1. Update persistent worker heartbeat
                update_worker_heartbeat(
                    db,
                    worker_id=self.worker_id,
                    details={"service": "standalone_worker", "status": "active"}
                )

                # 2. Concurrency-safe lease recovery every 30 seconds
                if time.time() - self.last_recovery_time > 30:
                    recovered = recover_expired_leases(db, worker_id=self.worker_id)
                    if recovered > 0:
                        print(f"[🔄 Lease Recovery]: Recovered {recovered} orphaned jobs with expired leases.")
                    self.last_recovery_time = time.time()

                # 3. Atomically claim next job using row-level locking
                job = claim_next_job(db, worker_id=self.worker_id, lease_duration_seconds=60)
                if job:
                    print(f"\n[⚡ Claimed Job {job.id[:8]}]: Channel {job.channel_id} | Trigger '{job.trigger_text}'")
                    await process_claimed_job(db, client, job, self.worker_id)
                    db.close()
                    continue  # Check for next job immediately without delay

                db.close()
            except Exception as e:
                print(f"[!] Worker loop error: {e}", flush=True)

            await asyncio.sleep(self.poll_interval)

    def stop(self):
        self.running = False
        db: Session = SessionLocal()
        update_worker_heartbeat(db, worker_id=self.worker_id, details={"status": "stopped"})
        db.close()
        print(f"[✓] Worker {self.worker_id} stopped cleanly.")

if __name__ == "__main__":
    worker = ReviewFlowWorker(poll_interval=1.0)
    try:
        asyncio.run(worker.run())
    except (KeyboardInterrupt, SystemExit):
        worker.stop()
