# Free Deployment Options Research (2025-2026)

Researched: 2026-03-03
Purpose: Find completely FREE deployment stack for Python FastAPI backend + Next.js frontend trading application

---

## 1. Fly.io

| Item | Detail |
|------|--------|
| **Free Tier Status** | NO free tier for new users. Legacy Hobby Plan (grandfathered) only. New users get a Free Trial only. |
| **Legacy Hobby Plan** | 3x shared-cpu-1x 256MB VMs, 3GB volume storage, 100GB outbound (NA/EU) |
| **Sleep/Spin-down** | Machines can be stopped/started; no auto-sleep on legacy |
| **WebSocket** | Yes |
| **Docker** | Yes (native) |
| **Can run trading bot 24/5?** | NOT possible for new users (no free tier). Legacy users: marginally possible with 256MB RAM |
| **Verdict** | DISQUALIFIED - no free tier for new signups |

## 2. Render.com

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent free tier, no credit card required |
| **Compute** | 512MB RAM, 0.1 vCPU per instance |
| **Limits** | 750 instance hours/month, 100GB outbound bandwidth, 500 build pipeline minutes |
| **Sleep/Spin-down** | YES - sleeps after 15 min of no inbound traffic (HTTP or WebSocket). Cold start on wake. |
| **WebSocket** | Yes, supported. But connection drops when service sleeps. |
| **Docker** | Yes |
| **Free PostgreSQL** | Yes - 1 instance, 1GB storage, 256MB RAM (expires after 90 days) |
| **Can run trading bot 24/5?** | NO - 15-minute sleep kills it. Workaround: external ping every 14 min, but unreliable for trading |
| **Verdict** | POOR for trading bot - sleep is a dealbreaker for real-time trading |

## 3. Railway.app

| Item | Detail |
|------|--------|
| **Free Tier** | NO permanent free tier. 30-day trial with $5 credit, then $1/month free credit |
| **After Trial** | Hobby Plan: $5/month (includes $5 usage credit) |
| **WebSocket** | Yes |
| **Docker** | Yes |
| **Can run trading bot 24/5?** | Not free. $1/month credit after trial is insufficient. |
| **Verdict** | DISQUALIFIED - not truly free |

## 4. Koyeb

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent, no credit card required, commercial use allowed |
| **Compute** | 1 Free Instance: 512MB RAM, 0.1 vCPU, 2GB SSD |
| **Bandwidth** | 100GB outbound/month |
| **Regions** | Free tier limited to Frankfurt or Washington D.C. |
| **Sleep/Spin-down** | YES - scales to zero after ~5 min idle. Light Sleep with 200ms restart. |
| **WebSocket** | Yes (HTTP/2, WebSocket, gRPC supported) |
| **Docker** | Yes (any container registry) |
| **Free PostgreSQL** | Yes, 1 free Postgres database included |
| **Can run trading bot 24/5?** | MARGINAL - 5-min sleep timeout is problematic. Need keep-alive pings. 0.1 vCPU is very weak. |
| **Verdict** | POSSIBLE with keep-alive, but risky for trading due to sleep + low CPU |

## 5. Oracle Cloud (Always Free) -- BEST FOR BACKEND

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, ALWAYS FREE (never expires) |
| **ARM Compute** | Up to 4 OCPUs (Ampere A1) + 24GB RAM total, split across up to 4 VMs |
| **x86 Compute** | 2x AMD VM.Standard.E2.1.Micro (1/8 OCPU, 1GB RAM each) |
| **Storage** | 200GB block volume total, 20GB object storage, 10GB archive |
| **Bandwidth** | 10TB outbound/month (extremely generous) |
| **Network** | 1 public IP, up to 50 Mbps, 1 load balancer (10 Mbps) |
| **Sleep/Spin-down** | NO auto-sleep. But idle instances (<20% CPU over 7 days) may be RECLAIMED. |
| **WebSocket** | Yes (full VM, run anything) |
| **Docker** | Yes (full VM, run anything including Docker/Podman) |
| **Databases** | 2x Always Free Autonomous Databases (20GB each, Oracle or MySQL HeatWave) |
| **Risk** | Idle instance reclamation if <20% CPU for 7 days. Mitigate: convert to PAYG (still free within limits) or run keep-busy script |
| **Can run trading bot 24/5?** | YES - 4 ARM cores + 24GB RAM is MORE than enough. Trading activity keeps CPU above idle threshold. |
| **Verdict** | BEST OPTION for backend. Massively generous. Convert to PAYG to avoid reclamation. |

