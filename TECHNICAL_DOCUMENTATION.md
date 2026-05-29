# Post-Discharge Care Agent — Technical Documentation

> **Agent:** Aasha — Voice-based post-discharge check-in assistant for knee replacement patients  
> **File:** `agent.py` (agent_mvp.py)  
> **Framework:** LiveKit Agents (Python)  
> **Last Updated:** May 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Models Used](#3-models-used)
4. [Token & Usage Analysis](#4-token--usage-analysis)
5. [Model Selection Rationale](#5-model-selection-rationale)
6. [Cost Analysis](#6-cost-analysis)
7. [API Endpoints & Integrations](#7-api-endpoints--integrations)
8. [Environment Configuration](#8-environment-configuration)
9. [Call Flow & Conversation Design](#9-call-flow--conversation-design)
10. [Deployment & Execution](#10-deployment--execution)
11. [Data Sheet References](#11-data-sheet-references)

---

## 1. Project Overview

This project implements an **AI-powered voice agent** for automated post-discharge follow-up calls to patients who have undergone **knee replacement surgery**. The agent, named **"Aasha"**, calls patients daily after discharge, checks their recovery status (pain level, wound condition, mobility, medication adherence, exercise compliance), and escalates clinical concerns to the care team via WhatsApp and Trello.

### Key Features
- **Voice-based conversational check-in** via LiveKit real-time audio
- **Clinical red-flag detection** (pain ≥ 8/10, wound infection, DVT/PE symptoms, missed blood thinners, falls, etc.)
- **WhatsApp notifications** to patients (normal summary, red alerts, missed-call follow-ups)
- **Trello card creation** for flagged cases (nurse action checklist)
- **Google Sheets logging** for all call outcomes and patient data
- **Multilingual support** (English, Hindi, Gujarati — the agent code-switches based on patient speech)
- **Safety-net logging** on disconnect, errors, or early termination

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LiveKit Cloud                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Agent Session                           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │   │
│  │  │  Silero  │→ │ Deepgram │→ │  Gemini  │→ │Cartesia│ │   │
│  │  │   VAD    │  │ STT Nova3│  │2.5 Flash │  │TTS Sonc│ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘ │   │
│  │                                                     │   │
│  │              Turn Handling (MultilingualModel)       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Google      │    │  Twilio      │    │  Trello API      │
│  Sheets API  │    │  WhatsApp    │    │  (red flags)     │
│  (call logs) │    │  (patient    │    │  → Nurse card    │
│  (patient DB)│    │   messages)  │    │  + checklist     │
└──────────────┘    └──────────────┘    └──────────────────┘
```

### Data Flow

1. **Patient scheduled** → Agent calls patient via LiveKit WebRTC
2. **Audio stream** → Silero VAD detects speech segments
3. **Speech** → Deepgram Nova-3 transcribes to text (STT)
4. **Text** → Google Gemini 2.5 Flash processes via prompt instructions
5. **LLM response** → Cartesia Sonic 2 TTS converts to speech
6. **Call complete** → Google Sheets updated, WhatsApp sent, Trello card if flagged
7. **Disconnect safety** → If call drops mid-way, auto-log and send WhatsApp

---

## 3. Models Used

| Component | Model | Provider | Version / ID |
|-----------|-------|----------|-------------|
| **LLM** | Gemini 2.5 Flash | Google (via LiveKit) | `gemini-2.5-flash` |
| **STT** | Nova-3 | Deepgram | `nova-3`, language: `en-US` |
| **TTS** | Sonic 2 | Cartesia | `sonic-2-2025-03-07`, voice ID: `248be419-c632-4f23-adf1-5324ed7dbf1d` |
| **VAD** | Silero VAD | Silero (open-source) | `silero.VAD.load(min_silence_duration=0.25)` |
| **Turn Detection** | MultilingualModel | LiveKit | `MultilingualModel()` — end-of-turn + interruption detection |
| **Patient DB** | Google Sheets | Google (gspread) | Spreadsheet: `Patient_data`, Sheet: `Sheet1` |
| **Call Logs** | Google Sheets | Google (gspread) | Spreadsheet: `call_logs`, Sheet: `Sheet1` |

### 3.1 Google Gemini 2.5 Flash (LLM)

- **Context window:** 1,000,000 tokens
- **Max output:** 66,000 tokens
- **Temperature:** 0.2 (low — deterministic clinical responses)
- **Capabilities used:** Text generation, function calling, structured output
- **Role:** Drives the entire conversation — understands patient speech, follows a rigid 9-step protocol, calls function tools for pain scoring, clinical lookups, flagging, logging, and ending calls.

### 3.2 Deepgram Nova-3 (STT)

- **Architecture:** Latent-space ASR model
- **WER:** 5.26% (internal), 12.8% (third-party benchmarks)
- **Latency:** < 300ms streaming
- **Languages:** 45+ languages (configured for en-US)
- **Role:** Real-time speech-to-text for patient responses during the call.

### 3.3 Cartesia Sonic 2 (TTS)

- **Model:** `sonic-2-2025-03-07`
- **Time-to-first-audio:** ~90ms
- **Voice:** Cartesia voice ID `248be419-c632-4f23-adf1-5324ed7dbf1d`
- **Speed:** `"slow"` (deliberate, warm pace suitable for elderly patients)
- **Emotion:** `["positivity:medium"]`
- **Role:** Converts LLM responses to natural speech; selected for low latency required in real-time conversation.

### 3.4 Silero VAD (Voice Activity Detection)

- **License:** MIT (free, open-source)
- **Runtime:** ONNX / PyTorch
- **Min silence duration:** 0.25 seconds
- **Role:** Detects when the patient is speaking vs. silent, enabling turn-taking.

### 3.5 MultilingualModel (Turn Detection)

- **Provider:** LiveKit plugins
- **Role:** Detects end-of-turn (patient finished speaking) and manages interruptions. Configured with:
  - **Endpointing:** dynamic mode, min_delay 0.6s, max_delay 2.5s
  - **Interruption:** VAD-based with false-interruption resume at 1.0s timeout

---

## 4. Token & Usage Analysis

### 4.1 Prompt Token Budget

The system prompt (`build_prompt()`) is designed to be **~250 tokens** (per code comment at line 199). Actual token count is approximately 350–400 tokens after variable substitution (patient name, meds, etc.).

### 4.2 Typical Per-Call Token Usage

| Turn | Direction | Content | Est. Input Tokens | Est. Output Tokens |
|------|-----------|---------|-------------------|-------------------|
| 0 | — | System prompt (setup) | 400 | — |
| 1 | Patient | "Hello?" | ~5 (audio STT) | — |
| 1 | Agent | "Am I speaking with Mr. X?" | — | ~50 |
| 2 | Patient | "Yes, speaking" | ~10 | — |
| 2 | Agent | Intro + "How is pain today?" | — | ~60 |
| 3 | Patient | "Pain is 6 out of 10" | ~15 | — |
| 3 | Agent | Pain update + "Wound ok?" | — | ~40 |
| 4-10 | — | Wound / Mobility / Exercise / Meds / Wellbeing | ~100 total | ~300 total |
| 11 | Agent | log_and_close() call | — | ~50 |
| 12 | Agent | Goodbye + end_call() | — | ~30 |
| | **Total** | | **~530** | **~530** |

**Notes:**
- Each function tool invocation (update_pain_score, lookup_clinical_info, flag_red_alert, log_and_close, end_call) adds ~100–200 tokens for the tool call + response.
- Total per-call LLM usage: **~1,000–2,000 tokens** (input + output combined)
- Audio input (STT) and output (TTS) are billed by duration, not tokens.

### 4.3 Audio Usage Per Call

| Metric | Estimate |
|--------|----------|
| Avg call duration | 3–5 minutes |
| Patient speaking time (STT) | ~1.5–2.5 minutes |
| Agent speaking time (TTS) | ~1.5–2.5 minutes |
| VAD processing | Continuous during call |

---

## 5. Model Selection Rationale

### Why Gemini 2.5 Flash?

| Factor | Rationale |
|--------|-----------|
| **Cost** | $0.30/1M input, $2.50/1M output — cheapest among capable LLMs for this use case |
| **Multilingual** | Strong support for Hindi and Gujarati code-switching (required for Indian patient demographic) |
| **Function calling** | Native tool-calling capability used for pain scoring, clinical lookup, flagging, logging |
| **Low temperature** | Clinical use case demands deterministic, reproducible responses (temp=0.2) |
| **Long context** | 1M context window accommodates multi-turn conversations without truncation |
| **Latency** | Flash-tier is optimized for real-time inference |
| **Comparison** | 76% cheaper than Gemini Pro 2.5 for equivalent token volumes |

### Why Deepgram Nova-3 (over alternatives)?

| Alternative | WER | Latency | Cost/min | Why Nova-3 Wins |
|-------------|-----|---------|----------|-----------------|
| **Nova-3** | 5.26% | <300ms | **$0.0077** | Best latency-to-accuracy ratio |
| OpenAI Whisper | ~8.9% | ~500ms | $0.0060 | Higher WER, higher latency |
| Google Chirp 2 | — | — | $0.0160 | 2× more expensive |
| Nova-2 | ~7% | ~350ms | $0.0058 | Older; Nova-3 has 53% lower WER |
| **Decision:** Nova-3 selected for streaming-optimized architecture, medical terminology support, and lowest streaming latency at competitive pricing. |

### Why Cartesia Sonic 2 (over alternatives)?

| Alternative | TTFA | Cost/min | Quality | Why Sonic 2 Wins |
|-------------|------|----------|---------|------------------|
| **Sonic 2** | **~90ms** | **~$0.03/min** | Arena #10 | Lowest latency for real-time voice |
| ElevenLabs | ~300ms | ~$0.18/min | Arena #1 | 3× latency, 6× cost |
| Gemini Flash TTS | ~250ms | ~$0.012/min | Arena #2 | Better quality but higher latency |
| Grok TTS | ~200ms | ~$0.0042/min | Lower quality | Budget option; inferior voice quality |
| **Decision:** Sonic 2 chosen for **sub-100ms latency** critical for natural conversational flow with elderly patients. Voice warmth with "positivity:medium" emotion setting suits the healthcare context. |

### Why Silero VAD (free, open-source)?

- **MIT licensed** — no vendor lock-in, no API costs
- **Enterprise-grade** — 9K+ GitHub stars, production proven
- **Lightweight** — ONNX runtime, runs locally on CPU
- **0.25s min silence** tuned for conversational turn-taking

---

## 6. Cost Analysis

### 6.1 Per-Minute Cost Breakdown (Call Duration Basis)

| Component | Provider | Model | Pricing Model | Cost per Call Minute |
|-----------|----------|-------|---------------|---------------------|
| **Agent Session** | LiveKit Cloud | — | $0.01/min (agent session) | **$0.01000** |
| **LLM** | Google | Gemini 2.5 Flash | $0.30/1M input, $2.50/1M output | **~$0.00130** |
| **STT** | Deepgram | Nova-3 | $0.0077/min (streaming) | **$0.00770** |
| **TTS** | Cartesia | Sonic 2 | ~$0.03/min (~15 credits/sec) | **~$0.03000** |
| **VAD** | Silero | — | Free (MIT, local) | **$0.00000** |
| **Turn Detection** | LiveKit | MultilingualModel | Included in agent session | **$0.00000** |
| **Total (estimated)** | | | | **~$0.049/min** |

> **Note:** LLM cost per minute is estimated based on ~500 tokens/min call throughput. Actual varies by conversation length and complexity.

### 6.2 Per-Call Cost Estimate (4-min average call)

| Component | Cost |
|-----------|------|
| LiveKit Agent Session (4 min × $0.01) | $0.0400 |
| LLM (~2,000 tokens total) | $0.0053 |
| STT (~2 min speech × $0.0077) | $0.0154 |
| TTS (~2 min speech × $0.03) | $0.0600 |
| WhatsApp (1 message × ~$0.0084) | $0.0084 |
| Google Sheets API | Free tier |
| Trello API | Free tier |
| **Total per call** | **~$0.13** |

### 6.3 Monthly Cost Projection

| Volume | Calls/month | Minutes | Monthly Cost |
|--------|------------|---------|-------------|
| Pilot (10 patients, daily) | ~300 | ~1,200 | **~$156** |
| Small clinic (50 patients, daily) | ~1,500 | ~6,000 | **~$780** |
| Medium hospital (200 patients, daily) | ~6,000 | ~24,000 | **~$3,120** |

### 6.4 Platform Subscription Costs

| Service | Plan | Cost |
|---------|------|------|
| **LiveKit Cloud** | Build (free) → Ship ($50/mo) | $0–$50/mo |
| **Deepgram** | Pay-as-you-go ($200 free credit) | Usage-based |
| **Cartesia** | Pro ($4/mo) for 100K credits | $4/mo |
| **Google AI (Gemini)** | Pay-as-you-go | Usage-based |
| **Twilio** | Pay-as-you-go | Usage-based |
| **Trello** | Free | $0 |
| **Google Workspace** | Free tier | $0 |

---

## 7. API Endpoints & Integrations

### 7.1 LiveKit Cloud
- **WebSocket URL:** `wss://ami-ai-95ltod5x.livekit.cloud`
- **Auth:** API Key + API Secret
- **Purpose:** Real-time audio transport, agent session management, turn detection

### 7.2 Google Gemini API (via LiveKit Inference)
- **Model:** `gemini-2.5-flash`
- **Provider:** LiveKit plugins → Google AI
- **Auth:** `GOOGLE_API_KEY` (configured via env)
- **Endpoint:** Internal routing through LiveKit Inference (not called directly)

### 7.3 Deepgram API (via LiveKit Inference)
- **Model:** `nova-3`
- **Auth:** `DEEPGRAM_API_KEY`
- **Pricing Endpoint:** `https://api.deepgram.com/v1/listen?model=nova-3`
- **Purpose:** Real-time speech-to-text streaming

### 7.4 Cartesia API (via LiveKit Inference)
- **Model:** `sonic-2-2025-03-07`
- **Voice ID:** `248be419-c632-4f23-adf1-5324ed7dbf1d`
- **Auth:** `CARTESIA_API_KEY`
- **Purpose:** Text-to-speech with emotion control

### 7.5 Google Sheets API (via gspread)
- **Auth:** Service account (`pp.json`)
- **Spreadsheet 1:** `Patient_data` → Patient records (read/write)
  - Columns: patient_id, name, surgery_type, age, risk_factors, prescribed_medications, medication_schedule, prescribed_exercises, mobility_support, next_followup_date, discharge_date, phone_number, emergency_notes, last_pain_score, current_status
- **Spreadsheet 2:** `call_logs` → Call history (append-only)
  - Columns: patient_id, name, date, time, pain, symptoms, meds, mobility, exercises, red_flag, reason, summary

### 7.6 Twilio WhatsApp API
- **Base URL:** `https://api.twilio.com` (via Twilio Python SDK)
- **Auth:** `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`
- **From:** `TWILIO_WHATSAPP_FROM` (default: `whatsapp:+14155238886`)
- **To:** Patient phone number prefixed with `whatsapp:`
- **Endpoints used:** `messages.create()`
- **Cost:** $0.005/message (Twilio) + Meta fees (~$0.0034/msg) = ~$0.0084/msg

### 7.7 Trello API
- **Base URL:** `https://api.trello.com/1/`
- **Auth:** API Key (`TRELLO_API_KEY`) + Token (`TRELLO_TOKEN`)
- **Endpoints used:**
  - `POST /cards` — Create red-flag card with patient details
  - `POST /checklists` — Add nurse action checklist
  - `POST /checklists/{id}/checkItems` — Add checklist items
- **List ID:** `TRELLO_LIST_ID`
- **Cost:** Free tier (unlimited cards, 10 boards)

---

## 8. Environment Configuration

Required environment variables (`.env` file):

| Variable | Description | Source |
|----------|-------------|--------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL | LiveKit Console |
| `LIVEKIT_API_KEY` | LiveKit API key | LiveKit Console |
| `LIVEKIT_API_SECRET` | LiveKit API secret | LiveKit Console |
| `GOOGLE_API_KEY` | Google AI API key | Google AI Studio |
| `DEEPGRAM_API_KEY` | Deepgram API key | Deepgram Console |
| `CARTESIA_API_KEY` | Cartesia API key | Cartesia Dashboard |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | Twilio Console |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Twilio Console |
| `TWILIO_WHATSAPP_FROM` | WhatsApp sender number | Twilio Console |
| `TRELLO_API_KEY` | Trello API key | Trello Power-Ups |
| `TRELLO_TOKEN` | Trello API token | Trello Developer API |
| `TRELLO_LIST_ID` | Target Trello list ID | Trello Board URL |
| `HOSPITAL_NAME` | Display name (optional) | Configurable |
| `HOSPITAL_PHONE` | Helpline number (optional) | Configurable |

**Google Sheets:** Requires `pp.json` service account key file in the project root.

---

## 9. Call Flow & Conversation Design

### 9.1 Step-by-step Protocol (enforced by prompt)

```
Step 1  ── CONFIRM: "Am I speaking with [patient name]?"
            No answer in 20s → end_call()
            Patient unavailable → flag + log_and_close + end_call()

Step 2  ── INTRO: Warm Day N knee check-in introduction

Step 3  ── PAIN: Ask 1-10 → update_pain_score() immediately
            Auto-flag if: score ≥ 8, or ≥ 2 above last_pain

Step 4  ── WOUND: Swelling improving? Clean/dry? Redness/discharge/smell/fever?
            lookup_clinical_info() before flagging if unsure

Step 5  ── MOBILITY: Walking with support? Falls? Knee locking?

Step 6  ── EXERCISES: Done today? Skipped any?

Step 7  ── MEDS: All taken on schedule? Missed blood thinner?

Step 8  ── WELLBEING: Sleep, eating/drinking, anything else?

Step 9  ── CLOSE: log_and_close() → "Update shared" → goodbye → end_call()
```

### 9.2 Red Flag Conditions (automatic escalation)

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Pain score | ≥ 8/10 | Flag + Trello card |
| Pain worsening | ≥ 2 above last pain score | Flag + Trello card |
| Fever | > 101°F (patient-reported) | Flag + Trello card |
| Wound | Redness, discharge, smell, pus | Flag + Trello card |
| Calf pain | Possible DVT | Flag + ambulance guidance |
| Chest pain / breathlessness | Possible PE | Flag + ambulance guidance |
| Fainting | Any occurrence | Flag + Trello card |
| Missed blood thinner | Patient confirmed | Flag + Trello card |
| Cannot access meds | Patient confirmed | Flag + Trello card |
| Fall | Any occurrence | Flag + Trello card |
| Knee locking | Patient reported | Flag + Trello card |
| Patient distressed | Agent assessment | Flag + Trello card |
| Medical question asked | Any | Flag + Trello card |

### 9.3 WhatsApp Message Templates

| Scenario | Template |
|----------|----------|
| Normal check-in | Pain summary, symptoms, mobility, meds, exercises, helpline |
| Red flag | URGENT alert + reason, nurse will call 2-4 hrs, emergency number |
| Missed call | "We missed you, will try again at [time]", meds reminder |

### 9.4 Trello Card Structure (Red Flags)

```
Title:  URGENT [Patient Name] Day [N] - [Reason]
Desc:   Patient: [ID] | [Surgery Type] | Risk: [factors]
        Flag: [reason]
        Pain: [score]/10 | [emergency notes]
        [summary]
        WA: Sent/FAILED

Checklist: "Nurse Actions"
  ☐ Review summary
  ☐ Contact patient
  ☐ Inform doctor
  ☐ Resolve or escalate
```

---

## 10. Deployment & Execution

### 10.1 Requirements

File: `requirements-gemini.txt`

```
livekit-agents
livekit-plugins-gemini
livekit-plugins-cartesia
livekit-plugins-deepgram
livekit-plugins-silero
gspread
python-dotenv
twilio
requests
```

### 10.2 Running

| Mode | Command | Description |
|------|---------|-------------|
| Console (local mic/speaker) | `python agent.py console` | Test with local audio I/O |
| Dev (LiveKit playground) | `python agent.py dev` | Test via LiveKit web playground |

### 10.3 Production Deployment

Agent is deployed to **LiveKit Cloud** as a worker. The `entrypoint()` function is registered with:

```python
agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
```

LiveKit Cloud handles:
- Agent hosting and scaling (global data centers)
- WebRTC signaling and media routing
- Observability and analytics

---

## 11. Data Sheet References

### LLM: Gemini 2.5 Flash
- **Provider:** Google DeepMind
- **Release date:** May 2025
- **Pricing page:** https://ai.google.dev/gemini-api/docs/pricing
- **Input price:** $0.30 / 1M tokens (text/image/video), $1.00 / 1M tokens (audio)
- **Output price:** $2.50 / 1M tokens
- **Context window:** 1,000,000 tokens
- **Max output:** 66,000 tokens

### STT: Deepgram Nova-3
- **Provider:** Deepgram
- **Release date:** Early 2025
- **Pricing page:** https://deepgram.com/pricing
- **Streaming price:** $0.0077/min (PAYG), $0.0065/min (Growth/annual)
- **Batch price:** $0.0043/min (PAYG)
- **WER:** 5.26% internal, 12.8% third-party
- **Streaming latency:** < 300ms

### TTS: Cartesia Sonic 2
- **Provider:** Cartesia AI
- **Pricing page:** https://cartesia.ai/pricing
- **Model ID:** `sonic-2-2025-03-07`
- **TTFA:** ~90ms
- **Credit rate:** 15 credits/sec of audio
- **Voice ID:** `248be419-c632-4f23-adf1-5324ed7dbf1d`
- **Status:** EOL June 1, 2026 (should plan migration to Sonic 3)

### VAD: Silero VAD
- **Provider:** Silero Team
- **License:** MIT (free)
- **Repository:** https://github.com/snakers4/silero-vad
- **Latest version:** v6.2.1 (Feb 2026)

### LiveKit Cloud
- **Pricing page:** https://livekit.com/pricing
- **Agent session minutes:** $0.01/min (overage)
- **Build plan:** 1,000 free agent minutes/mo
- **Ship plan:** $50/mo (5,000 agent minutes included)

### Twilio WhatsApp
- **Pricing page:** https://twilio.com/whatsapp/pricing
- **Twilio fee:** $0.005/message
- **Meta fee:** ~$0.0034/message (utility/authentication templates)
- **Total:** ~$0.0084/message

### Trello API
- **Pricing page:** https://trello.com/pricing
- **Free tier:** 10 boards, unlimited cards, unlimited checklists
- **Rate limit:** 10 requests per second (API token-based)

---

*End of Technical Documentation*
