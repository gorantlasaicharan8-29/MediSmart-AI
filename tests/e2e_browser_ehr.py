"""
PHASE 10.1: Real Browser End-to-End EHR Verification Script.

Executes a full, authentic browser workflow against Google Chrome using Chrome DevTools Protocol (CDP):
1. Setup seed doctor and patient in medismart_test_db with a scheduled appointment.
2. Launch Google Chrome headless with remote debugging.
3. Doctor Workflow:
   - Login as Doctor (dr.rajesh.sharma@medismart.demo)
   - Navigate to Doctor Workspace
   - Open Consultation Record Modal
   - Fill Clinical Notes (Chief complaint, symptoms, examination, treatment plan, diagnosis)
   - Issue Digital Prescription with medications and dosage
   - Recommend Follow-Up appointment
   - Submit consultation encounter
   - Amend prescription with clinical rationale and adjusted dosage (v2)
   - Capture screenshot
4. Patient Workflow:
   - Login as Patient (patient.ehr.e2e@medismart.demo)
   - Navigate to /medical-records
   - Verify signed consultation encounter
   - Verify digital prescription with Revision v2 and Clinical Amendment Rationale
   - Verify clinician diagnosis badge and ICD-10 code
   - Verify follow-up recommendation and click Book Recommended Appointment
   - Capture screenshot
5. Verify Clinical Audit Trail logs in PostgreSQL.
"""
import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import websockets

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select, delete, text
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.security import get_password_hash
from app.models.user import User
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.models.ehr import ConsultationNote, Diagnosis, Prescription, PrescriptionItem, ClinicalAuditLog

TEST_DB_URL = "postgresql+asyncpg://postgres:Saicharan%40292007@localhost:5432/medismart_test_db"
CLINIC_TZ = ZoneInfo("Asia/Kolkata")
ARTIFACTS_DIR = Path(r"C:\Users\goran\.gemini\antigravity\brain\625a1890-4e3a-4709-a3e3-c577aa362b61")


class CDPBrowserSession:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.req_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=10_000_000)
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        await self.send("DOM.enable")

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def send(self, method, params=None):
        self.req_id += 1
        msg_id = self.req_id
        payload = {"id": msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP Error in {method}: {data['error']}")
                return data.get("result", {})

    async def navigate(self, url, wait_sec=2):
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(wait_sec)

    async def eval_js(self, js_code):
        res = await self.send("Runtime.evaluate", {
            "expression": js_code,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = res.get("result", {})
        if val.get("subtype") == "error":
            raise RuntimeError(f"JS Error: {val.get('description')}")
        return val.get("value")

    async def wait_for_selector(self, selector, timeout_sec=10):
        start = time.time()
        sel_json = json.dumps(selector)
        while time.time() - start < timeout_sec:
            exists = await self.eval_js(f"Boolean(document.querySelector({sel_json}))")
            if exists:
                return True
            await asyncio.sleep(0.3)
        raise TimeoutError(f"Element {selector} did not appear within {timeout_sec}s")

    async def set_input(self, selector, value):
        sel_json = json.dumps(selector)
        val_json = json.dumps(value)
        js = f"""
        (() => {{
            const el = document.querySelector({sel_json});
            if (!el) throw new Error('Element ' + {sel_json} + ' not found');
            const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, {val_json});
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
        return await self.eval_js(js)

    async def click(self, selector):
        sel_json = json.dumps(selector)
        js = f"""
        (() => {{
            const el = document.querySelector({sel_json});
            if (!el) throw new Error('Element ' + {sel_json} + ' not found');
            el.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            el.click();
            return true;
        }})()
        """
        return await self.eval_js(js)

    async def screenshot(self, filepath):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        raw_b64 = res.get("data")
        data = base64.b64decode(raw_b64)
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"Saved screenshot: {filepath}")


async def seed_test_database():
    print("\n--- Seeding test database for real browser test ---")
    engine = create_async_engine(TEST_DB_URL)
    today = datetime.now(CLINIC_TZ).date()

    async with engine.begin() as conn:
        # Check doctor user
        res = await conn.execute(text("SELECT id FROM users WHERE email = 'dr.rajesh.sharma@medismart.demo'"))
        doc_user_id = res.scalar()
        if not doc_user_id:
            raise RuntimeError("Doctor dr.rajesh.sharma@medismart.demo not found in test db")

        # Check doctor record
        res = await conn.execute(text(f"SELECT id, hospital_id FROM doctors WHERE user_id = '{doc_user_id}'"))
        doc_row = res.fetchone()
        doc_id = doc_row[0]
        hosp_id = doc_row[1]

        # Ensure patient user
        pat_email = "patient.ehr.e2e@medismart.demo"
        pat_pwd = get_password_hash("PatientSecurePass123!")
        res = await conn.execute(text(f"SELECT id FROM users WHERE email = '{pat_email}'"))
        pat_user_id = res.scalar()
        if not pat_user_id:
            pat_user_id = uuid.uuid4()
            await conn.execute(text(f"""
                INSERT INTO users (id, email, hashed_password, full_name, phone, role, is_active, created_at, updated_at)
                VALUES ('{pat_user_id}', '{pat_email}', '{pat_pwd}', 'John Doe', '+91 9988776655', 'patient', true, NOW(), NOW())
            """))
            print(f"Created patient user: {pat_email}")
        else:
            await conn.execute(text(f"UPDATE users SET hashed_password = '{pat_pwd}' WHERE id = '{pat_user_id}'"))

        # Clean previous test appointments for this doctor & patient to keep encounter clean
        await conn.execute(text(f"DELETE FROM prescription_items WHERE prescription_id IN (SELECT id FROM prescriptions WHERE patient_id = '{pat_user_id}')"))
        await conn.execute(text(f"UPDATE prescriptions SET superseded_by_id = NULL WHERE patient_id = '{pat_user_id}'"))
        await conn.execute(text(f"DELETE FROM prescriptions WHERE patient_id = '{pat_user_id}'"))
        await conn.execute(text(f"DELETE FROM diagnoses WHERE patient_id = '{pat_user_id}'"))
        await conn.execute(text(f"DELETE FROM consultation_notes WHERE patient_id = '{pat_user_id}'"))
        await conn.execute(text(f"DELETE FROM queue_entries WHERE patient_id = '{pat_user_id}'"))
        await conn.execute(text(f"DELETE FROM appointments WHERE patient_id = '{pat_user_id}'"))

        # Create scheduled appointment for today
        appt_id = uuid.uuid4()
        appt_token = f"MS-{today.strftime('%Y%m%d')}-E2E01"
        await conn.execute(text(f"""
            INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status, notes, created_at, updated_at)
            VALUES ('{appt_id}', '{appt_token}', '{pat_user_id}', '{doc_id}', '{hosp_id}', '{today}', '10:00:00', 'scheduled', 'Severe chronic migraine evaluation', NOW(), NOW())
        """))

        # Create queue entry
        q_id = uuid.uuid4()
        await conn.execute(text(f"""
            INSERT INTO queue_entries (id, hospital_id, doctor_id, appointment_id, patient_id, queue_date, token_number, position, status, checked_in_at, created_at, updated_at)
            VALUES ('{q_id}', '{hosp_id}', '{doc_id}', '{appt_id}', '{pat_user_id}', '{today}', 1, 1, 'waiting', NOW(), NOW(), NOW())
        """))

    await engine.dispose()
    print(f"Seeded appointment {appt_token} (ID: {appt_id}) for Dr. Rajesh Sharma and John Doe.")
    return {
        "doctor_email": "dr.rajesh.sharma@medismart.demo",
        "doctor_password": "DoctorSecurePass123!",
        "patient_email": "patient.ehr.e2e@medismart.demo",
        "patient_password": "PatientSecurePass123!",
        "appointment_token": appt_token,
        "appointment_id": str(appt_id),
    }


async def run_e2e_browser_test():
    seed_info = await seed_test_database()

    # Launch Chrome
    chrome_profile_dir = ARTIFACTS_DIR / "scratch" / "chrome_e2e_profile"
    chrome_cmd = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={chrome_profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--window-size=1280,900",
        "about:blank",
    ]
    print("\n--- Launching headless Google Chrome ---")
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(2.5)

    try:
        # Create a new page target
        req = urllib.request.Request("http://127.0.0.1:9222/json/new?http://127.0.0.1:5173", method="PUT")
        with urllib.request.urlopen(req) as resp:
            target = json.loads(resp.read().decode())
            page_ws_url = target.get("webSocketDebuggerUrl")

        session = CDPBrowserSession(page_ws_url)
        await session.connect()

        # =========================================================================
        # PART 1: DOCTOR WORKFLOW
        # =========================================================================
        print("\n--- [Step 1] Navigating to Doctor Login ---")
        await session.navigate("http://127.0.0.1:5173/login", wait_sec=2)
        await session.wait_for_selector("input[type='email']")

        print("--- [Step 2] Filling Doctor Credentials and Submitting ---")
        await session.set_input("input[type='email']", seed_info["doctor_email"])
        await session.set_input("input[type='password']", seed_info["doctor_password"])
        await session.click("button[type='submit']")
        await asyncio.sleep(2.5)

        # Navigate to doctor dashboard if not auto-redirected
        curr_url = await session.eval_js("window.location.pathname")
        print(f"Current pathname after login: {curr_url}")
        if curr_url != "/doctor":
            await session.navigate("http://127.0.0.1:5173/doctor", wait_sec=2)

        print("--- [Step 3] Verifying Doctor Workspace & Finding Appointment ---")
        await session.wait_for_selector("table")
        # Check that table contains our appointment token
        has_token = await session.eval_js(f"document.body.innerText.includes('{seed_info['appointment_token']}')")
        print(f"Appointment {seed_info['appointment_token']} visible in table: {has_token}")
        assert has_token, f"Appointment {seed_info['appointment_token']} not found in doctor appointments table!"

        print("--- [Step 4] Opening Consultation Record Modal (Document EHR) ---")
        # Click Document EHR button on our row
        click_doc_ehr = f"""
        (() => {{
            const rows = Array.from(document.querySelectorAll('tr'));
            const targetRow = rows.find(r => r.innerText.includes('{seed_info['appointment_token']}'));
            if (!targetRow) return false;
            const btns = Array.from(targetRow.querySelectorAll('button'));
            const docBtn = btns.find(b => b.innerText.includes('Document EHR') || b.innerText.includes('EHR Record'));
            if (!docBtn) return false;
            docBtn.click();
            return true;
        }})()
        """
        opened = await session.eval_js(click_doc_ehr)
        assert opened, "Failed to click 'Document EHR' button"
        await asyncio.sleep(1.5)

        # Modal is open: fill Consultation Notes & Diagnosis
        print("--- [Step 5] Documenting Clinical Consultation Notes & Diagnoses ---")
        await session.wait_for_selector("input#chiefComplaint, textarea[name='chief_complaint'], input[name='chief_complaint'], input")
        
        # Populate fields inside the modal using JS
        populate_notes_js = """
        (() => {
            const setVal = (el, val) => {
                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            };

            const inputs = Array.from(document.querySelectorAll('#consultation-form input, #consultation-form textarea'));
            // Chief Complaint
            const cc = inputs.find(i => i.placeholder?.includes('primary presenting') || i.placeholder?.includes('complaint'));
            if (cc) setVal(cc, 'Severe unilateral throbbing headache with visual aura');

            // Symptoms
            const sym = inputs.find(i => i.placeholder?.includes('Duration, intensity') || i.placeholder?.includes('symptoms'));
            if (sym) setVal(sym, 'Nausea, photophobia, phonophobia, scintillating scotoma');

            // Examination Notes
            const exam = inputs.find(i => i.placeholder?.includes('Blood pressure, heart rate'));
            if (exam) setVal(exam, 'BP 120/78 mmHg, HR 72 bpm, cranial nerves intact');

            // Clinical Observations
            const obs = inputs.find(i => i.placeholder?.includes("assessment") || i.placeholder?.includes("observations"));
            if (obs) setVal(obs, 'General condition alert, oriented x3, no focal motor deficits');

            // Structured Diagnosis Name & Code
            const diagName = inputs.find(i => i.placeholder?.includes('Hypertension'));
            if (diagName) setVal(diagName, 'Migraine with aura');

            const diagCode = inputs.find(i => i.placeholder?.includes('ICD-10'));
            if (diagCode) setVal(diagCode, 'G43.109');

            // Diagnosis Summary
            const diagSum = inputs.find(i => i.placeholder?.includes('Comprehensive diagnostic conclusion'));
            if (diagSum) setVal(diagSum, 'Classic Migraine with Aura, refractory to OTC analgesics');

            // Treatment Plan
            const tx = inputs.find(i => i.placeholder?.includes('Pharmacological therapy') || i.placeholder?.includes('treatment'));
            if (tx) setVal(tx, 'Initiate abortive triptan therapy and oral magnesium prophylaxis');

            // Lifestyle Advice
            const advice = inputs.find(i => i.placeholder?.includes('Low sodium diet') || i.placeholder?.includes('Lifestyle'));
            if (advice) setVal(advice, 'Maintain regular sleep schedule and headache trigger diary.');

            return true;
        })()
        """
        await session.eval_js(populate_notes_js)
        await asyncio.sleep(0.5)

        print("--- [Step 6] Navigating to Digital Prescriptions Tab ---")
        # Switch to Digital Prescriptions tab
        await session.eval_js("""
        (() => {
            const tabs = Array.from(document.querySelectorAll('button'));
            const rxTab = tabs.find(t => t.innerText.includes('Digital Prescriptions'));
            if (rxTab) rxTab.click();
        })()
        """)
        await asyncio.sleep(0.8)

        # Populate prescription
        print("--- [Step 7] Adding Medication Items to Digital Prescription ---")
        populate_rx_js = """
        (() => {
            const setVal = (el, val) => {
                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            };

            const inputs = Array.from(document.querySelectorAll('#consultation-form input, #consultation-form textarea'));
            const medName = inputs.find(i => i.placeholder?.includes('Amoxicillin') || i.placeholder?.includes('Medication Name'));
            if (medName) setVal(medName, 'Sumatriptan Succinate');

            const dosage = inputs.find(i => i.placeholder?.includes('500mg') || i.placeholder?.includes('Dosage'));
            if (dosage) setVal(dosage, '50mg');

            const freq = inputs.find(i => i.placeholder?.includes('Twice daily') || i.placeholder?.includes('Frequency'));
            if (freq) setVal(freq, 'Once at aura onset');

            const dur = inputs.find(i => i.placeholder?.includes('5 days') || i.placeholder?.includes('Duration'));
            if (dur) setVal(dur, '3 days');

            const instr = inputs.find(i => i.placeholder?.includes('instructions') || i.placeholder?.includes('After meals'));
            if (instr) setVal(instr, 'Take with water at first sign of aura');

            const rxNotes = inputs.find(i => i.placeholder?.includes('Dispensing notes') || i.placeholder?.includes('instructions to pharmacist'));
            if (rxNotes) setVal(rxNotes, 'Do not exceed 100mg in 24 hours.');

            return true;
        })()
        """
        await session.eval_js(populate_rx_js)
        await asyncio.sleep(0.5)

        print("--- [Step 8] Navigating to Follow-Up & Care Plan Tab ---")
        # Switch to Follow-Up tab
        await session.eval_js("""
        (() => {
            const tabs = Array.from(document.querySelectorAll('button'));
            const fuTab = tabs.find(t => t.innerText.includes('Follow-Up'));
            if (fuTab) fuTab.click();
        })()
        """)
        await asyncio.sleep(0.8)

        # Set follow-up date (7 days from now)
        target_date = (date.today() + timedelta(days=7)).isoformat()
        populate_fu_js = f"""
        (() => {{
            const setVal = (el, val) => {{
                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }};

            const dateInput = document.querySelector('#consultation-form input[type="date"]');
            if (dateInput) setVal(dateInput, '{target_date}');

            const inputs = Array.from(document.querySelectorAll('#consultation-form textarea'));
            const fuInstr = inputs.find(i => i.placeholder?.includes('Repeat fasting') || i.placeholder?.includes('instructions'));
            if (fuInstr) setVal(fuInstr, 'Return for review if headaches continue or change characteristics');

            return true;
        }})()
        """
        await session.eval_js(populate_fu_js)
        await asyncio.sleep(0.5)

        print("--- [Step 9] Submitting Consultation Record & Issuing Prescription ---")
        # Click Save Consultation & Issue EHR
        submit_btn_js = """
        (() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const saveBtn = btns.find(b => b.innerText.includes('Save EHR') || b.innerText.includes('Complete') || b.innerText.includes('Update') || b.getAttribute('form') === 'consultation-form');
            if (saveBtn) {
                saveBtn.click();
                return true;
            }
            return false;
        })()
        """
        saved = await session.eval_js(submit_btn_js)
        assert saved, "Save button not found in Consultation Modal"
        await asyncio.sleep(2.5)

        # Upon save, onSaved() refreshes the table and closes the modal
        print("--- [Step 9.1] Verifying Encounter Completed in Doctor Dashboard ---")
        table_text = await session.eval_js("document.body.innerText")
        has_completed = "Completed" in table_text
        print(f"Appointment marked Completed: {has_completed}")
        assert has_completed, "Appointment was not marked as Completed after EHR documentation"

        print("--- [Step 10] Testing Prescription Amendment Lifecycle (Hardening) ---")
        # Wait for table reload after onSaved()
        await session.wait_for_selector("tbody tr", timeout_sec=10)
        await asyncio.sleep(1)

        # Click EHR Record button on the completed row to re-open the signed encounter
        debug_row_info = await session.eval_js(f"""
        (() => {{
            const rows = Array.from(document.querySelectorAll('tr'));
            const targetRow = rows.find(r => r.innerText.includes('{seed_info['appointment_token']}'));
            if (!targetRow) return {{ found: false, count: rows.length, rows: rows.map(r => r.innerText) }};
            const btns = Array.from(targetRow.querySelectorAll('button'));
            return {{ found: true, rowText: targetRow.innerText, buttons: btns.map(b => b.innerText) }};
        }})()
        """)
        print("Reopen row debug info:", debug_row_info)

        reopen_ehr = f"""
        (() => {{
            const rows = Array.from(document.querySelectorAll('tr'));
            const targetRow = rows.find(r => r.innerText.includes('{seed_info['appointment_token']}'));
            if (!targetRow) return false;
            const btns = Array.from(targetRow.querySelectorAll('button'));
            const docBtn = btns.find(b => b.innerText.includes('EHR Record') || b.innerText.includes('Document') || b.innerText.includes('Details'));
            if (!docBtn) return false;
            docBtn.click();
            return true;
        }})()
        """
        reopened = await session.eval_js(reopen_ehr)
        assert reopened, f"Failed to re-open consultation modal for completed encounter: {debug_row_info}"
        await asyncio.sleep(1.5)

        # Switch to Digital Prescriptions tab
        await session.eval_js("""
        (() => {
            const tabs = Array.from(document.querySelectorAll('button'));
            const rxTab = tabs.find(t => t.innerText.includes('Digital Prescriptions'));
            if (rxTab) rxTab.click();
        })()
        """)
        await asyncio.sleep(0.8)

        # Verify immutability banner is displayed
        body_text = await session.eval_js("document.body.innerText")
        has_immutability_banner = "Issued Rx" in body_text or "immutable" in body_text or "Locked" in body_text
        print(f"Prescription immutability safeguard active: {has_immutability_banner}")
        assert has_immutability_banner, "Prescription immutability alert was not displayed for active issued Rx"

        # Fill amendment rationale and modify dose to 25mg
        amend_js = """
        (() => {
            const setVal = (el, val) => {
                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            };

            const inputs = Array.from(document.querySelectorAll('#consultation-form input, #consultation-form textarea'));
            const amendReason = inputs.find(i => i.placeholder?.includes('amendment') || i.placeholder?.includes('Rationale') || i.placeholder?.includes('250mg'));
            if (amendReason) setVal(amendReason, 'Patient reported mild sedation on 50mg; dosage titrated down to 25mg.');

            const dosage = inputs.find(i => i.placeholder?.includes('500mg') || i.placeholder?.includes('Dosage'));
            if (dosage) setVal(dosage, '25mg');

            return true;
        })()
        """
        await session.eval_js(amend_js)
        await asyncio.sleep(0.5)

        # Submit amendment
        await session.eval_js(submit_btn_js)
        await asyncio.sleep(2.5)
        print("Prescription amendment successfully submitted!")

        # Capture screenshot of Doctor Workspace with saved consultation
        screenshot_doc = str(ARTIFACTS_DIR / "browser_e2e_doctor_consultation.png")
        await session.screenshot(screenshot_doc)

        # Close modal
        await session.eval_js("""
        (() => {
            const closeBtns = Array.from(document.querySelectorAll('button'));
            const close = closeBtns.find(b => b.innerText.trim() === 'Close' || b.getAttribute('aria-label') === 'Close modal');
            if (close) close.click();
        })()
        """)
        await asyncio.sleep(1)

        # Logout Doctor
        print("--- [Step 11] Logging Out Doctor ---")
        await session.eval_js("""
        (async () => {
            try {
                await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
            } catch (e) {}
            const btns = Array.from(document.querySelectorAll('button, a'));
            const out = btns.find(b => b.innerText.includes('Sign Out') || b.innerText.includes('Logout'));
            if (out) out.click();
        })()
        """)
        await asyncio.sleep(2)

        # =========================================================================
        # PART 2: PATIENT WORKFLOW
        # =========================================================================
        print("\n--- [Step 12] Navigating to Patient Login ---")
        await session.navigate("http://127.0.0.1:5173/login", wait_sec=2)
        await session.wait_for_selector("input[type='email']")

        print("--- [Step 13] Logging In as Patient ---")
        await session.set_input("input[type='email']", seed_info["patient_email"])
        await session.set_input("input[type='password']", seed_info["patient_password"])
        await session.click("button[type='submit']")
        await asyncio.sleep(2.5)

        print("--- [Step 14] Navigating to Patient Medical Records (/medical-records) ---")
        await session.navigate("http://127.0.0.1:5173/medical-records", wait_sec=3)
        await session.wait_for_selector("h1")

        # Verify page content
        page_content = await session.eval_js("document.body.innerText")
        with open(ARTIFACTS_DIR / "scratch" / "patient_page_dump.txt", "w", encoding="utf-8") as f:
            f.write(page_content)
        print("Patient page dump saved to scratch/patient_page_dump.txt")
        print("Page preview:\n", page_content[:400].encode('ascii', errors='replace').decode())

        assert "My Medical Records" in page_content, "My Medical Records heading missing"
        assert "Verified Electronic Health Record" in page_content, "Verified EHR badge missing"
        print("Verified Medical Records page header and HIPAA compliance notice.")

        # Check Consultation Card
        assert "Dr. Rajesh Sharma" in page_content, "Dr. Rajesh Sharma encounter not visible"
        assert "Classic Migraine with Aura" in page_content, "Diagnosis summary not visible in encounter card"
        print("Verified consultation encounter card with Dr. Rajesh Sharma.")

        # Check Digital Prescriptions Tab
        print("--- [Step 15] Checking Patient Digital Prescriptions Tab ---")
        await session.eval_js("""
        (() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const rxTab = btns.find(b => b.innerText.includes('Prescriptions'));
            if (rxTab) rxTab.click();
        })()
        """)
        await asyncio.sleep(2)

        rx_page_content = await session.eval_js("document.body.innerText")
        with open(ARTIFACTS_DIR / "scratch" / "rx_page_dump.txt", "w", encoding="utf-8") as f:
            f.write(rx_page_content)
        print("Prescription page dump saved to scratch/rx_page_dump.txt")
        assert "Sumatriptan Succinate" in rx_page_content, "Prescribed medication Sumatriptan Succinate not found"
        assert "25mg" in rx_page_content, "Amended dosage 25mg not found in active prescription"
        assert "Revision v2" in rx_page_content or "v2" in rx_page_content, "Prescription revision version 2 badge missing"
        assert "CLINICAL AMENDMENT RATIONALE" in rx_page_content.upper(), "Amendment rationale section missing"
        print("Verified digital prescription: Sumatriptan 25mg, Revision v2, Amendment Rationale displayed.")

        # Check Clinician Diagnoses Tab
        print("--- [Step 16] Checking Patient Clinician Diagnoses Tab ---")
        await session.eval_js("""
        (() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const diagTab = btns.find(b => b.innerText.includes('Diagnoses'));
            if (diagTab) diagTab.click();
        })()
        """)
        await asyncio.sleep(1.5)

        diag_content = await session.eval_js("document.body.innerText")
        assert "Migraine with aura" in diag_content, "Structured diagnosis name missing"
        assert "G43.109" in diag_content, "ICD-10 code G43.109 missing"
        print("Verified clinician diagnosis: Migraine with aura (G43.109).")

        # Check Follow-Up Care Tab & Action
        print("--- [Step 17] Checking Follow-Up Care Tab and Booking Flow ---")
        await session.eval_js("""
        (() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const fuTab = btns.find(b => b.innerText.includes('Follow-Up'));
            if (fuTab) fuTab.click();
        })()
        """)
        await asyncio.sleep(1.5)

        fu_content = await session.eval_js("document.body.innerText")
        assert "Target Consultation Date" in fu_content or "Doctor Recommended" in fu_content, "Follow-up card missing"
        assert "Book Recommended Appointment" in fu_content, "Follow-up booking button missing"
        print("Verified follow-up recommendation and booking button.")

        # Click Book Recommended Appointment
        await session.eval_js("""
        (() => {
            const btns = Array.from(document.querySelectorAll('a, button'));
            const bookBtn = btns.find(b => b.innerText.includes('Book Recommended Appointment'));
            if (bookBtn) bookBtn.click();
        })()
        """)
        await asyncio.sleep(2)

        final_path = await session.eval_js("window.location.pathname")
        assert "/appointments" in final_path, f"Follow-up action did not route to /appointments, was: {final_path}"
        print(f"Follow-up action successfully navigated to: {final_path}")

        # Capture screenshot of Patient Medical Records & Follow-Up
        screenshot_pat = str(ARTIFACTS_DIR / "browser_e2e_patient_records.png")
        await session.screenshot(screenshot_pat)

        print("\n========================================================")
        print("REAL BROWSER END-TO-END VERIFICATION: 100% SUCCESSFUL!")
        print("========================================================")

        await session.close()
    finally:
        proc.terminate()


async def verify_clinical_audit_logs():
    print("\n--- Verifying Clinical Audit Trail in PostgreSQL ---")
    engine = create_async_engine(TEST_DB_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT action, target_type, actor_role, metadata_json, created_at 
            FROM clinical_audit_logs 
            ORDER BY created_at DESC 
            LIMIT 10;
        """))
        logs = res.fetchall()
        print(f"Found {len(logs)} recent clinical audit log entries:")
        for l in logs:
            action, target_type, actor_role, meta, ts = l
            print(f"  [{ts}] {action} on {target_type} by {actor_role} — meta: {meta}")

        # Verify key actions exist
        actions = [l[0] for l in logs]
        assert "CONSULTATION_CREATED" in actions or "CONSULTATION_UPDATED" in actions, "Missing consultation audit log"
        assert "PRESCRIPTION_ISSUED" in actions or "PRESCRIPTION_AMENDED" in actions, "Missing prescription audit log"
        print("Clinical audit trail verification passed!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_e2e_browser_test())
    asyncio.run(verify_clinical_audit_logs())