## 6. Google Cloud (Always Free)

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, ALWAYS FREE components |
| **Compute Engine** | 1x e2-micro: 2 shared vCPU (0.25 baseline), 1GB RAM, 30GB disk |
| **Cloud Run** | 2M requests/month, 360,000 GB-sec memory, 180,000 vCPU-sec, 1GB egress (us-central1/east1/west1 only) |
| **Regions** | Oregon (us-west1), Iowa (us-central1), S. Carolina (us-east1) only for free |
| **Bandwidth** | Only 1GB/month egress for Compute Engine (very low!) |
| **Sleep/Spin-down** | e2-micro: always on. Cloud Run: scales to zero between requests. |
| **WebSocket** | e2-micro: yes. Cloud Run: yes but with timeout limits. |
| **Docker** | e2-micro: yes. Cloud Run: native Docker. |
| **Databases** | 1x Firestore (1GB), but no free PostgreSQL |
| **Can run trading bot 24/5?** | e2-micro BARELY - 1GB RAM is tight for FastAPI + trading logic. Cloud Run not suitable (scales to zero). |
| **Verdict** | POSSIBLE but tight. 1GB RAM is limiting. Good as secondary/fallback. |

## 7. AWS Free Tier

| Item | Detail |
|------|--------|
| **EC2 t2.micro** | 12-MONTH FREE ONLY. 1 vCPU, 1GB RAM, 750 hrs/month. Expires after 1 year. |
| **Lambda** | ALWAYS FREE: 1M invocations/month, 400,000 GB-sec compute |
| **Storage** | 5GB S3, 25GB DynamoDB |
| **Bandwidth** | 100GB outbound (first 12 months), then 1GB/month |
| **Sleep/Spin-down** | EC2: always on. Lambda: cold starts. |
| **WebSocket** | EC2: yes. Lambda: via API Gateway WebSocket (complex). |
| **Docker** | EC2: yes. Lambda: container images supported. |
| **Can run trading bot 24/5?** | EC2: yes but only for 12 months. Lambda: not suitable for persistent connections. |
| **Verdict** | NOT truly free long-term. EC2 expires after 12 months. Lambda unsuitable for trading bot. |

## 8. Vercel

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent (Hobby plan) |
| **Functions** | 150,000 invocations/month, 10s timeout, 100GB bandwidth |
| **Build** | 6,000 build minutes/month |
| **Python Support** | Yes, via ASGI serverless functions (FastAPI works) |
| **WebSocket** | NO - explicitly not supported |
| **Docker** | No |
| **Sleep/Spin-down** | Serverless - no persistent process |
| **Can run trading bot 24/5?** | NO - serverless only, no WebSocket, 10s timeout, no persistent connections |
| **Verdict** | EXCELLENT for Next.js frontend. UNUSABLE for FastAPI trading backend. |

## 9. Cloudflare Workers

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent |
| **Requests** | 100,000 requests/day |
| **CPU Time** | 10ms per invocation (free tier) - very restrictive |
| **Python Support** | Yes (via Pyodide/WASM). FastAPI supported via ASGI. |
| **WebSocket** | Yes (via Durable Objects, but Durable Objects require paid plan $5/month) |
| **Docker** | No |
| **Sleep/Spin-down** | Serverless - no persistent process |
| **Can run trading bot 24/5?** | NO - 10ms CPU limit, no free Durable Objects for WebSocket state |
| **Verdict** | DISQUALIFIED for trading backend |

