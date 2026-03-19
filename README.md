##  Important Notice
This system runs locally via ngrok. The ngrok URL may change 
if the tunnel restarts. Current URL:
https://nongravitational-norene-jestful.ngrok-free.dev

If the URL is unreachable, contact me and I will restart 
the tunnel and provide the new URL within 5 minutes.

To test locally:
1. Clone the repo
2. pip install -r requirements.txt
3. python run.py
4. ngrok http 5000

# CareCloud Voice Agent — Patient Registration System

> Voice AI agent that registers patients over the phone, powered by Vapi + Claude + Flask + SQLite.

---

## Live Demo

| Resource | URL |
|---|---|
| **Phone Number** | +1 (914) 372-0256|
| **API Base URL** | `https://nongravitational-norene-jestful.ngrok-free.dev`
| **Ngrok (local)** | `https://nongravitational-norene-jestful.ngrok-free.dev` |
| **Health Check** | `GET /` → `{"message":"CareCloud Voice Agent is Online"}` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CALLER (Phone)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PSTN / SIP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VAPI (Telephony + STT/TTS)                   │
│  - Provisions real U.S. phone number                            │
│  - Converts speech ↔ text                                       │
│  - Routes events to our webhook                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS POST /webhook
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              FLASK SERVER (Python / Uvicorn)                    │
│                                                                 │
│  /webhook  ── Vapi event handler                                │
│    ├── assistant-request  → returns Claude config + tools       │
│    ├── function-call      → tool dispatch                       │
│    │     ├── lookup_patient_by_phone  (duplicate detection)     │
│    │     ├── save_patient             (POST /patients)          │
│    │     └── update_patient           (PUT /patients/:id)       │
│    ├── end-of-call-report → logs transcript                     │
│    └── status-update      → call lifecycle logging              │
│                                                                 │
│  /patients ── REST API (CRUD + soft delete + search)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ SQLAlchemy ORM
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              SQLite (dev) / PostgreSQL (prod)                   │
│  patients table — UUID PK, full demographic schema,             │
│  soft-delete via deleted_at, UTC timestamps                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack & Justification

| Layer | Choice | Why |
|---|---|---|
| **Telephony + Voice** | Vapi | Abstracts STT/TTS/telephony; fastest path to working voice agent |
| **LLM** | Claude Sonnet (Anthropic) | Superior instruction following, natural conversation, less hallucination |
| **Backend** | Python + Flask | Fast to build, easy to read, aligns with uvicorn server already running |
| **ORM** | SQLAlchemy | Clean models, easy migration to PostgreSQL for production |
| **Database** | SQLite (dev) / PostgreSQL (prod) | SQLite = zero setup locally; PostgreSQL = production-grade persistence |
| **Tunnel** | ngrok | Instant HTTPS for local dev; free tier works fine for review |
| **Hosting** | Render / Railway | One-click deploys from GitHub, free tier available |

---

## Project Structure

```
carecloud/
├── app/
│   ├── __init__.py
│   ├── main.py           # Flask app factory, error handlers
│   ├── models.py         # SQLAlchemy Patient model, DB init, seeding
│   ├── routes.py         # REST API blueprints (CRUD)
│   ├── validators.py     # All input validation (phone, DOB, state, ZIP, etc.)
│   └── vapi_handler.py   # Vapi webhook handler, system prompt, tool definitions
├── tests/
│   └── test_api.py       # 17 unit + integration tests
├── scripts/
│   └── update_vapi_url.py  # Update Vapi serverUrl when ngrok restarts
├── .env.example
├── .gitignore
├── Procfile              # Railway / Heroku
├── render.yaml           # Render deployment config
├── requirements.txt
└── run.py                # Entry point
```

---

## Quick Start (Local)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/carecloud-voice-agent.git
cd carecloud-voice-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
PORT=5000
DATABASE_URL=sqlite:///./carecloud.db
BASE_URL=https://YOUR-NGROK-URL.ngrok-free.dev
VAPI_API_KEY=your_vapi_api_key_here
VAPI_ASSISTANT_ID=4eea5695-5661-4b0d-82ce-a9ff04793706
```

### 3. Start Ngrok

```bash
ngrok http 5000
# Copy the https URL → paste into BASE_URL in .env
```

### 4. Start the Server

```bash
python run.py
```

### 5. Update Vapi with Your Ngrok URL

```bash
python scripts/update_vapi_url.py
```

### 6. Run Tests

```bash
python -m pytest tests/ -v
```

---

## REST API Reference

All responses follow: `{ "data": {...}, "error": null }`

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/patients` | List all patients (supports `?last_name=`, `?date_of_birth=`, `?phone_number=`) |
| `GET` | `/patients/:id` | Get patient by UUID |
| `POST` | `/patients` | Create new patient |
| `PUT` | `/patients/:id` | Partial update |
| `DELETE` | `/patients/:id` | Soft delete (sets `deleted_at`) |

### Example: Create Patient

```bash
curl -X POST http://localhost:5000/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "05/15/1990",
    "sex": "Female",
    "phone_number": "5550001234",
    "address_line_1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001"
  }'
```

### Example: Search by Phone

```bash
curl "http://localhost:5000/patients?phone_number=5550001234"
```

---

## Vapi Webhook Events Handled

