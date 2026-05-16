"""
agent_mvp.py  —  Post-Discharge Care Agent (Knee Replacement)
==============================================================
RUN:
    python agent_mvp.py console      # local mic/speaker test
    python agent_mvp.py dev          # LiveKit playground
"""

import asyncio
import logging
import os
import time
from datetime import datetime

import gspread
import requests
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
from livekit.plugins import google
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext, TurnHandlingOptions
from livekit.agents import room_io
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, silero
from livekit.plugins.groq import LLM as GroqLLM
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env")
logger = logging.getLogger("care-agent")

ACTIVE_PATIENT_ID = "P001"

HOSPITAL_NAME  = os.getenv("HOSPITAL_NAME", "City Care Hospital")
HOSPITAL_PHONE = os.getenv("HOSPITAL_PHONE", "1800-XXX-XXXX")
TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TRELLO_KEY     = os.getenv("TRELLO_API_KEY")
TRELLO_TOK     = os.getenv("TRELLO_TOKEN")
TRELLO_LIST    = os.getenv("TRELLO_LIST_ID")

gc             = gspread.service_account(filename="pp.json")
patients_sheet = gc.open("Patient_data").get_worksheet(0)
logs_sheet     = gc.open("call_logs").get_worksheet(0)


# =============================================================================
#  SHEET HELPERS
# =============================================================================

def get_patient(pid: str) -> dict | None:
    for r in patients_sheet.get_all_records():
        if str(r.get("patient_id", "")).strip() == pid.strip():
            return r
    return None


def get_last_pain(pid: str) -> str:
    for r in patients_sheet.get_all_records():
        if str(r.get("patient_id", "")).strip() == pid.strip():
            s = str(r.get("last_pain_score", "")).strip()
            return s if (s and s != "0") else "no previous record"
    return "no previous record"


def pain_worsening(last: str, current: int) -> bool:
    try:
        return int(last) != 0 and (current - int(last)) >= 2
    except (ValueError, TypeError):
        return False


def compute_day(discharge_str: str) -> int:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return max((datetime.now() - datetime.strptime(discharge_str.strip(), fmt)).days + 1, 1)
        except ValueError:
            continue
    return 1


def update_patient_status(pid: str, pain: str, red_flag: bool) -> None:
    rows    = patients_sheet.get_all_records()
    headers = patients_sheet.row_values(1)
    pain_col   = (headers.index("last_pain_score") + 1) if "last_pain_score" in headers else None
    status_col = (headers.index("current_status")  + 1) if "current_status"  in headers else None
    for i, r in enumerate(rows):
        if str(r.get("patient_id", "")).strip() == pid.strip():
            n = i + 2
            if pain_col:   patients_sheet.update_cell(n, pain_col, pain)
            if status_col: patients_sheet.update_cell(n, status_col,
                "URGENT - Nurse Review Needed" if red_flag else "Checked In")
            return


def log_call(pid, name, pain, symptoms, meds, mobility, exercises, red_flag, reason, summary):
    row = [pid, name, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"),
           pain, symptoms, meds, mobility, exercises, "YES" if red_flag else "NO", reason, summary]
    for attempt in range(1, 4):
        try:
            logs_sheet.append_row(row)
            update_patient_status(pid, pain, red_flag)
            logger.info("[LOG] %s | Pain:%s | Flag:%s", name, pain, "YES" if red_flag else "NO")
            return
        except Exception as exc:
            logger.warning("[WARN] Sheet %d/3: %s", attempt, exc)
            if attempt < 3: time.sleep(2)
    backup = f"backup_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    open(backup, "w").write(str(row))
    logger.critical("[CRITICAL] Backup -> %s", backup)


# =============================================================================
#  WHATSAPP
# =============================================================================

def _safe(v, fallback="not recorded"):
    return v if (v and v.strip() not in {"", "0", "not reported", "none reported",
                                         "not confirmed", "not assessed"}) else fallback

def _wa_normal(p, day, pain, symptoms, meds, mobility):
    return (
        f"*{HOSPITAL_NAME} - Day {day} Check-In*\n\n"
        f"Hi {p['name']} Thank you for today's check-in.\n\n"
        f"Pain: {_safe(pain)}/10 | Symptoms: {_safe(symptoms,'None')} | Mobility: {_safe(mobility)}\n\n"
        f"Meds: {p['prescribed_medications']}\nExercises: {p['prescribed_exercises']}\n\n"
        f"Do not stop meds without consulting your doctor. Helpline: {HOSPITAL_PHONE}"
    )

def _wa_red_flag(p, day, pain, reason, symptoms):
    return (
        f"URGENT - {HOSPITAL_NAME} Alert\n\n"
        f"Hi {p['name']}, concern flagged on Day {day}: {reason}\n\n"
        f"A nurse will call within 2-4 hrs. Emergency: {HOSPITAL_PHONE}\n\n"
        f"{p['emergency_notes']}\n\nKeep taking: {p['prescribed_medications']}"
    )