## 10. Hugging Face Spaces

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent (CPU Basic) |
| **Compute** | 2 vCPU, 16GB RAM (generous!) |
| **Sleep/Spin-down** | YES - sleeps after 48 hours idle (better than most). Can be kept alive with pings. |
| **WebSocket** | Limited (designed for Gradio/Streamlit, not raw WebSocket) |
| **Docker** | Yes (Docker SDK supported) |
| **Storage** | Ephemeral only (/tmp). No persistent disk. |
| **Port** | Must use port 7860 |
| **Can run trading bot 24/5?** | MARGINAL - 48hr sleep is manageable with pings. But ephemeral storage means no persistent data. No native WebSocket for trading. |
| **Verdict** | Creative option but not ideal for production trading |

## 11. GitHub Codespaces

| Item | Detail |
|------|--------|
| **Free Tier** | 120 core-hours/month (= 60 hours on 2-core machine), 15GB storage |
| **Can run trading bot 24/5?** | NO - only 60 hours/month vs ~130 hours needed for 24/5 KST market hours |
| **Verdict** | DISQUALIFIED - insufficient hours for continuous operation |

## 12. Supabase (Database)

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent |
| **Database** | 500MB PostgreSQL storage, 2 projects |
| **Auth** | 50,000 MAU |
| **Storage** | 1GB file storage |
| **Edge Functions** | 500,000 invocations/month |
| **Egress** | 2GB database, 2GB storage |
| **Sleep/Pause** | YES - pauses after 7 days of inactivity. Can prevent with scheduled pings. |
| **Verdict** | GOOD for database if kept alive. 500MB sufficient for trading data initially. |

## 13. Neon.tech (Database)

| Item | Detail |
|------|--------|
| **Free Tier** | Yes, permanent |
| **Storage** | 0.5GB per project (up to 10 projects = 5GB total) |
| **Compute** | 100 CU-hours/month (~400 hours at 0.25 CU) |
| **Features** | Auto-scaling, scale-to-zero (5 min idle timeout), point-in-time recovery (6 hrs) |
| **Sleep/Spin-down** | YES - scales to zero after 5 min idle, but auto-wakes on connection |
| **Verdict** | GOOD alternative to Supabase. Auto-wake on connection is better for trading. |

## 14. PlanetScale (Database)

| Item | Detail |
|------|--------|
| **Free Tier** | REMOVED in March 2024 |
| **Minimum Plan** | $39/month |
| **Verdict** | DISQUALIFIED - no free tier |

---

## RECOMMENDED FREE STACK

### Backend: Oracle Cloud Always Free (ARM)

**Configuration:**
- 1x VM.Standard.A1.Flex: 4 OCPU, 24GB RAM (or split as needed)
- Ubuntu 22.04 ARM
- Docker installed
- Run FastAPI + trading bot in Docker containers
- 200GB storage for logs, data, etc.
- 10TB/month bandwidth

**Why Oracle:**
- Most powerful free compute by far (4 cores, 24GB RAM)
- Always-on (no sleep/spin-down)
- Full Docker support
- Full WebSocket support
- Enough power to run FastAPI + Redis + PostgreSQL all on one VM
- Convert to PAYG to avoid idle reclamation (still free within limits)
- Trading activity ensures CPU stays above 20% threshold

### Frontend: Vercel (Free Hobby Plan)

**Configuration:**
- Deploy Next.js app
- 100GB bandwidth, 150K function invocations
- Connect to Oracle backend via API/WebSocket

**Why Vercel:**
- Best Next.js hosting (built by Next.js creators)
- Excellent free tier for frontend
- Global CDN
- Automatic deployments from Git