| Event | Handler |
|---|---|
| `assistant-request` | Returns dynamic Claude config + tool definitions |
| `function-call` | Dispatches to `lookup_patient_by_phone`, `save_patient`, `update_patient` |
| `end-of-call-report` | Logs full transcript + summary to stdout and `carecloud.log` |
| `status-update` | Logs call lifecycle (ringing, in-progress, ended) |
| `hang` | Logs silence/hang detection warning |

---

## Voice Agent System Prompt Design

The system prompt (`app/vapi_handler.py → SYSTEM_PROMPT`) is structured into:

1. **Persona** — "Alex", warm intake coordinator, natural speech
2. **Conversational Flow** — 8-step registration flow with explicit branching
3. **Error Handling Rules** — per-field re-prompting for invalid data
4. **Confirmation Gate** — hard rule: never save without explicit confirmation
5. **Language Support** — auto-switch to Spanish on detection
6. **Tool Usage Rules** — when to call each tool, what to say after

**Design decisions:**
- `temperature: 0.3` — low randomness for consistent data collection
- Short sentences — optimized for audio output, not text
- Fields collected in conversational pairs, not one-by-one
- Optional fields offered as a group opt-in, not individually prompted

---

## Production Deployment (Render)

1. Push to GitHub
2. Connect repo to [Render](https://render.com)
3. Set environment variables in Render dashboard:
   - `DATABASE_URL` → PostgreSQL connection string (Render provides free PostgreSQL)
   - `BASE_URL` → your Render app URL (e.g., `https://carecloud.onrender.com`)
   - `VAPI_API_KEY` → your Vapi key
4. Deploy — the `render.yaml` handles the rest
5. Update Vapi assistant serverUrl: `python scripts/update_vapi_url.py`

---

## Data Model

| Field | Type | Required | Validation |
|---|---|---|---|
| `patient_id` | UUID | Auto | Auto-generated |
| `first_name` | String | ✅ | 1–50 chars, alpha + hyphens/apostrophes |
| `last_name` | String | ✅ | Same as above |
| `date_of_birth` | Date | ✅ | Valid date, not in future, MM/DD/YYYY |
| `sex` | Enum | ✅ | Male / Female / Other / Decline to Answer |
| `phone_number` | String | ✅ | 10-digit U.S. number |
| `address_line_1` | String | ✅ | Street address |
| `city` | String | ✅ | 1–100 chars |
| `state` | String | ✅ | Valid 2-letter U.S. state code |
| `zip_code` | String | ✅ | 5-digit or ZIP+4 |
| `email` | String | ❌ | Valid email format |
| `address_line_2` | String | ❌ | Apt/suite |
| `insurance_provider` | String | ❌ | Free text |
| `insurance_member_id` | String | ❌ | Alphanumeric |
| `preferred_language` | String | ❌ | Default: English |
| `emergency_contact_name` | String | ❌ | Full name |
| `emergency_contact_phone` | String | ❌ | 10-digit U.S. |
| `created_at` | Timestamp | Auto | UTC |
| `updated_at` | Timestamp | Auto | UTC, updates on every PUT |
| `deleted_at` | Timestamp | Auto | Null unless soft-deleted |

---

## Edge Cases Handled

| Scenario | Behavior |
|---|---|
| Invalid phone number (< 10 digits) | Agent re-prompts specifically for phone |
| Future date of birth | Agent asks caller to double-check |
| Invalid U.S. state | Agent asks for 2-letter abbreviation |
| Invalid ZIP code | Agent asks for 5-digit ZIP |
| Duplicate phone number | Agent offers to update existing record |
| Caller wants to start over | Agent resets all collected data |
| DB write fails | Caller hears a graceful error, not silence |
| Call drops mid-registration | All collected data logged to stdout + file |
| Spanish speaker | Agent switches entirely to Spanish |

---

## Known Limitations & Trade-offs

1. **SQLite in production** — fine for demo/review, not for concurrent writes; swap `DATABASE_URL` to PostgreSQL for real production.
2. **Ngrok free tier** — URL changes on every restart; run `scripts/update_vapi_url.py` after each restart. Paid ngrok plan solves this.
3. **No authentication on API** — REST API is open. For production, add API key middleware or OAuth.
4. **No HIPAA compliance** — this is a technical assessment; do not use with real patient data.
5. **In-process tool calls** — `save_patient` calls `POST /patients` via HTTP loopback; for production, call the service layer directly to avoid the round-trip.

---

## Next Steps (if more time)

- [ ] PostgreSQL + Alembic migrations
- [ ] API authentication (Bearer token)
- [ ] Call transcript storage linked to patient record
- [ ] Simple web dashboard (React or plain HTML) to view registered patients
- [ ] Appointment scheduling offer after registration
- [ ] Retry logic for failed DB writes during calls
- [ ] Webhook signature verification (Vapi HMAC)
- [ ] Docker + docker-compose for one-command local setup

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `PORT` | No | Server port (default: 5000) |
| `DATABASE_URL` | No | SQLAlchemy DB URL (default: SQLite) |
| `BASE_URL` | ✅ | Public URL of this server (ngrok or Render URL) |
| `VAPI_API_KEY` | ✅ | Vapi private API key |
| `VAPI_ASSISTANT_ID` | No | Existing Vapi assistant UUID to update |
| `FLASK_DEBUG` | No | Set `true` for debug mode (never in production) |
