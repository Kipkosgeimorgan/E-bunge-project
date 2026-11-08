#!/usr/bin/env python3
"""End-to-end smoke test for the local PHP app; uses an isolated temporary SQLite file."""
from __future__ import annotations

import base64
import http.cookiejar
import json
import sqlite3
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Browser:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def get(self, path: str) -> str:
        with self.opener.open(self.base + path) as response:
            assert response.status == 200, (path, response.status)
            return response.read().decode()

    def get_bytes(self, path: str) -> bytes:
        with self.opener.open(self.base + path) as response:
            assert response.status == 200, (path, response.status)
            return response.read()

    def post(self, path: str, data: dict[str, str], allow_error: bool = False) -> str:
        page = self.get(path)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page)
        assert csrf, f"No CSRF token in {path}"
        payload = {**data, "csrf": csrf.group(1)}
        request = urllib.request.Request(
            self.base + path,
            data=urllib.parse.urlencode(payload).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": self.base + path},
            method="POST",
        )
        with self.opener.open(request) as response:
            assert response.status == 200
            body = response.read().decode()
            if not allow_error and 'class="alert error"' in body:
                raise AssertionError("Unexpected application error: " + re.search(r'class="alert error"[^>]*>(.*?)</div>', body, re.S).group(1))
            return body

    def post_multipart(self, path: str, data: dict[str, str], file_field: str, filename: str, content: bytes, mime: str = "application/pdf") -> str:
        page = self.get(path)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page)
        assert csrf, f"No CSRF token in {path}"
        boundary = "----ebunge-workflow-check"
        fields = {**data, "csrf": csrf.group(1)}
        chunks = []
        for key, value in fields.items():
            chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode() + content + b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(self.base + path, data=b"".join(chunks), headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Referer": self.base + path}, method="POST")
        with self.opener.open(request) as response:
            body = response.read().decode()
            if 'class="alert error"' in body:
                raise AssertionError("Unexpected upload error")
            return body

    def register(self, email: str, username: str, role: str) -> str:
        html = self.get("/register")
        assert f'value="{role}"' in html
        return self.post("/register", {
            "action": "register", "email": email, "username": username, "role": role,
            "password": "CountyAssembly!2026", "password_confirm": "CountyAssembly!2026",
        })

    def login(self, login: str) -> str:
        return self.post("/signin", {"action": "login", "login": login, "password": "CountyAssembly!2026", "remember": "1"})


def main() -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="ebunge-check-") as data_dir:
        env = os.environ.copy()
        db_file = Path(data_dir) / "check.sqlite"
        env.update({"EBUNGE_COOKIE_SECURE": "0", "EBUNGE_DB_PATH": str(db_file), "EBUNGE_UPLOAD_DIR": str(Path(data_dir) / "uploads")})
        server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", str(ROOT / "public"), str(ROOT / "public" / "router.php")],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                try:
                    with urllib.request.urlopen(base + "/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("PHP server did not become ready")

            public = Browser(base)
            home = public.get("/")
            assert "Legislative work" in home and "Public portal" in home
            assert "value=\"admin\"" not in public.get("/register")
            manifest=json.loads(public.get("/manus-routes.json"))
            declared={route["path"] for route in manifest["routes"]}
            for route in ["/settings/branding","/voting/correct/:id","/committees/correct/:id","/sittings/correct/:id","/petitions/correct/:id"]:
                assert route in declared, f"Route manifest missing {route}"

            mca = Browser(base)
            assert "Account created" in mca.register("mca@example.test", "mca_test", "mca")
            assert "Good day" in mca.login("mca_test")
            mca_dashboard=mca.get("/dashboard")
            assert 'class="active" href="/dashboard"' in mca_dashboard
            for href in ["/motions","/sittings","/attendance","/voting","/committees","/petitions","/reports","/activity"]:
                assert f'href="{href}"' in mca_dashboard, f"MCA dashboard missing ordinary navigation route {href}"
            assert "Quick access" not in mca_dashboard and "Open a section" not in mca_dashboard
            assert "Submit a motion" in mca_dashboard and "Submit a petition" in mca_dashboard
            assert 'class="active" href="/attendance"' in mca.get("/attendance")
            assert "Activity tracker" in mca.get("/activity")
            assert "Submit for Hansard review" in mca.get("/petitions/new")
            motion_page = mca.post_multipart("/motions/new", {
                "action": "motion_create", "title": "Ward water access", "category": "Infrastructure",
                "body": "Request a review of water access in the ward.",
            }, "document", "water-access.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF")
            assert "Motion submitted" in motion_page
            assert b"%PDF-1.4" in mca.get("/download/motion/1").encode()

            hansard = Browser(base)
            hansard.register("hansard@example.test", "hansard_test", "hansard")
            hansard.login("hansard_test")
            hansard_dashboard=hansard.get("/dashboard")
            for href in ["/motions","/sittings","/attendance","/voting","/committees","/petitions","/reports","/activity"]:
                assert f'href="{href}"' in hansard_dashboard, f"Hansard dashboard missing ordinary navigation route {href}"
            assert "Quick access" not in hansard_dashboard and "Open a section" not in hansard_dashboard
            assert "Schedule a sitting" in hansard_dashboard and "Review petitions" in hansard_dashboard
            for path in ["/voting?form=new","/committees?form=new","/reports?form=new"]:
                assert "<details open" in hansard.get(path), f"Shortcut did not open form at {path}"
            assert "Submit for Speaker approval" in hansard.get("/sittings/new")
            assert "Ward water access" in hansard.get("/motions")
            hansard.post("/motions", {"action": "motion_forward", "id": "1", "note": "Checked"})

            speaker = Browser(base)
            speaker.register("speaker@example.test", "speaker_test", "speaker")
            speaker.login("speaker_test")
            speaker_dashboard=speaker.get("/dashboard")
            for href in ["/motions","/sittings","/attendance","/voting","/committees","/petitions","/reports","/activity","/settings/branding"]:
                assert f'href="{href}"' in speaker_dashboard, f"Speaker dashboard missing route {href}"
            assert "Incoming" in speaker_dashboard and "Waiting" in speaker_dashboard and "Recently completed" in speaker_dashboard
            assert "Quick access" not in speaker_dashboard and "Open a section" not in speaker_dashboard
            assert "Assembly identity" in speaker.get("/settings/branding")
            try:
                mca.get("/settings/branding")
                raise AssertionError("Only the Speaker may edit shared branding")
            except urllib.error.HTTPError as error:
                assert error.code == 403
            # A tiny valid PNG verifies persistent, MIME-checked branding uploads.
            png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
            speaker.post_multipart("/settings/branding",{"action":"branding_update","motto":"Kura yetu, sauti yetu."},"logo","assembly.png",png,"image/png")
            assert "Kura yetu, sauti yetu." in public.get("/")
            assert 'src="/branding/logo"' in speaker.get("/dashboard")
            assert speaker.get_bytes("/branding/logo")==png
            assert "Ward water access" in speaker.get("/motions")
            speaker.post("/motions", {"action": "motion_decision", "id": "1", "decision": "approved_for_tabling", "note": "Approved"})
            assert "Ward water access" in public.get("/public")
            assert "Approved For Tabling" in mca.get("/activity")
            mca.post("/motions/new", {"action": "motion_create", "title": "Correction workflow", "category": "Health", "body": "Initial wording."})
            hansard.post("/motions", {"action": "motion_return", "id": "2", "note": "Clarify the requested action."})
            assert "Correct and resubmit" in mca.get("/motions")
            mca.post("/motions/resubmit/2", {"action": "motion_resubmit", "id": "2", "title": "Correction workflow", "category": "Health", "body": "Clarified requested action."})
            hansard.post("/motions", {"action": "motion_forward", "id": "2", "note": "Correction checked"})
            speaker.post("/motions", {"action": "motion_decision", "id": "2", "decision": "returned_for_correction", "note": "Please clarify the impact."})
            assert "Please clarify the impact." in mca.get("/motions")
            returned_progress=hansard.get("/activity")
            assert 'class="progress-card is-returned"' in returned_progress
            assert "Correction requested" in returned_progress and "Please clarify the impact." in returned_progress
            mca.post("/motions/resubmit/2", {"action": "motion_resubmit", "id": "2", "title": "Correction workflow", "category": "Health", "body": "Final corrected wording."})
            hansard.post("/motions", {"action": "motion_forward", "id": "2", "note": "Final review"})
            speaker.post("/motions", {"action": "motion_decision", "id": "2", "decision": "approved_for_tabling", "note": "Approved after correction"})
            assert "Approved after correction" in speaker.get("/dashboard")

            official = Browser(base)
            official.register("official@example.test", "mca_official", "mca")
            official.login("mca_official")
            official.post("/motions/new", {"action": "motion_create", "title": "Other MCA private motion", "category": "Health", "body": "Separate account record."})
            outsider = Browser(base)
            outsider.register("outsider@example.test", "mca_outsider", "mca")
            outsider.login("mca_outsider")

            petition_page = public.get("/public")
            assert "Submit a petition" in petition_page
            assert "Petition received" in public.post("/public", {
                "action": "petition_create", "source": "public", "submitter_name": "Public Resident",
                "submitter_email": "resident@example.test", "ward": "North Ward", "title": "Safer crossing",
                "body": "Request a review of the crossing.", "consent": "yes",
            })
            consent_error = public.post("/public", {"action": "petition_create", "source": "public", "submitter_name": "Public Resident", "submitter_email": "resident@example.test", "title": "Missing consent", "body": "This should not be recorded."}, allow_error=True)
            assert "Confirm the petition submission" in consent_error
            hansard.post("/petitions", {"action": "petition_forward", "id": "1", "note": "Reviewed"})
            speaker.post("/petitions", {"action": "petition_decision", "id": "1", "decision": "approved", "note": "Approved for publication"})
            assert "Safer crossing" in public.get("/public")
            assert "Petition: Safer crossing" in hansard.get("/motions")
            assert "Petition: Safer crossing" in speaker.get("/motions")
            assert "Petition: Safer crossing" not in mca.get("/motions")

            mca.post("/petitions/new", {"action":"petition_create","source":"mca","submitter_name":"MCA Test","submitter_email":"mca@example.test","ward":"North Ward","title":"MCA petition correction","body":"Initial petition wording."})
            hansard.post("/petitions", {"action":"petition_forward","id":"2","note":"Reviewed"})
            speaker.post("/petitions", {"action":"petition_decision","id":"2","decision":"returned_for_correction","note":"Add the requested remedy."})
            assert "Add the requested remedy." in mca.get("/petitions")
            mca.post("/petitions/correct/2", {"action":"petition_resubmit","id":"2","title":"MCA petition correction","body":"Corrected remedy and affected ward.","ward":"North Ward"})
            hansard.post("/petitions", {"action":"petition_forward","id":"2","note":"Correction reviewed"})
            speaker.post("/petitions", {"action":"petition_decision","id":"2","decision":"approved","note":"Approved"})
            assert "Petition: MCA petition correction" in mca.get("/motions")

            sitting_date = (datetime.now(ZoneInfo("Africa/Nairobi")).date() + timedelta(days=2)).isoformat()
            hansard.post("/sittings/new", {
                "action": "sitting_create", "title": "Plenary sitting", "sitting_type": "Plenary",
                "sitting_date": sitting_date, "start_time": "10:00", "venue": "Assembly Chamber",
                "description": "Order paper review", "quorum_required": "4",
            })
            assert "Plenary sitting" not in public.get("/public")
            speaker.post("/sittings", {"action": "sitting_approve", "id": "1"})
            assert "Plenary sitting" in public.get("/public")
            assert 'href="/attendance?sitting=1"' in hansard.get("/attendance")
            assert 'name="attendance_status"' in hansard.get("/attendance?sitting=1")
            hansard.post("/attendance?sitting=1", {
                "action": "sitting_attendance", "sitting_id": "1", "user_id": "1",
                "attendance_status": "attended", "note": "Present",
            })
            hansard.post("/attendance", {"action": "attendance_submit", "id": "1"})
            attendance_queue=speaker.get("/dashboard")
            assert "Approve attendance" in attendance_queue and "Plenary sitting" in attendance_queue
            speaker.post("/attendance", {"action": "attendance_approve", "id": "1"})
            attendance_html = mca.get("/attendance")
            assert "Attended" in attendance_html
            assert "Approved" in hansard.get("/attendance?sitting=1")

            hansard.post("/sittings/new", {"action":"sitting_create","title":"Budget sitting","sitting_type":"Plenary","sitting_date":sitting_date,"start_time":"11:00","venue":"Assembly Chamber","description":"Budget review","quorum_required":"4"})
            speaker.post("/sittings", {"action":"sitting_return","id":"2","note":"Correct the start time."})
            assert "Correct the start time." in hansard.get("/sittings")
            hansard.post("/sittings/correct/2", {"action":"sitting_resubmit","id":"2","title":"Budget sitting","sitting_type":"Plenary","sitting_date":sitting_date,"start_time":"11:30","venue":"Assembly Chamber","description":"Budget review revised","quorum_required":"4"})
            speaker.post("/sittings", {"action":"sitting_approve","id":"2"})

            now = datetime.now(ZoneInfo("Africa/Nairobi"))
            hansard.post("/voting", {
                "action": "vote_subject_create", "title": "Water committee report", "details": "Record the position.",
                "opens_at": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"),
                "closes_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"), "sitting_id": "1",
            })
            assert "Water committee report" not in mca.get("/voting")
            speaker.post("/voting", {"action":"vote_subject_return","id":"1","note":"Clarify the question."})
            assert "Clarify the question." in hansard.get("/voting")
            hansard.post("/voting/correct/1", {"action":"vote_subject_resubmit","id":"1","title":"Water committee report","details":"Record the position clearly.","opens_at":(now-timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"),"closes_at":(now+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),"sitting_id":"1"})
            speaker.post("/voting", {"action": "vote_subject_open", "id": "1"})
            assert "Water committee report" in mca.get("/voting")
            assert "recorded" in mca.post("/voting", {"action": "cast_vote", "id": "1", "choice": "support"}).lower()
            duplicate = mca.post("/voting", {"action": "cast_vote", "id": "1", "choice": "oppose"}, allow_error=True)
            assert "already been recorded" in duplicate
            with sqlite3.connect(db_file) as conn:
                conn.execute("UPDATE vote_subjects SET closes_at=datetime('now','-1 minute') WHERE id=1")
            hansard.post("/voting", {"action": "vote_close", "id": "1"})
            hansard_results=hansard.get("/voting")
            assert "Hansard Result Review" in hansard_results and "Support" in hansard_results
            assert "Water committee report" not in mca.get("/voting")
            assert 'class="tally-grid"' not in speaker.get("/voting")
            hansard.post("/voting", {"action":"vote_results_submit","id":"1"})
            assert 'class="tally-grid"' in speaker.get("/voting")
            assert "Water committee report" not in mca.get("/voting")
            speaker.post("/voting", {"action":"vote_result_return","id":"1","note":"Confirm the tally source."})
            assert "Confirm the tally source." in hansard.get("/voting")
            hansard.post("/voting", {"action":"vote_result_resubmit","id":"1","note":"Tally checked against the recorded ballots."})
            speaker.post("/voting", {"action": "vote_result_approve", "id": "1"})
            mca_votes=mca.get("/voting")
            assert "Result approved" in mca_votes and "Support" in mca_votes and "Oppose" in mca_votes

            hansard.post("/committees", {"action": "committee_create", "name": "Water Services Committee", "description": "Review water service records.", "chair_id": "1", "member_ids[]": "1", "official_ids[]": "4"})
            speaker.post("/committees", {"action":"committee_return","id":"1","note":"Confirm the committee mandate."})
            assert "Confirm the committee mandate." in hansard.get("/committees")
            hansard.post("/committees/correct/1", {"action":"committee_resubmit","id":"1","name":"Water Services Committee","description":"Review water service records and report back.","chair_id":"1","member_ids[]":"1","official_ids[]":"4"})
            speaker.post("/committees", {"action": "committee_approve", "id": "1"})
            assert "Water Services Committee" in mca.get("/committees")
            assert "Committee official" in mca.get("/committees")
            assert "Water Services Committee" in official.get("/committees")
            assert "Water Services Committee" not in outsider.get("/committees")
            assert "Other MCA private motion" not in mca.get("/motions")
            hansard.post("/committees", {"action": "meeting_create", "committee_id": "1", "title": "Water review meeting", "meeting_date": sitting_date, "start_time": "11:00", "venue": "Committee Room", "agenda": "Review reports"})
            speaker.post("/committees", {"action": "meeting_approve", "id": "1"})
            assert "Water review meeting" in mca.get("/committees")

            speaker_queue=speaker.get("/dashboard")
            assert "Incoming" in speaker_queue and "Waiting" in speaker_queue and "Recently completed" in speaker_queue
            assert "Other MCA private motion" in speaker_queue
            progress=hansard.get("/activity")
            assert "Workflow progress" in progress and "progress-card" in progress
            assert '<ol class="progress-steps"' in progress and 'class="progress-step is-current"' in progress
            assert "Hansard review" in progress and "Approved for tabling" in progress

            hansard.post("/reports", {"action": "report_create", "title": "Motion register extract", "report_type": "motions"})
            pending_reports = speaker.get("/reports")
            assert "Reports awaiting Speaker approval" in pending_reports and "Motion register extract" in pending_reports
            speaker.post("/reports", {"action": "report_approve", "id": "1"})
            report_csv = mca.get("/download/report/1")
            assert "Ward water access" in report_csv and "Correction workflow" in report_csv
            assert "Other MCA private motion" not in report_csv
            for _ in range(6):
                reset_response = public.post("/forgot-password", {"action": "forgot", "email": "mca@example.test"})
                assert "If an account matches" in reset_response
            check = sqlite3.connect(db_file)
            assert check.execute("SELECT COUNT(*) FROM password_resets").fetchone()[0] == 5

            try:
                mca.get("/sittings/new")
                raise AssertionError("MCA must not open the Hansard-only sitting scheduler")
            except urllib.error.HTTPError as error:
                assert error.code == 403
            print("PASS: account and role controls, private attachments, returned motion/petition/sitting/voting/committee corrections, public and MCA petition-to-motion conversion, Support/Oppose ballots with Hansard review and Speaker result approval, Speaker queue and attendance approval, custom logo/motto, progress tracker, report scope, route manifest, reset throttling and access denial")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