### Database: Option A or B

**Option A: Self-hosted PostgreSQL on Oracle VM**
- Run PostgreSQL in Docker on the same Oracle ARM VM
- 24GB RAM is plenty for app + DB together
- Zero additional cost, no sleep issues
- Full control

**Option B: Neon.tech Free Tier (if you want managed)**
- 0.5GB free storage
- Auto-wakes on connection (better than Supabase for trading)
- Good for starting small

**Option C: Oracle Autonomous Database (Always Free)**
- 2 free databases, 20GB each
- Managed, no maintenance
- But Oracle-specific, not standard PostgreSQL

### Architecture Summary

```
[Vercel - Next.js Frontend]
        |
        | HTTPS / WSS
        v
[Oracle Cloud ARM VM - Always Free]
  |- FastAPI (uvicorn)
  |- WebSocket server
  |- Trading bot engine
  |- PostgreSQL (Docker)
  |- Redis (Docker, optional)
  |- Nginx reverse proxy
```

### Cost: $0/month

| Component | Service | Cost |
|-----------|---------|------|
| Frontend | Vercel Hobby | $0 |
| Backend + Bot | Oracle Cloud ARM (4 OCPU, 24GB) | $0 |
| Database | PostgreSQL on Oracle VM | $0 |
| Domain | Use free subdomains or bring your own | $0 (or ~$10/year for domain) |
| SSL | Let's Encrypt via Certbot | $0 |
| **Total** | | **$0/month** |

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Oracle reclaims idle VM | Convert to PAYG (free within limits); trading bot keeps CPU active |
| Oracle ARM availability | ARM instances can be hard to provision initially; use launch script to retry |
| Vercel function limits | Frontend is mostly static; 150K invocations is plenty |
| Single point of failure | Set up monitoring (UptimeRobot free tier: 50 monitors) |
| Oracle account closure | Keep account active, log in regularly, consider backup on GCP e2-micro |

### Backup/Fallback Plan

If Oracle Cloud becomes unavailable:
1. **GCP e2-micro** (1GB RAM) - can run a minimal FastAPI trading bot
2. **Koyeb** (512MB) - with keep-alive pings to prevent sleep
3. **Render** (512MB) - with external ping service (unreliable for trading)

---

## QUICK COMPARISON TABLE

| Platform | Truly Free? | Always On? | WebSocket? | Docker? | RAM | Trading Bot Viable? |
|----------|------------|------------|------------|---------|-----|-------------------|
| Oracle Cloud ARM | Yes (forever) | Yes* | Yes | Yes | 24GB | YES (best) |
| GCP e2-micro | Yes (forever) | Yes | Yes | Yes | 1GB | Barely |
| Koyeb | Yes (forever) | No (5min sleep) | Yes | Yes | 512MB | Marginal |
| Render | Yes (forever) | No (15min sleep) | Yes | Yes | 512MB | No |
| Fly.io | No (new users) | - | Yes | Yes | - | N/A |
| Railway | No ($5/mo) | Yes | Yes | Yes | - | N/A |
| Vercel | Yes (forever) | Serverless | No | No | - | No (frontend only) |
| Cloudflare Workers | Yes (forever) | Serverless | Paid only | No | - | No |
| HF Spaces | Yes (forever) | No (48hr sleep) | Limited | Yes | 16GB | Marginal |
| AWS EC2 | 12 months only | Yes | Yes | Yes | 1GB | Temporary |
| Supabase DB | Yes (forever) | No (7-day pause) | N/A | N/A | - | DB only |
| Neon DB | Yes (forever) | No (5min idle) | N/A | N/A | - | DB only |
| PlanetScale | No (removed) | - | - | - | - | N/A |
| GitHub Codespaces | 60 hrs/mo | No | - | Yes | - | No |

**Winner: Oracle Cloud Always Free + Vercel + self-hosted PostgreSQL = $0/month production trading stack**
