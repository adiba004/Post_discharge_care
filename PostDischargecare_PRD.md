## 1. Document summary

This PRD describes a product to reduce preventable hospital readmissions after patient discharge.

The product is an AI voice agent that checks in with patients during the high-risk 7-14 day period after discharge. It speaks with patients in simple language, detects red flags, updates patient status, and alerts nurses when human follow-up is needed.

The goal is not to replace nurses. The goal is to help nurses cover more patients safely by automating routine check-ins and escalating only the cases that need human attention.

## 2. Problem statement

After discharge, many patients enter a dangerous care gap.

There is often no touchpoint between hospital discharge and the next appointment, which is usually 7-14 days later. During this time:

- Patients miss medications.
- Patients ignore or fail to notice worsening symptoms.
- Patients may not understand discharge instructions.
- Nurses do not have capacity to call every patient every day.
- Preventable issues become readmissions.

This creates poor patient outcomes and high cost for both hospitals and patients.

## 3. Why this matters

Readmissions are expensive, stressful for patients, and often preventable.

A better follow-up system can help hospitals:

- Catch risk earlier.
- Improve patient adherence to medications and instructions.
- Reduce avoidable readmissions.
- Use nurse time more efficiently.
- Improve patient confidence after discharge.

## 4. Background / opportunity

Today, most post-discharge follow-up is manual, inconsistent, or missing.

Hospitals know that patients need support after discharge, but operations teams face two major limits:

1. Nurse capacity is limited.
2. Outreach needs to happen repeatedly, not just once.

An AI voice agent is a strong fit because it can:

- Reach many patients every day.
- Follow the same safe check-in structure each time.
- Speak in English, Hindi, and Hinglish.
- Escalate only when needed.
- Create a clear daily queue for nurses.

## 5. Product vision

Create a safe, scalable post-discharge follow-up system where every discharged patient receives proactive outreach, risk is identified early, and nurses focus only on patients who need clinical attention.

## 6. Goals

### Business goals

- Reduce 30-day preventable readmissions.
- Reduce manual outreach burden on nurses.
- Improve coverage of post-discharge follow-up.
- Create a repeatable model hospitals can scale across departments.

### User goals

- Help patients feel supported after discharge.
- Help patients follow medication and recovery instructions.
- Help nurses identify which patients need urgent attention.
- Help care teams act earlier before symptoms worsen.

## 7. Success measures

### Primary success measures

- Reduction in 30-day readmission rate for patients enrolled in the program.
- Percentage of discharged patients successfully reached within the follow-up window.
- Percentage of red-flag cases reviewed by a nurse within SLA.
- Reduction in nurse time spent on routine check-in calls.

### Secondary success measures

- Medication adherence signal rate.
- Callback completion rate for busy or unanswered patients.
- Percentage of conversations completed end-to-end by the AI agent.
- Patient satisfaction with follow-up experience.
- Accuracy of red-flag detection.
- False-positive alert rate.
- False-negative escalation misses.

## 8. Target users

### Primary users

- Discharged patients recovering at home.
- Nurses or care coordinators monitoring recovery.

### Secondary users

- Hospital operations teams.
- Department heads / care program owners.
- Quality teams tracking readmissions and patient outcomes.

## 9. User personas

### Persona 1: Recovering patient

- Recently discharged after surgery or treatment.
- May be anxious, tired, or confused.
- May prefer Hindi, Hinglish, or English.
- Needs simple questions and clear next steps.

### Persona 2: Nurse / care coordinator

- Manages many discharged patients at once.
- Cannot manually call every patient daily.
- Needs quick visibility into which patients are high risk.
- Needs reliable summaries and clear escalation reasons.

### Persona 3: Hospital operations lead

- Wants lower readmissions and better follow-up coverage.
- Needs measurable outcomes, not just call volume.
- Needs a system that is easy to operate and audit.

Detailed personas: [aasha_personas_final.pdf](aasha_personas_final.pdf)

## 10. As-is state

Today, the discharge follow-up experience looks like this:

- Patient is discharged from the hospital.
- Instructions may be given verbally or on paper.
- The next appointment is typically 7-14 days later.
- In many cases, no daily monitoring happens in between.
- Some patients forget medications or do not understand what symptoms matter.
- Nurses may call some patients manually, but not all.
- Outreach quality varies by person, shift, and workload.
- Important issues may only be discovered when the patient worsens or returns to the hospital.

### Current pain points

- No consistent touchpoint after discharge.
- High-risk symptoms may go unnoticed.
- Medication non-adherence is detected late.
- Nurses spend time on low-risk check-ins instead of high-risk follow-up.
- No structured daily monitoring across all patients.
- Escalation is reactive instead of proactive.

## 11. Future state

In the future experience:

- Every eligible discharged patient is enrolled into an automated follow-up program.
- The AI voice agent calls patients on scheduled days.
- The agent greets the patient by name and uses patient-specific context.
- The agent asks a structured recovery check-in.
- The system detects red flags automatically.
- Low-risk cases are documented without nurse effort.
- High-risk cases are surfaced quickly to nurses with clear summaries.
- Nurses focus their time only on the patients who need human attention.
- Hospitals get visibility into outcomes, call performance, and risk trends.

## 12. Jobs to be done

### Patient job to be done

When I am recovering at home after discharge, I want someone to check on me in a simple and trustworthy way, so I can stay on track and get help before my condition worsens.

### Nurse job to be done

When I am managing many discharged patients, I want a system that identifies which patients are likely at risk, so I can focus my time on the people who most need follow-up.

### Hospital job to be done

When we discharge patients, we want a scalable follow-up process that reduces avoidable readmissions and improves quality of care without adding large manual workload.

## 13. Product scope

### In scope

- Outbound AI voice calls to discharged patients.
- Personalized calls using patient name, surgery / case context, medications, and watchlist symptoms.
- Structured 9-step check-in flow.
- Support for English, Hindi, and Hinglish.
- Tone adaptation based on patient emotional state.
- Red-flag detection for defined risk signals.
- Google Sheets as the initial patient data source and status tracker.
- Writing call summaries and latest status back to Google Sheets.
- Nurse-facing red-flag visibility in Google Sheets.
- Safe escalation to human care team when required.
- Callback handling for busy patients.

### Out of scope for MVP

- AI giving medical advice.
- Replacing clinical judgment.
- Full EMR / EHR integration.
- Two-way nurse chat inside the product.
- Automated treatment changes.
- Complex appointment scheduling workflows.
- Full multilingual support beyond the first 3 languages.
- Fully automated handling of escalation cases.

## 14. Product principles

- **Safety first:** If the system is unsure, escalate.
- **Simple language:** Questions must be easy for patients to understand.
- **Human in the loop:** Nurses handle flagged cases.
- **Consistency:** Every patient gets a structured check-in.
- **Auditability:** Every call outcome and flag reason is recorded.
- **Respect and trust:** Tone must be calm, supportive, and non-judgmental.

## 15. Proposed solution overview

The product is an AI voice-based post-discharge follow-up system with four core layers:

### 15.1 Voice Agent

The AI voice agent:

- Calls patients by name.
- Knows patient context such as surgery, medications, and watchlist symptoms.
- Conducts a structured 9-step check-in.
- Supports English, Hindi, and Hinglish.
- Adapts tone to the patient's emotional state.

### 15.2 Red Flag Detection

The system flags cases when it detects:

- High pain.
- Worsening pain trend.
- Watchlist symptoms.
- Wound concerns.
- Falls.
- Medication access issues.
- Cognitive confusion.

A rules / Python-based gate validates the escalation logic to reduce false flags.

### 15.3 Data Layer

The system:

- Reads patient context from Google Sheets.
- Writes back full call summaries after each call.
- Updates patient status in real time.
- Maintains a simple operating view for the care team.

### 15.4 Nurse Alert Layer

When a patient is flagged:

- A red flag appears in Google Sheets.
- The nurse reviews the case.
- Human follow-up begins outside the AI layer.
- No AI is used for clinical handling after escalation in the MVP.

## 16. End-to-end user flow

1. Patient is discharged and added to the follow-up list.
2. Patient record includes name, discharge reason / surgery, medication list, and watchlist symptoms.
3. AI voice agent calls the patient on the scheduled day.
4. Patient answers and completes the structured check-in.
5. AI records responses and checks for risk patterns.
6. If no red flag is detected, the call is marked complete and summary is logged.
7. If patient is busy, callback is scheduled.
8. If a red flag is detected, the patient is marked for nurse review.
9. Nurse sees flagged cases in Google Sheets and follows up manually.

## 17. Detailed conversation flow

The exact wording may evolve, but the MVP should support a structured check-in such as:

1. Greeting and identity confirmation.
2. Confirm recovery context (for example surgery / discharge type).
3. General wellbeing check.
4. Pain check.
5. Symptom check against watchlist.
6. Medication adherence / access check.
7. Wound / mobility / fall risk check where relevant.
8. Clarifying questions if concerning answers are given.
9. Close with reassurance and next-step guidance.

### Important rule

The system must not answer medical questions with clinical advice. If the patient asks for medical advice, the system should escalate to a nurse / human care team.

## 18. Functional requirements

### 18.1 Patient data intake

The system must:

- Read patient profile data from Google Sheets.
- Support fields such as patient name, phone number, surgery / discharge type, medication list, watchlist symptoms, call status, and escalation status.
- Allow simple status updates after each call.

### 18.2 Outbound calling

The system must:

- Place outbound voice calls to patients.
- Retry or callback based on configurable rules.
- Recognize basic call outcomes such as answered, busy, no answer, and failed.
- Record the final outcome of each attempt.

### 18.3 Conversation engine

The system must:

- Follow a structured, controlled conversation path.
- Personalize the conversation using patient data.
- Handle English, Hindi, and Hinglish.
- Detect emotional cues and adapt tone.
- Keep prompts short and easy to understand.

### 18.4 Red-flag logic

The system must flag when it detects:

- Severe pain.
- Increasing pain over time.
- Listed warning symptoms.
- Wound changes.
- Fall or possible injury.
- Medication access issue.
- Cognitive confusion.
- Patient asks a medical question that requires clinician support.

The system should also support configurable threshold logic so hospital teams can tune rules later.

### 18.5 Documentation and status updates

The system must:

- Save a structured call summary after each completed interaction.
- Update patient status in Google Sheets.
- Store reason codes for flag / no flag outcomes.
- Capture timestamps for calls and escalations.

### 18.6 Nurse review workflow

The system must:

- Mark flagged patients clearly in Google Sheets.
- Show why the patient was flagged.
- Distinguish informational completion from urgent follow-up.
- Avoid using AI for clinical triage resolution after escalation in MVP.

## 19. Edge-case requirements

The MVP must correctly handle these cases:

- **Busy patient:** schedule a callback; do not flag.
- **Cognitive confusion:** immediate flag.
- **Patient already at hospital:** do not create duplicate escalation.
- **Fall detected:** flag.
- **Wound change detected:** flag.
- **Medication access issue:** flag.
- **Medical question asked by patient:** do not answer; always flag.
- **Unable to complete conversation:** save partial outcome and retry / route based on logic.

## 20. Non-functional requirements

- High call reliability.
- Simple and understandable voice experience.
- Low latency in conversation response.
- Secure handling of patient data.
- Accurate audit trail for call summaries and flags.
- Configurable rules without heavy engineering for every change.
- Clear fallback behavior when AI confidence is low.

## 21. Safety requirements

Because this product touches health-related recovery workflows, safety requirements are critical:

- The AI must not diagnose.
- The AI must not recommend treatment changes.
- The AI must not reassure a clearly risky patient without escalation.
- The system must escalate uncertain cases.
- All flag logic should be reviewable and testable.
- Escalation reasons must be visible to human reviewers.

## 22. Assumptions

- Hospitals can provide a daily or batch patient list.
- Patients are reachable by phone after discharge.
- A structured watchlist exists by discharge type or surgery type.
- Nurses will review flagged cases during defined operating hours.
- Google Sheets is acceptable for the first operating version.
- The hospital accepts a human-in-the-loop care model for flagged cases.

## 23. Dependencies

### Clinical / operational dependencies

- Defined discharge workflows.
- Approved symptom watchlists.
- Nurse review process and ownership.
- Escalation SLA definition.
- Approved call script / wording.

### Product / technical dependencies

- Voice calling provider.
- Speech-to-text and text-to-speech quality for English, Hindi, and Hinglish.
- Red-flag rules engine or Python validation layer.
- Google Sheets integration.
- Patient data formatting and cleanliness.
- Logging and monitoring.

### Compliance / governance dependencies

- Consent and outreach policy.
- Patient data privacy and security requirements.
- Hospital approval for content and escalation logic.
- Review process for prompt / script updates.

## 24. Risks and mitigations

### Risk 1: False negatives miss truly risky patients

**Impact:** serious patient safety issue.

**Mitigation:** conservative thresholds, mandatory escalation for uncertain cases, pilot review of transcripts, human QA.

### Risk 2: False positives create too many nurse alerts

**Impact:** alert fatigue and reduced trust.

**Mitigation:** rules-based validation layer, tune thresholds during pilot, track false-positive rate weekly.

### Risk 3: Patients do not understand the AI or language quality is weak

**Impact:** low completion and low trust.

**Mitigation:** use short prompts, test Hindi and Hinglish deeply, support repeat / rephrase behavior.

### Risk 4: Patients ask for medical advice

**Impact:** safety and liability risk.

**Mitigation:** never answer clinical questions; always escalate.

### Risk 5: Poor patient data quality in Google Sheets

**Impact:** wrong personalization, failed calls, weak summaries.

**Mitigation:** input validation, required-field checks, data-cleaning process.

### Risk 6: Nurse team cannot respond fast enough to flags

**Impact:** escalation value drops.

**Mitigation:** define SLA, working hours, ownership, and alert review cadence before pilot.

### Risk 7: Patients do not answer unknown numbers

**Impact:** lower reach rate.

**Mitigation:** branded calling where possible, retry strategy, prior SMS / discharge communication.

### Risk 8: Emotion detection is inaccurate

**Impact:** poor conversation quality.

**Mitigation:** use tone adaptation as supportive behavior only, not for core clinical decisioning.

## 25. Metrics

### Outcome metrics

- 30-day readmission rate.
- Preventable readmission rate.
- Time from discharge to first successful contact.
- Percentage of patients with at least one successful follow-up.

### Operational metrics

- Call answer rate.
- Call completion rate.
- Callback success rate.
- Average call duration.
- Flag rate.
- Nurse review turnaround time.
- Daily flagged patient volume.

### Quality metrics

- Red-flag precision.
- Red-flag recall.
- False-positive rate.
- False-negative rate.
- Script adherence rate.
- Conversation drop-off rate by step.

### Experience metrics

- Patient satisfaction score.
- Nurse satisfaction / trust score.
- Language-wise completion rate.
- Language-wise misunderstanding rate.

## 26. North star

Increase safe post-discharge follow-up coverage while reducing preventable readmissions.

## 27. Release strategy: 3 phases from research to MVP

## Phase 1: Research and clinical design

### Objective

Validate the problem, define the safest workflow, and identify what the MVP should and should not do.

### Key questions to answer

- Which patient cohorts have the highest readmission risk?
- Which surgeries / discharge types should we start with?
- Which symptoms must always trigger escalation?
- What wording is easiest for patients to understand?
- What operating model can nurses realistically support?

### Activities

- Interview nurses, care coordinators, and discharge teams.
- Review current discharge journey and follow-up process.
- Analyze readmission drivers and common post-discharge issues.
- Define patient cohorts and use cases for phase 1.
- Create symptom watchlists and escalation rules.
- Draft conversation script and safety boundaries.
- Validate what data fields are available in Google Sheets or source systems.

### Deliverables

- Problem validation report.
- As-is journey map.
- Future-state workflow.
- Patient cohort definition.
- Initial call script.
- Red-flag taxonomy.
- Operating model for nurse follow-up.
- Pilot success metrics and baseline.

### Exit criteria

- Clinical stakeholders approve escalation logic.
- First patient cohort is selected.
- Required data fields are identified.
- MVP scope is frozen.

## Phase 2: Pilot / prototype

### Objective

Test the workflow in a controlled environment and learn before scaling.

### Scope

- Limited hospital unit or patient cohort.
- Limited number of patients.
- English + Hindi, with Hinglish if quality is acceptable.
- Google Sheets-based operations.
- Manual review of flagged cases by nurses.

### Activities

- Build the first working voice agent.
- Connect Google Sheets for read / write.
- Implement structured call flow.
- Add basic red-flag logic and Python validation gate.
- Train / tune prompts for language clarity.
- Run supervised pilot with daily review.
- Audit calls, summaries, and flag quality.

### Deliverables

- Working prototype.
- Pilot operations dashboard in Google Sheets.
- QA rubric for calls.
- Daily issue log and iteration backlog.
- Initial performance report.

### Exit criteria

- Stable call completion rate.
- Acceptable flag accuracy.
- Nurses confirm alert volume is manageable.
- No major safety failure in pilot.
- Team agrees on MVP improvements.

## Phase 3: MVP

### Objective

Launch a reliable first version that can run as a real hospital workflow for a defined use case.

### Scope

- Production-ready outbound call flow.
- Personalized patient context.
- 9-step recovery check-in.
- English, Hindi, and Hinglish support.
- Red-flag detection for defined conditions.
- Real-time summary writeback to Google Sheets.
- Nurse alert workflow in Google Sheets.
- Callback handling and basic reporting.

### MVP success definition

The MVP is successful if it can:

- Reach a meaningful share of target patients.
- Surface high-risk cases reliably.
- Reduce manual nurse workload for low-risk check-ins.
- Operate safely with clear human escalation.
- Produce measurable improvement in follow-up coverage.

### Post-MVP ideas

- EHR / EMR integration.
- Appointment coordination.
- SMS reminders.
- Broader language coverage.
- Department-specific recovery playbooks.
- Better nurse workflow UI beyond Google Sheets.

## 28. Open questions

- Which hospital department should be the first launch partner?
- Which patient cohorts are safest and highest value to start with?
- What is the acceptable maximum false-negative rate?
- Should all patients receive the same call cadence?
- How will patient consent be captured and stored?
- Is there a need for SMS backup if calls fail?
- What are the nurse SLAs for urgent vs non-urgent flags?

## 29. Recommendation

Start with one defined patient cohort, one hospital team, and a narrow set of red flags. Optimize for safety, clarity, and nurse trust before expanding automation depth or adding more workflows.

## 30. One-line MVP statement

An AI voice agent that checks on discharged patients in English, Hindi, and Hinglish, detects recovery risks early, logs every interaction, and alerts nurses only when human follow-up is needed.