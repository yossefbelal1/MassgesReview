# Production Deployment Guide

## Architecture Topology

```
Internet -> Reverse Proxy (Nginx / Cloudflare) -> Docker Compose
                                                     ├── FastAPI API (Port 8000)
                                                     ├── Telegram Engine (Worker)
                                                     ├── Frontend (Port 3000 / Nginx)
                                                     ├── PostgreSQL (Internal Network)
                                                     └── Redis (Internal Network)
```

## Deployment Steps

1. **Clone Repository**:
   ```bash
   git clone https://github.com/yossefbelal1/MassgesReview.git
   cd MassgesReview
   ```

2. **Configure Production Environment**:
   ```bash
   cp .env.example .env
   # Edit .env and supply your production SECRET_KEY, TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION
   ```

3. **Deploy with Docker Compose**:
   ```bash
   docker compose up -d --build
   ```

4. **Verify Health**:
   ```bash
   curl http://localhost:8000/api/v1/health/ready
   ```