def _wa_missed(p, day, retry_time):
    return (
        f"{HOSPITAL_NAME} - Missed Day {day} Check-In\n\n"
        f"Hi {p['name']} We missed you. Will try again at {retry_time}.\n\n"
        f"Please take your meds: {p['prescribed_medications']}\n{HOSPITAL_PHONE}"
    )

def send_whatsapp(to, body):
    if not all([TWILIO_SID, TWILIO_AUTH, to]):
        return False
    for attempt in range(1, 3):
        try:
            m = TwilioClient(TWILIO_SID, TWILIO_AUTH).messages.create(
                from_=TWILIO_WA_FROM, to="whatsapp:" + to, body=body)
            logger.info("[WA] Sent %s", m.sid)
            return True
        except Exception as exc:
            logger.warning("[WA] %d/2: %s", attempt, exc)
            if attempt < 2: time.sleep(3)
    return False

def dispatch_whatsapp(p, day, pain, symptoms, meds, mobility, red_flag, reason,
                      missed=False, retry_time="2 hours from now"):
    phone = str(p.get("phone_number", "")).strip().replace(" ", "")
    if not phone: return False
    msg = (_wa_missed(p, day, retry_time) if missed
           else _wa_red_flag(p, day, pain, reason, symptoms) if red_flag
           else _wa_normal(p, day, pain, symptoms, meds, mobility))
    return send_whatsapp(phone, msg)


# =============================================================================
#  TRELLO
# =============================================================================

def create_trello_card(p, day, pain, symptoms, meds, reason, summary, wa_sent):
    if not all([TRELLO_KEY, TRELLO_TOK, TRELLO_LIST]): return
    title = f"URGENT {p['name']} Day {day} - {reason[:55]}"
    desc  = (f"Patient: {p['patient_id']} | {p['surgery_type']} | Risk: {p['risk_factors']}\n"
             f"Flag: {reason}\nPain: {pain}/10 | {p['emergency_notes']}\n\n{summary}\n"
             f"WA: {'Sent' if wa_sent else 'FAILED'}")
    for attempt in range(1, 4):
        try:
            card = requests.post("https://api.trello.com/1/cards",
                params={"key": TRELLO_KEY, "token": TRELLO_TOK,
                        "idList": TRELLO_LIST, "name": title, "desc": desc}, timeout=10)
            card.raise_for_status()
            cl = requests.post("https://api.trello.com/1/checklists",
                params={"key": TRELLO_KEY, "token": TRELLO_TOK,
                        "idCard": card.json()["id"], "name": "Nurse Actions"}, timeout=10)
            cl.raise_for_status()
            for item in ["Review summary", "Contact patient", "Inform doctor", "Resolve or escalate"]:
                requests.post(f"https://api.trello.com/1/checklists/{cl.json()['id']}/checkItems",
                    params={"key": TRELLO_KEY, "token": TRELLO_TOK, "name": item}, timeout=10)
            return
        except Exception as exc:
            logger.warning("[TRELLO] %d/3: %s", attempt, exc)
            if attempt < 3: time.sleep(2)


# =============================================================================
#  PROMPT — ~250 tokens
# =============================================================================

