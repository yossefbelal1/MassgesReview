# Contributing to ReviewFlow

Thank you for your interest in contributing to ReviewFlow SaaS!

## Development Workflow

1. Fork the repository and create your branch from `main`.
2. Ensure Python 3.10+ and Node.js 20+ are installed.
3. Install backend dependencies: `pip install -r backend/requirements.txt`.
4. Install frontend dependencies: `cd frontend && npm install`.
5. Run the test suite: `pytest backend/tests -v`.
6. Verify frontend build: `cd frontend && npm run build`.
7. Submit a pull request following our PR template.

## Code Standards
- All endpoints must enforce multi-tenant scoping (`tenant_id == current_user.tenant_id`).
- Never commit `.env` files, Telegram session files (`*.session`), or database credentials.
- All new features must include unit or integration tests in `backend/tests/`.
