import sys
import asyncio
import logging
from backend.app.core.database import SessionLocal
from backend.app.models.models import UserbotLoginAttempt
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service
from backend.app.services.retention_engine import retention_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("complete_login")

TENANT_ID = "35a9ed01-05f3-4056-8da2-45598469d646"

async def complete_login(code: str, password: str = None):
    db = SessionLocal()
    try:
        # Find latest login attempt for this tenant
        attempt = db.query(UserbotLoginAttempt).filter(
            UserbotLoginAttempt.tenant_id == TENANT_ID
        ).order_by(UserbotLoginAttempt.created_at.desc()).first()

        if not attempt:
            print("ERROR: No active login attempt found for this tenant.")
            return

        print(f"Verifying login attempt {attempt.id} for phone {attempt.phone} with code: {code}...")
        result = await dedicated_userbot_service.verify_login_code(
            db=db,
            tenant_id=TENANT_ID,
            login_attempt_id=attempt.id,
            code=code,
            password=password
        )

        print("--- VERIFY RESULT ---")
        print("SUCCESS:", result.get("success"))
        print("NEEDS_2FA:", result.get("needs_2fa"))
        print("MESSAGE:", result.get("message"))
        print("USERBOT:", result.get("userbot"))

        if result.get("success") and not result.get("needs_2fa"):
            # Trigger pending recovery contacts immediately
            asyncio.create_task(retention_engine.process_pending_recovery_contacts(db))
            print("TRIGGERED: Pending recovery contacts loop started!")

    except Exception as e:
        logger.error(f"Verification error: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python complete_userbot_login.py <CODE> [2FA_PASSWORD]")
        sys.exit(1)
    otp_code = sys.argv[1]
    pwd = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(complete_login(otp_code, pwd))