def build_prompt(p: dict, last_pain: str, call_day: int) -> str:
    return (
        f"You are Aasha, a warm post-discharge voice assistant for {HOSPITAL_NAME}. "
        f"Day {call_day} knee replacement check-in. NOT a doctor. Never give medical advice.\n\n"

        f"PATIENT: {p['name']} | {p['surgery_type']} | Age {p['age']} | Risk: {p['risk_factors']}\n"
        f"MEDS: {p['prescribed_medications']} | SCHEDULE: {p['medication_schedule']}\n"
        f"EXERCISES: {p['prescribed_exercises']} | AID: {p['mobility_support']}\n"
        f"NEXT FOLLOWUP: {p['next_followup_date']} | LAST PAIN: {last_pain} (never say aloud)\n\n"

        "VOICE RULES: Plain speech only. One question at a time. Wait for full answer. "
        "Switch to Hindi/Gujarati if patient uses it.\n\n"

        "STEPS (in order, never skip):\n"
        f"1. CONFIRM: 'Am I speaking with {p['name']}?' "
        "No answer 20s -> end_call only. Unavailable -> flag+log_and_close+end_call.\n"
        f"2. INTRO: Warm Day {call_day} knee check-in intro.\n"
        "3. PAIN: Ask 1-10. Confirmed -> update_pain_score() immediately.\n"
        "4. WOUND: Swelling improving? Wound clean/dry? Redness/discharge/smell/fever?\n"
        f"5. MOBILITY: Walking safely with {p['mobility_support']}? Falls? Knee locking?\n"
        "6. EXERCISES: Done today? Skipped any?\n"
        "7. MEDS: All taken on schedule? Flag if missed blood thinner or can't access.\n"
        "8. WELLBEING: Sleep ok? Eating/drinking? Anything else?\n"
        f"9. CLOSE: log_and_close() -> 'Update shared with care team, next followup {p['next_followup_date']}.' Goodbye -> end_call().\n\n"

        f"FLAG via flag_red_alert(reason): Pain>=8 | Pain 2+ above {last_pain} | Fever>101F | "
        "Wound redness/discharge/smell | Calf pain | Chest pain | Breathlessness | Fainting | "
        "Missed blood thinner | Can't access meds | Fall | Knee locked | Distressed | Medical question. "
        "Unsure -> always flag. Use lookup_clinical_info to assess first if needed.\n\n"

        "TOOLS (ONE per turn, wait for reply after each):\n"
        "- update_pain_score(score): confirmed number only\n"
        "- lookup_clinical_info(query): assess any symptom\n"
        "- flag_red_alert(reason): clinical only, never identity/intro\n"
        "- log_and_close(symptoms,meds,mobility,exercises,summary): after steps 3-8\n"
        "- end_call(): after log_and_close+goodbye. Exception: step 1 no-response.\n"
        "NEVER batch tools. NEVER fabricate.\n\n"

        f"SUMMARY FORMAT: 'Day {call_day}. Pain X/10 vs {last_pain}. "
        "Swelling:[]. Wound:[]. Fever:y/n. Mobility:[]. Exercises:[]. "
        "Meds:[]. Wellbeing:[]. Flag:YES-[reason]/NO. Outcome:completed/partial/unavailable.'"
    )


# =============================================================================
#  CARE AGENT
# =============================================================================

