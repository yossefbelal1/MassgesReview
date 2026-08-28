# Security Architecture & Policies

## Multi-Tenancy Isolation
Every query to channels, automations, messages, and publishing history is scoped by `tenant_id`. Cross-tenant manipulation is rejected at the database and API levels with 404/403 responses.

## Credential Management
- No raw session strings or API hashes are committed to source control.
- In production (`ENVIRONMENT=production`), the application validates that strong unique secrets are present, failing startup immediately if missing.

## Telegram Session Protection
Telegram session credentials are kept in secure persistent storage or injected via environment variables (`TELEGRAM_STRING_SESSION`).
