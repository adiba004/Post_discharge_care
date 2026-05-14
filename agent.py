"""
agent_mvp.py — Post-Discharge Care MVP (Final)
================================================
INSTALL BEFORE RUNNING:
  pip install livekit-agents livekit-plugins-groq livekit-plugins-cartesia
  pip install livekit-plugins-deepgram livekit-plugins-silero
  pip install gspread python-dotenv twilio requests

ADD TO .env:
  LIVEKIT_URL=wss://your-project.livekit.cloud
  LIVEKIT_API_KEY=your_livekit_api_key
  LIVEKIT_API_SECRET=your_livekit_api_secret
  DEEPGRAM_API_KEY=your_deepgram_api_key
  GROQ_API_KEY=your_groq_api_key
  CARTESIA_API_KEY=your_cartesia_api_key
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN=your_twilio_auth_token
  TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
  TRELLO_API_KEY=your_trello_api_key
  TRELLO_TOKEN=your_trello_token
  TRELLO_LIST_ID=your_red_flag_list_id
  HOSPITAL_NAME=City Care Hospital
  HOSPITAL_PHONE=1800-XXX-XXXX

HOW TO TEST:
  Change ACTIVE_PATIENT_ID to "P-101", "P-102", or "P-103" and run.
  python agent_mvp.py dev

VERIFY AFTER EACH CALL:
  ✓ call_logs — new row with all 10 columns filled correctly
  ✓ Patient_data — col 9 (Last_Pain_Score) and col 10 (Current_Status) updated
  ✓ WhatsApp received on patient phone (correct template: normal / red-flag / missed)
  ✓ Trello card created ONLY if red flag was raised
"""

import asyncio
import os
import time
import gspread
import requests
from datetime import datetime
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient

from livekit import agents
from livekit.agents import Agent, AgentSession, TurnHandlingOptions
from livekit.agents.llm import function_tool
from livekit.plugins import silero, cartesia, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env")

# ── CHANGE THIS TO SWITCH PATIENT ───────────────────────────────────────────
ACTIVE_PATIENT_ID = "P-101"

# ── CONFIG ───────────────────────────────────────────────────────────────────
HOSPITAL_NAME  = os.getenv("HOSPITAL_NAME", "City Care Hospital")
HOSPITAL_PHONE = os.getenv("HOSPITAL_PHONE", "1800-XXX-XXXX")
TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TRELLO_KEY     = os.getenv("TRELLO_API_KEY")
TRELLO_TOK     = os.getenv("TRELLO_TOKEN")
TRELLO_LIST    = os.getenv("TRELLO_LIST_ID")

# ── SHEETS ───────────────────────────────────────────────────────────────────
gc             = gspread.service_account(filename="pp.json")
patients_sheet = gc.open("Patient_data").get_worksheet(0)
logs_sheet     = gc.open("call_logs").get_worksheet(0)


# ═══════════════════════════════════════════════
#  SHEET HELPERS
# ═══════════════════════════════════════════════

def get_patient(pid: str) -> dict | None:
    for r in patients_sheet.get_all_records():
        if str(r.get("patient_id", "")).strip() == pid.strip():
            return r
    return None


def get_last_pain(pid: str) -> str:
    """
    Returns last pain score as string.
    FIX: treats empty string AND "0" as no previous record —
    empty cells in gspread default to 0 which caused false worsening flags.
    """
    for r in patients_sheet.get_all_records():
        if str(r.get("patient_id", "")).strip() == pid.strip():
            s = str(r.get("Last_Pain_Score", "")).strip()
            return s if (s and s != "0") else "no previous record"
    return "no previous record"


def pain_worsening(last: str, current: int) -> bool:
    """
    FIX: explicitly guard against last == 0 (blank cell default).
    Returns True only if pain has genuinely increased by 2+ points.
    """
    try:
        last_int = int(last)
        if last_int == 0:
            return False  # 0 means no real previous record
        return (current - last_int) >= 2
    except (ValueError, TypeError):
        return False


def compute_day(discharge_str: str) -> int:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return max(
                (datetime.now() - datetime.strptime(discharge_str.strip(), fmt)).days + 1,
                1
            )
        except ValueError:
            continue
    return 1