class CareAgent(Agent):

    def __init__(self, patient: dict, last_pain: str, call_day: int) -> None:
        self._patient        = patient
        self._call_day       = call_day
        self._last_pain      = last_pain
        self._pain           = "not reported"
        self._symptoms       = "none reported"
        self._meds           = "not confirmed"
        self._mobility       = "not assessed"
        self._exercises      = "not confirmed"
        self._flag           = False
        self._reason         = ""
        self._pain_collected = False
        self._log_done       = False
        self._ended          = False
        super().__init__(instructions=build_prompt(patient, last_pain, call_day))

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                f"Greet warmly and confirm you are speaking with {self._patient['name']}. "
                f"You are Aasha from {HOSPITAL_NAME}, calling for Day {self._call_day} knee check-in."
            )
        )

    @function_tool(description="Look up clinical guidance for a symptom before deciding to flag.")
    async def lookup_clinical_info(self, context: RunContext, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["calf", "clot", "dvt"]):
            return "Calf pain/swelling = possible DVT. Call flag_red_alert immediately."
        if any(w in q for w in ["chest", "breath", "faint"]):
            return "Chest pain/breathlessness = possible PE. Tell patient to call ambulance now."
        if any(w in q for w in ["fever", "chills"]):
            return "Fever >101F post-surgery = infection. Call flag_red_alert immediately."
        if any(w in q for w in ["wound", "redness", "discharge", "smell", "pus"]):
            return "Wound discharge/redness/smell = infection. Call flag_red_alert immediately."
        if any(w in q for w in ["blood thinner", "rivaroxaban", "apixaban", "enoxaparin"]):
            return "Missed blood thinner = clot risk. Call flag_red_alert immediately."
        if any(w in q for w in ["pain", "normal"]):
            d = self._call_day
            if d <= 3:  return f"Day {d}: 5-7/10 normal. Heavy swelling. Full walker."
            if d <= 7:  return f"Day {d}: 4-6/10 normal. Swelling reducing. Short walks."
            if d <= 10: return f"Day {d}: 3-5/10 normal. 10-15 min walks. Bending improving."
            return      f"Day {d}: 2-4/10 normal. Near-independent walking."
        if "swelling" in q:
            return "Some swelling normal. Sudden increase or one leg much larger -> flag."
        return "Unsure. Call flag_red_alert to be safe."

    @function_tool(description="Record pain score 1-10. Call immediately on confirmed number. Extract from vague answers. Round decimals.")
    async def update_pain_score(self, context: RunContext, score: int) -> str:
        if self._pain == str(score):
            return f"Pain {score}/10 already noted."
        self._pain = str(score)
        self._pain_collected = True
        if score >= 8:
            self._flag, self._reason = True, f"High pain: {score}/10"
        elif pain_worsening(self._last_pain, score):
            self._flag, self._reason = True, f"Pain worsening: {self._last_pain}/10 -> {score}/10"
        return f"Pain {score}/10 noted. Proceed to Step 4."

    @function_tool(description="Flag clinical concern. Never call for identity, intro, or non-clinical reasons.")
    async def flag_red_alert(self, context: RunContext, reason: str) -> str:
        if any(w in reason.lower() for w in ["identity", "confirmed", "intro", "call started"]):
            return "Not a clinical flag. Continue from Step 2."
        self._flag, self._reason = True, reason
        logger.warning("[RED FLAG] %s", reason)
        return f"Flagged: {reason}. Continue check-in unless immediate emergency."

    @function_tool(description="Log call and send WhatsApp. Only after pain collected and steps 3-8 done.")
    async def log_and_close(self, context: RunContext, symptoms_reported: str,
                            medications_taken: str, mobility_status: str,
                            exercise_compliance: str, transcript_summary: str) -> str:
        if not self._pain_collected and not self._flag:
            return "Pain not collected. Ask: On a scale of 1 to 10, how is your pain today?"
        self._symptoms, self._meds  = symptoms_reported, medications_taken
        self._mobility, self._exercises = mobility_status, exercise_compliance
        self._log_done = True
        await asyncio.to_thread(log_call, self._patient["patient_id"], self._patient["name"],
            self._pain, symptoms_reported, medications_taken, mobility_status, exercise_compliance,
            self._flag, self._reason, transcript_summary)
        wa = await asyncio.to_thread(dispatch_whatsapp, self._patient, self._call_day, self._pain,
            symptoms_reported, medications_taken, mobility_status, self._flag, self._reason)
        if self._flag:
            await asyncio.to_thread(create_trello_card, self._patient, self._call_day, self._pain,
                symptoms_reported, medications_taken, self._reason, transcript_summary, wa)
        return "Logged. WhatsApp sent. Trello if flagged. Say goodbye and call end_call."

    @function_tool(description="End session. Only after log_and_close+goodbye. Exception: step 1 no-response.")
    async def end_call(self, context: RunContext, outcome: str = "completed") -> str:
        if self._ended: return "Already ended."
        if not self._log_done:
            await asyncio.to_thread(log_call, self._patient["patient_id"], self._patient["name"],
                self._pain, self._symptoms, self._meds, self._mobility, self._exercises,
                self._flag, self._reason or "Early end", f"Safety-net. Outcome: {outcome}")
        self._ended = True
        asyncio.create_task(self._close_after_speech())
        return "Closing."

    async def _close_after_speech(self):
        await asyncio.sleep(14)
        await self.session.aclose()

    async def _handle_disconnect(self):
        if self._ended or self._log_done: return
        self._ended = True
        await asyncio.to_thread(log_call, self._patient["patient_id"], self._patient["name"],
            self._pain, self._symptoms, self._meds, self._mobility, self._exercises,
            self._flag, self._reason or "Call dropped", "Patient disconnected.")
        await asyncio.to_thread(dispatch_whatsapp, self._patient, self._call_day, self._pain,
            self._symptoms, self._meds, self._mobility, self._flag, self._reason, True)


# =============================================================================
#  TTS + ENTRYPOINT
# =============================================================================

ACTIVE_TTS = cartesia.TTS(
    model="sonic-2-2025-03-07",
    voice="248be419-c632-4f23-adf1-5324ed7dbf1d",
    speed="slow",
    emotion=["positivity:medium"],
)


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    patient = get_patient(ACTIVE_PATIENT_ID)
    if not patient:
        logger.error("Patient '%s' not found", ACTIVE_PATIENT_ID)
        return
    last_pain = get_last_pain(ACTIVE_PATIENT_ID)
    call_day  = compute_day(str(patient.get("discharge_date", "")))
    logger.info("Patient: %s | Day: %d | Last pain: %s", patient["name"], call_day, last_pain)

    agent   = CareAgent(patient=patient, last_pain=last_pain, call_day=call_day)
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en-US"),
        llm = google.LLM(
        model="gemini-2.5-flash",
        temperature=0.2
    ),
        tts=ACTIVE_TTS,
        vad=silero.VAD.load(min_silence_duration=0.25),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
            endpointing={"mode": "dynamic", "min_delay": 0.6, "max_delay": 2.5},
            interruption={"mode": "vad", "resume_false_interruption": True,
                          "false_interruption_timeout": 1.0},
        ),
        user_away_timeout=20.0,
        max_tool_steps=5,
    )

    @session.on("close")
    def _on_close(*args):
        if not agent._log_done:
            asyncio.get_event_loop().create_task(agent._handle_disconnect())

    await session.start(room=ctx.room, agent=agent,
                        room_options=room_io.RoomOptions(close_on_disconnect=True))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))