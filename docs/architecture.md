# ReviewFlow Architecture

## System Overview

ReviewFlow is structured into discrete layers:

```
[ Telegram Channels ]  <--- MTProto Events --->  [ Telegram Engine (Telethon) ]
                                                            |
                                                   [ Event State Machine ]
                                                            |
                                                   [ PostgreSQL / SQLite ]
                                                            ^
                                                            |
[ React 18 Dashboard ] <--- REST API (FastAPI) ---> [ Application Services ]
```

## Core Components

1. **API / Control Plane (FastAPI)**: Handles JWT authentication, channel management, automation configuration, analytics, and admin operations.
2. **Persistence Layer (SQLAlchemy & Alembic)**: Relational schema enforcing multi-tenancy, foreign keys, cascade deletes, and composite indexes.
3. **Telegram Engine (Telethon)**: Dual-layer listener and watcher polling connected channels, matching triggers, and forwarding reviews from the verified central repository with randomized human timing jitter.
4. **Security Middleware**: Enforces rate limiting, CORS allowlisting, and security response headers.