def update_patient_status(pid: str, pain: str, red_flag: bool):
    """Update Last_Pain_Score (col 9) and Current_Status (col 10) in Patient_data."""
    rows = patients_sheet.get_all_records()
    for i, r in enumerate(rows):
        if str(r.get("patient_id", "")).strip() == pid.strip():
            n = i + 2  # row 1 = header, gspread is 1-indexed
            patients_sheet.update_cell(n, 9, pain)
            patients_sheet.update_cell(
                n, 10,
                "🚨 RED FLAG — Nurse Review Needed" if red_flag else "✓ Checked In"
            )
            print(f"[SHEET] Patient_data updated → {'RED FLAG' if red_flag else 'OK'}")
            return


def log_call(
    pid: str, name: str, pain: str,
    symptoms: str, meds: str,
    red_flag: bool, reason: str, summary: str,
):
    """
    Append one row to call_logs sheet, then update Patient_data.
    Column order: patient_id | name | call_date | call_time | pain_score |
                  symptoms_reported | medications_taken | red_flag |
                  red_flag_reason | transcript_summary
    Retries 3x with 2s backoff. Writes local backup if all fail.
    """
    row = [
        pid, name,
        datetime.now().strftime("%Y-%m-%d"),
        datetime.now().strftime("%H:%M:%S"),
        pain, symptoms, meds,
        "YES" if red_flag else "NO",
        reason, summary,
    ]
    for attempt in range(1, 4):
        try:
            logs_sheet.append_row(row)
            update_patient_status(pid, pain, red_flag)
            print(f"[LOG ✓] {name} | Pain:{pain}/10 | Flag:{'YES 🚨' if red_flag else 'NO ✓'}")
            return
        except Exception as e:
            print(f"[WARN] Sheet write {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(2)
    backup = f"backup_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(backup, "w") as f:
        f.write(str(row))
    print(f"[CRITICAL] All sheet writes failed — backed up to {backup}")


# ═══════════════════════════════════════════════
#  WHATSAPP — 3 templates
# ═══════════════════════════════════════════════

def _wa_normal(p: dict, day: int, pain: str, symptoms: str, meds: str) -> str:
    return (
        f"🏥 *{HOSPITAL_NAME} — Day {day} Check-In Summary*\n\n"
        f"Hi {p['name']} 👋 Thank you for speaking with us today.\n\n"
        f"📊 *Today's Update*\n"
        f"🔴 Pain Score  : {pain}/10\n"
        f"🩹 Symptoms   : {symptoms if symptoms.strip() else 'None reported'}\n"
        f"💊 Medications: {meds}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💊 *Your Medications (as prescribed)*\n"
        f"{p['medications']}\n\n"
        f"⚠️ Do not stop or change any medication without consulting Dr. {p['doctor_name']}.\n\n"
        f"📞 Questions? {HOSPITAL_PHONE}\n"
        f"_Automated summary. Not a substitute for medical advice._"
    )


def _wa_red_flag(p: dict, day: int, pain: str, reason: str, symptoms: str, meds: str) -> str:
    return (
        f"🚨 *URGENT — {HOSPITAL_NAME} Recovery Alert*\n\n"
        f"Hi {p['name']}, a concern was flagged during your Day {day} check-in.\n\n"
        f"⚠️ *What was flagged:* {reason}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ A nurse from Dr. {p['doctor_name']}'s team will call you within *2–4 hours.*\n\n"
        f"If this feels like an emergency:\n"
        f"🏥 Go to the nearest ER  or  📞 Call {HOSPITAL_PHONE}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💊 *Keep taking your medications — do not stop:*\n"
        f"{p['medications']}\n\n"
        f"📋 Pain: {pain}/10 | Symptoms: {symptoms or 'None'} | Meds: {meds}\n"
        f"_Shared with Dr. {p['doctor_name']}'s care team._"
    )


def _wa_missed(p: dict, day: int, retry_time: str) -> str:
    return (
        f"📞 *{HOSPITAL_NAME} — Missed Check-In*\n\n"
        f"Hi {p['name']} 👋 We tried calling for your Day {day} check-in "
        f"but couldn't reach you. No worries!\n\n"
        f"We'll try again at *{retry_time}*.\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💊 *Please take your medications:*\n"
        f"{p['medications']}\n\n"
        f"📞 {HOSPITAL_PHONE} | _— {HOSPITAL_NAME} Care Team_"
    )


def send_whatsapp(to: str, body: str) -> bool:
    if not all([TWILIO_SID, TWILIO_AUTH, to]):
        print("[WA] Missing credentials or number — skipping")
        return False
    for attempt in range(1, 3):
        try:
            m = TwilioClient(TWILIO_SID, TWILIO_AUTH).messages.create(
                from_=TWILIO_WA_FROM, to=f"whatsapp:{to}", body=body
            )
            print(f"[WA ✓] Sent | SID: {m.sid}")
            return True
        except Exception as e:
            print(f"[WA ✗] Attempt {attempt}/2: {e}")
            if attempt < 2:
                time.sleep(3)
    return False


def dispatch_whatsapp(
    p: dict, day: int, pain: str, symptoms: str, meds: str,
    red_flag: bool, reason: str,
    missed: bool = False, retry_time: str = "2 hours from now",
) -> bool:
    phone = "+919662389846"  # test number — all summaries go here
    if missed:
        msg = _wa_missed(p, day, retry_time)
    elif red_flag:
        msg = _wa_red_flag(p, day, pain, reason, symptoms, meds)
    else:
        msg = _wa_normal(p, day, pain, symptoms, meds)
    return send_whatsapp(phone, msg)


# ═══════════════════════════════════════════════
#  TRELLO — red flag cards only
# ═══════════════════════════════════════════════

def create_trello_card(
    p: dict, day: int, pain: str, symptoms: str, meds: str,
    reason: str, summary: str, wa_sent: bool,
):
    if not all([TRELLO_KEY, TRELLO_TOK, TRELLO_LIST]):
        print("[TRELLO] Missing credentials — skipping")
        return
    short = reason[:55] + "..." if len(reason) > 55 else reason
    title = f"🚨 {p['name']} — Day {day} — {short}"
    desc  = (
        f"**Patient:** {p['patient_id']} | **Surgery:** {p['surgery_type']}\n"
        f"**Doctor:** Dr. {p['doctor_name']} | **Time:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"**Flag Reason:** {reason}\n\n"
        f"Pain: {pain}/10 | Symptoms: {symptoms or 'None'} | Meds: {meds}\n\n"
        f"**Summary:**\n{summary}\n\n"
        f"WhatsApp: {'✅ Sent' if wa_sent else '❌ Failed'} | Action within: 2 hrs"
    )
    for attempt in range(1, 4):
        try:
            card = requests.post(
                "https://api.trello.com/1/cards",
                params={"key": TRELLO_KEY, "token": TRELLO_TOK,
                        "idList": TRELLO_LIST, "name": title, "desc": desc},
                timeout=10,
            )
            card.raise_for_status()
            card_id = card.json()["id"]

            cl = requests.post(
                "https://api.trello.com/1/checklists",
                params={"key": TRELLO_KEY, "token": TRELLO_TOK,
                        "idCard": card_id, "name": "Nurse Actions"},
                timeout=10,
            )
            cl.raise_for_status()
            cl_id = cl.json()["id"]

            for item in ["Review call summary", "Contact patient", "Inform doctor", "Resolve or escalate to ER"]:
                requests.post(
                    f"https://api.trello.com/1/checklists/{cl_id}/checkItems",
                    params={"key": TRELLO_KEY, "token": TRELLO_TOK, "name": item},
                    timeout=10,
                )
            print(f"[TRELLO ✓] {title}")
            return
        except Exception as e:
            print(f"[TRELLO] Attempt {attempt}/3: {e}")
            if attempt < 3:
                time.sleep(2)
    print(f"[TRELLO ✗] Card NOT created for {p['name']}")


# ═══════════════════════════════════════════════
#  CARE AGENT
# ═══════════════════════════════════════════════

class CareAgent(Agent):

    def __init__(self, patient: dict, last_pain: str, call_day: int):
        self._patient   = patient
        self._session   = None
        self._ended     = False
        self._log_done  = False
        self._call_day  = call_day
        self._last_pain = last_pain

        # State — written by tools, read at close time
        self._pain      = "not reported"
        self._symptoms  = "none reported"
        self._meds      = "not confirmed"
        self._flag      = False
        self._reason    = ""

        super().__init__(instructions=self._build_prompt(patient, last_pain, call_day))

    def on_session_started(self, session: AgentSession):
        self._session = session

    # ── PROMPT ─────────────────────────────────────────────────────────────

    def _build_prompt(self, p: dict, last_pain: str, call_day: int) -> str:
        return f"""
You are a warm post-discharge care voice assistant for {HOSPITAL_NAME}.
Your only job: a structured daily health check-in call. You are NOT a doctor. Never give medical advice.

PATIENT DATA — use ONLY this. Never invent anything.
  Name       : {p['name']}
  Surgery    : {p['surgery_type']}
  Medications: {p['medications']}
  Watchlist  : {p['watchlist']}
  Doctor     : Dr. {p['doctor_name']}
  Last Pain  : {last_pain}  ← never say this number aloud to the patient
  Day        : {call_day}

LANGUAGE: Start in English. If patient replies in Hindi, Hinglish, or Gujarati — switch immediately and stay in that language. Keep medication names in English always.

TONE: Warm and slow. One question at a time. Always wait for the full answer before moving on. Sound like a caring nurse, never a robot. If patient sounds anxious — reassure first, then continue.

=== 7-STEP FLOW — follow in order, never skip ===

STEP 1 — IDENTITY
Say: "Hello! Am I speaking with {p['name']}?"
• Confirmed → go to Step 2.
• Wrong person → ask if patient is available.
  If yes: wait, re-confirm identity directly with patient.
  If no (sleeping / out / at hospital): "No problem, I'll note this and have someone follow up." → flag_red_alert("Patient unavailable — caregiver answered") → log_and_close() → end_call().
• No response for 20 seconds: "I'll try again later." → end_call() ONLY. Do NOT call log_and_close().

STEP 2 — INTRO
Warm intro. Mention this is Day {call_day} check-in after {p['surgery_type']}. Don't preview the questions.

STEP 3 — PAIN SCORE
Ask: "On a scale of 1 to 10, how is your pain right now?"
• Vague → "Closer to 3–4, or more like 7–8?"
• Got number → call update_pain_score() immediately.
• Too much pain to talk → flag_red_alert("Severe pain — unable to continue call") → log_and_close() → end_call().

STEP 4 — SYMPTOMS
Ask about each item in the watchlist one at a time, woven naturally into conversation.
Watchlist: {p['watchlist']}
• Do NOT list all symptoms at once. Do NOT ask about anything outside the watchlist.
• Confirmed symptom → flag_red_alert("Watchlist symptom confirmed: [name]").
• "Maybe" or unsure → treat as confirmed → flag it.
• New serious symptom not on watchlist → flag_red_alert("New symptom: [name]").
• Emergency (chest pain / breathlessness / fainting) → "Please call emergency services right now." → flag_red_alert("EMERGENCY: [symptom]") → log_and_close() → end_call().

STEP 5 — MEDICATIONS
Ask: "Have you been able to take your medications today — {p['medications']}?"
Only mention these medications. Never name others.
• Not taken / ran out / can't access → flag_red_alert("Cannot access medications: [reason]").
• Doctor told them to stop (not in records) → flag_red_alert("Patient says doctor changed medications — needs verification").
• Any medication question → NEVER answer → flag_red_alert("Medication question: [their words]").

STEP 6 — OPEN CONCERNS
Ask: "Is there anything else you're feeling or worried about that I should note for your doctor?"
• Medical concern → flag if serious.
• Non-medical (billing / transport) → "The hospital admin team can help with that." Move on.

STEP 7 — CLOSE
Call log_and_close() with structured summary (format below).
Tell them: "I've shared your update with Dr. {p['doctor_name']}'s team."
If flagged: "Someone will follow up with you within 2–4 hours."
Warm goodbye → call end_call().

=== SUMMARY FORMAT — write this as transcript_summary inside log_and_close() ===
"Pain: X/10 (better/worse/same vs last score of {last_pain}). Symptoms: [list or none reported]. Meds: [taken / not taken / partial — reason if not]. Concerns: [any or none]. Red flag: YES — [reason] / NO. Outcome: completed / partial / unavailable / disconnected."

=== RED FLAGS — call flag_red_alert(reason) immediately for any of: ===
Pain ≥ 8 | Pain 2+ above {last_pain} | Any watchlist symptom confirmed or suspected | Can't access meds | Patient distressed or confused | At hospital during call | Caregiver answered | Any medical question | New serious symptom | Wound change reported | UNSURE → always flag, never guess

=== HARD RULES ===
• One question at a time. Always wait for the answer.
• Never give medical advice. Never.
• Never say the Last Pain Score number aloud to the patient.
• Never mention medications not in the patient data.
• Never call end_call() before log_and_close() — except Step 1 no-response.
• Never call log_and_close() before Steps 3–6 are done — except forced early close.

=== TOOL ORDER ===
update_pain_score(score)               → only after patient gives a confirmed number
flag_red_alert(reason)                 → immediately when concern is confirmed or suspected
log_and_close(symptoms, meds, summary) → only after Steps 3–6 done, using summary format above
end_call()                             → only after log_and_close() returns and goodbye is said
""".strip()

    # ── TOOLS ──────────────────────────────────────────────────────────────

    @function_tool(
        description=(
            "Call when patient gives a pain number. "
            "Extract digit from vague answers like 'about 6' or 'maybe 7'. "
            "Round decimals to nearest whole number."
        )
    )
    async def update_pain_score(self, score: int) -> str:
        # FIX: idempotency guard — interrupted speech can replay this tool
        if self._pain == str(score):
            print(f"[TOOL] Pain {score}/10 already recorded — skipping duplicate")
            return f"Pain score {score}/10 already noted."

        self._pain = str(score)
        print(f"[TOOL] Pain: {score}/10")

        if score >= 8:
            self._flag   = True
            self._reason = f"High pain score: {score}/10"
            print(f"[RED FLAG 🚨] High pain: {score}/10")
        elif pain_worsening(self._last_pain, score):
            self._flag   = True
            self._reason = f"Pain worsening — was {self._last_pain}/10, now {score}/10"
            print(f"[RED FLAG 🚨] Pain worsening: {self._last_pain} → {score}")

        return f"Pain score {score}/10 noted."

    @function_tool(
        description=(
            "Call immediately when any red flag is confirmed — high pain, worsening pain, "
            "watchlist symptom, medication issue, distress, medical question, or caregiver answered. "
            "Pass the exact reason as a string."
        )
    )
    async def flag_red_alert(self, reason: str) -> str:
        self._flag   = True
        self._reason = reason
        print(f"[RED FLAG 🚨] {reason}")
        return f"Flagged. Dr. {self._patient['doctor_name']}'s team will follow up shortly."

    @function_tool(
        description=(
            "Call at end of call with full structured summary. "
            "Must include pain, symptoms, meds, concerns, red flag status, and outcome. "
            "Must be called before end_call()."
        )
    )
    async def log_and_close(
        self,
        symptoms_reported : str,
        medications_taken : str,
        transcript_summary: str,
    ) -> str:
        self._symptoms = symptoms_reported
        self._meds     = medications_taken
        self._log_done = True

        # 1. Write to Google Sheets
        await asyncio.to_thread(
            log_call,
            self._patient["patient_id"], self._patient["name"],
            self._pain, symptoms_reported, medications_taken,
            self._flag, self._reason, transcript_summary,
        )

        # 2. Send WhatsApp
        wa_sent = await asyncio.to_thread(
            dispatch_whatsapp,
            self._patient, self._call_day, self._pain,
            symptoms_reported, medications_taken,
            self._flag, self._reason,
        )

        # 3. Trello card — only if red flag raised
        if self._flag:
            await asyncio.to_thread(
                create_trello_card,
                self._patient, self._call_day, self._pain,
                symptoms_reported, medications_taken,
                self._reason, transcript_summary, wa_sent,
            )

        return "Logged to Sheets. WhatsApp sent. Trello card created if flagged."

    @function_tool(
        description=(
            "End the session. Only call AFTER log_and_close() has returned "
            "and goodbye has been said to the patient."
        )
    )
    async def end_call(self, outcome: str = "completed") -> str:
        if self._ended:
            return "Already ended."

        # Safety net — log if end_call fires before log_and_close somehow
        if not self._log_done:
            print("[WARN] Safety-net log — end_call before log_and_close")
            await asyncio.to_thread(
                log_call,
                self._patient["patient_id"], self._patient["name"],
                self._pain, self._symptoms, self._meds,
                self._flag, self._reason or "Call ended before normal logging",
                f"Safety-net log. Outcome: {outcome}",
            )

        self._ended = True
        asyncio.create_task(self._close_after_speech())
        return "Session closing."

    async def _close_after_speech(self):
        await asyncio.sleep(14)
        if self._session:
            await self._session.aclose()

    async def handle_disconnect(self):
        """Patient disconnected before end_call(). Log partial + send missed-call WhatsApp."""
        if self._ended or self._log_done:
            return
        self._ended = True
        print("[WARN] Patient disconnected — logging partial data")
        await asyncio.to_thread(
            log_call,
            self._patient["patient_id"], self._patient["name"],
            self._pain, self._symptoms, self._meds,
            self._flag, self._reason or "Call dropped",
            "Patient disconnected mid-call.",
        )
        await asyncio.to_thread(
            dispatch_whatsapp,
            self._patient, self._call_day, self._pain,
            self._symptoms, self._meds,
            self._flag, self._reason,
            True, "2 hours from now",
        )


# ── TTS ──────────────────────────────────────────────────────────────────────
ACTIVE_TTS = cartesia.TTS(
    model="sonic-3",                           # The best model for dedicated English
    language="en",                             # Enforces strict English speech generation
    voice="248be419-c632-4f23-adf1-5324ed7dbf1d", # Your targeted English voice ID
    speed=0.85,                                # Numeric float < 1.0 creates a natural "slow" pace
    emotion=["positivity:medium"],             # Expressive control supported natively by sonic-3
)

# ── LIVEKIT ENTRYPOINT ───────────────────────────────────────────────────────
async def entrypoint(ctx: agents.JobContext):
    patient = get_patient(ACTIVE_PATIENT_ID)
    if not patient:
        print(f"[ERROR] Patient '{ACTIVE_PATIENT_ID}' not found — aborting")
        return

    last_pain = get_last_pain(ACTIVE_PATIENT_ID)
    call_day  = compute_day(str(patient.get("discharge_date", "")))

    print(f"\n[INFO] Patient  : {patient['name']}")
    print(f"[INFO] Surgery  : {patient['surgery_type']}")
    print(f"[INFO] Last Pain: {last_pain}")
    print(f"[INFO] Day      : {call_day}")

    agent = CareAgent(patient=patient, last_pain=last_pain, call_day=call_day)

    session = AgentSession(
        # FIX: switched from livekit inference STT to deepgram direct —
        # inference STT relay was causing WinError 64 / connection drops on Windows
        stt = deepgram.STT(
    model="nova-3",      # Deepgram's flagship fast streaming model
    language="en-US",    # Locks tokenizer strictly to English (Best accuracy)
),
        # FIX: using llama-3.1-8b-instant — higher TPM limit than 70b on Groq free tier
        llm = google.LLM(
        model="gemini-2.5-flash",
        temperature=0.2
    ),
        tts=ACTIVE_TTS,
        vad=silero.VAD.load(min_silence_duration=0.25),
        turn_detection=MultilingualModel(),
        turn_handling=TurnHandlingOptions(
            endpointing={
                "mode"     : "dynamic",
                "min_delay": 0.6,   # longer — elderly / slow speakers
                "max_delay": 2.5,
            },
            interruption={"mode": "vad"},
        ),
        allow_interruptions   =True,
        preemptive_generation =True,
    )

    @ctx.room.on("participant_disconnected")
    def on_leave(participant):
        asyncio.create_task(_on_disconnect(agent, session))

    async def _on_disconnect(a: CareAgent, s: AgentSession):
        await a.handle_disconnect()
        try:
            await s.aclose()
        except Exception:
            pass

    await session.start(room=ctx.room, agent=agent)
    agent.on_session_started(session)

    await session.say(
        f"Hello! Am I speaking with {patient['name']}?",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )