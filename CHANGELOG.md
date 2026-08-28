# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-28

### Added
- Enterprise multi-tenant architecture with tenant-isolated database models.
- Dual-layer MTProto listener and watcher engine for sub-second keyword detection.
- Configurable initial start delay (تأخير بدء الإرسال) and human timing jitter.
- 3-Step channel onboarding wizard supporting large channels (>200 subscribers).
- Server-side plan limit enforcement (Starter, Pro, VIP) with atomic quotas.
- Real-time dependency health checks (`/health/live`, `/health/ready`, `/health/deps`).
- Alembic database migration pipeline.
- Comprehensive automated Pytest test suite covering Auth, Multi-Tenancy, Health, and Plans.
- Production multi-stage Dockerfiles and isolated Docker Compose networks.
- Comprehensive technical documentation in `docs/`.

### Security
- Eliminated hardcoded Telegram credentials and JWT secrets.
- Implemented strict 401/403 authorization semantics across all protected routes.
- Enforced rate limiting and security headers middleware.
- Restricted Docker network access to private internal bridge for PostgreSQL and Redis.
