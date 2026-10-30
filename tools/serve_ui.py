"""The ward portal's local server: runs the real pipeline on patients entered by hand.

    python tools/serve_ui.py                   # http://127.0.0.1:8765 (serves ui/dist if built)
    python tools/serve_ui.py --fresh --open    # an empty ward, opened in the browser (demo.cmd)

Never on the scoring path: run.py and src/medsafe/ never import it. It exists so the portal can
check a patient a nurse types in without the browser holding any detection logic. Each check
writes the patient through the same adapter run.py uses and calls the same ``run_pipeline``,
then shapes the result with ``tools/export_ui.patient_view``, so a hand-entered patient and an
exported one are the same object on screen.

Who may enter what, and who may do what with an alert, is ``medsafe.workflow`` (ENTRIES,
PERMISSIONS, check). This server enforces it; the portal only hides what a role cannot do.
Records, consents and the append-only audit log live in ``data/ward/`` (ignored by git:
hand-entered patients never enter the repo).

The ABHA step is a sandbox, never connected to ABDM: a nurse requests consent for a sandbox
address (``<patient id>@sbx``), the patient's approval is a button, and the "records" are one
synthetic patient from the pack's test split. Every screen that shows it says so. There is no real authentication: the role comes from the demo
sign-in, as in the rest of the prototype.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import sys
import tempfile
import webbrowser
from dataclasses import asdict, replace
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "src", REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval.pack import data_dir  # noqa: E402
from medsafe import workflow  # noqa: E402
from medsafe.data.adapter import Dataset, load_dataset, load_patients  # noqa: E402
from medsafe.data.schema import Patient  # noqa: E402
from medsafe.pipeline import build_resolver, run_pipeline  # noqa: E402
from medsafe.rules.regimen import is_stopped  # noqa: E402
from tools.ehr_reference import EhrTables, check_patient  # noqa: E402
from tools.export_ui import patient_view  # noqa: E402

DEFAULT_PORT = 8765
DEFAULT_STORE = REPO_ROOT / "data" / "ward"
UI_DIST = REPO_ROOT / "ui" / "dist"
PATIENT_COLUMNS = ("patient_id", "age", "sex", "weight_kg", "egfr_ml_min_1_73m2", "pregnant",
                   "diagnoses", "allergies", "medication_list", "prescriber_count")
FIELDS = ("age", "sex", "weight_kg", "pregnant", "diagnoses", "allergies", "prescriber_count")
REVIEW_EVENTS = ("defer", "escalate")         # what puts an alert in the pharmacist's queue
CONSENT_LIFETIME = timedelta(hours=24)        # a sandbox consent lets the ward fetch for one day
ABHA_SUFFIX = "@sbx"                          # the ABDM sandbox suffix: no real ABHA address looks like this


class WardError(Exception):
    """A request the ward cannot carry out. ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def abha_address(patient_id: str) -> str:
    """The sandbox ABHA address of a synthetic patient: ``h4p-00gtpzt5@sbx``."""
    return f"{patient_id.lower()}{ABHA_SUFFIX}"


def now() -> str:
    """The current UTC time, ISO 8601 to the second."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_lines(text: str) -> list[str]:
    """A typed medication list as lines: split on ';' or line breaks, trimmed, empties dropped.

    The same split the pack defines for medication_list, so each line reaches the pipeline
    exactly as it would from the CSV.
    """
    return [line.strip() for line in re.split(r"[;\n]", text or "") if line.strip()]


class Ward:
    """Hand-entered patient records, checked by the real pipeline, with an append-only audit log.

    Args:
        dataset: The pack's reference tables (its patients are not used).
        store: Folder for ``records.json`` and ``audit.jsonl``.
    """

    def __init__(self, dataset: Dataset, store: Path, sandbox: Sequence[Patient] = ()):
        self.dataset = replace(dataset, patients=[])
        self.resolver = build_resolver(self.dataset)
        self.ehr_tables = EhrTables.from_dataset(self.dataset)
        self.generics = frozenset(dataset.drugs)
        self.store = store
        self.store.mkdir(parents=True, exist_ok=True)
        self.records_path = store / "records.json"
        self.audit_path = store / "audit.jsonl"
        self.consents_path = store / "consents.json"
        self.lock = Lock()
        self.records: dict[str, dict[str, Any]] = (
            json.loads(self.records_path.read_text(encoding="utf-8")) if self.records_path.is_file() else {})
        self.consents: dict[str, dict[str, Any]] = (
            json.loads(self.consents_path.read_text(encoding="utf-8")) if self.consents_path.is_file() else {})
        self.abha = {abha_address(p.patient_id): p for p in sandbox}

    # ---- reading ---------------------------------------------------------------------------

    def events(self, record_id: str | None = None) -> list[dict[str, Any]]:
        """Every audit event, oldest first; only one record's when ``record_id`` is given."""
        if not self.audit_path.is_file():
            return []
        rows = [json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines() if line]
        return [r for r in rows if record_id is None or r["patient_id"] == record_id]

    def alert_states(self, record_id: str) -> dict[str, dict[str, Any]]:
        """The latest decision on each alert of a record (``shown`` events do not count)."""
        states: dict[str, dict[str, Any]] = {}
        for event in self.events(record_id):
            if event["event"] != "shown":
                states[event["alert"]] = event
        return states

    def needs_pharmacist(self, record: dict[str, Any]) -> list[str]:
        """Why a record is in the pharmacist's queue, one reason per line; empty if it is not."""
        why = []
        unresolved = [m["raw"] for m in record["result"]["medications"] if m["status"] == "unresolved"]
        if unresolved:
            why.append(f"{len(unresolved)} line(s) to confirm by name")
        live = {a["key"] for a in record["result"]["medsafe"]["alerts"] or ()}
        waiting = [k for k, e in self.alert_states(record["id"]).items()
                   if k in live and e["event"] in REVIEW_EVENTS]
        if waiting:
            why.append(f"{len(waiting)} alert(s) deferred or escalated")
        if record.get("review_requested"):
            why.append("pharmacist review requested")
        return why

    def progress(self, record: dict[str, Any]) -> dict[str, Any]:
        """Where a record is on the ward, and what each role still has to do on it.

        Workflow bookkeeping only, read from the record and the audit log: an eGFR the lab has
        not entered, lines and handed-over alerts waiting on the pharmacist, and submitted alerts
        nobody has accepted or overridden. Nothing here reads what an alert says.
        """
        states = self.alert_states(record["id"])
        submitted = [a for a in record["result"]["medsafe"]["alerts"] or () if a["submitted"]]
        decided = [a for a in submitted if states.get(a["key"], {}).get("event") in ("accept", "override")]
        handed = [a for a in submitted if states.get(a["key"], {}).get("event") in REVIEW_EVENTS]
        undecided = [a for a in submitted if a["key"] not in states]
        unresolved = [m for m in record["result"]["medications"] if m["status"] == "unresolved"]
        tasks = []
        if not record.get("egfr"):
            tasks.append({"role": "lab", "kind": "egfr", "count": 1, "text": "Enter eGFR"})
        if unresolved:
            tasks.append({"role": "pharmacist", "kind": "confirm_name", "count": len(unresolved),
                          "text": f"Confirm {len(unresolved)} line(s) by name"})
        if handed:
            tasks.append({"role": "pharmacist", "kind": "answer", "count": len(handed),
                          "text": f"Answer {len(handed)} alert(s) handed over"})
        if record.get("review_requested"):
            tasks.append({"role": "pharmacist", "kind": "review", "count": 1, "text": "Review requested"})
        if undecided:
            tasks.append({"role": "prescriber", "kind": "decide", "count": len(undecided),
                          "text": f"Decide on {len(undecided)} alert(s)"})
        return {"tasks": tasks, "decisions": {"submitted": len(submitted), "decided": len(decided),
                                              "handed": len(handed), "undecided": len(undecided)}}

    def view(self, record: dict[str, Any]) -> dict[str, Any]:
        """A record as the portal reads it: the record, its alert decisions, its queue reasons and
        what each role still has to do on it."""
        return {**record, "alert_states": self.alert_states(record["id"]),
                "events": self.events(record["id"]), "pharmacist_queue": self.needs_pharmacist(record),
                **self.progress(record)}

    def listing(self) -> list[dict[str, Any]]:
        """Every record, newest first, as a summary row."""
        rows = []
        for record in sorted(self.records.values(), key=lambda r: r["created_at"], reverse=True):
            result = record["result"]
            rows.append({"id": record["id"], "created_at": record["created_at"],
                         "created_by": record["created_by"], "age": result["age"], "sex": result["sex"],
                         "egfr": result["egfr"], "lines": len(result["medications"]),
                         "actions": result["compare"]["medsafe"]["actions"],
                         "to_verify": result["compare"]["medsafe"]["to_verify"],
                         "top_severity": result["compare"]["medsafe"]["top_severity"],
                         "review_requested": bool(record.get("review_requested")),
                         "pharmacist_queue": self.needs_pharmacist(record), **self.progress(record)})
        return rows

    def get(self, record_id: str) -> dict[str, Any]:
        """One record, or WardError 404."""
        if record_id not in self.records:
            raise WardError(f"no record {record_id}", HTTPStatus.NOT_FOUND)
        return self.records[record_id]

    # ---- the check -------------------------------------------------------------------------

    def check(self, record: dict[str, Any]) -> dict[str, Any]:
        """Run the real pipeline on a record and return its patient view.

        A line a pharmacist confirmed is sent to the pipeline as the generic name(s) they chose,
        keeping a "stopped" marker if the original had one; the view shows the line as written,
        with the confirmation beside it.
        """
        lines = record["lines"]
        sent = []
        for line in lines:
            confirmed = line.get("confirmed")
            text = " + ".join(confirmed["generics"]) if confirmed else line["raw"]
            sent.append(f"{text} (stopped)" if confirmed and is_stopped(line["raw"]) else text)
        row = {"patient_id": record["id"], "medication_list": "\n".join(sent),
               "egfr_ml_min_1_73m2": record.get("egfr") or "",
               **{f: record["fields"].get(f) or "" for f in FIELDS}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patients_ward.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=PATIENT_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerow(row)
            patients = load_patients(path)
        if not patients:
            raise WardError("the record could not be read: is the medication list empty?")
        result = run_pipeline(replace(self.dataset, patients=patients), resolver=self.resolver)
        if getattr(result, "failures", None):
            raise WardError(f"the pipeline could not check this record: {result.failures}",
                            HTTPStatus.UNPROCESSABLE_ENTITY)
        view = patient_view(result.patients[0], check_patient(result.patients[0].patient, self.ehr_tables), None)
        for line, medication in zip(lines, view["medications"]):
            medication["raw"] = line["raw"]
            medication["confirmed"] = line.get("confirmed")
        return view

    def _save(self, record: dict[str, Any], actor: dict[str, str], entry: str, detail: str) -> dict[str, Any]:
        """Re-check a record, note who entered what, persist, and return its view."""
        record["result"] = self.check(record)
        record["history"].append({"at": now(), "user": actor["user"], "role": actor["role"],
                                  "entry": entry, "detail": detail})
        self.records[record["id"]] = record
        self.records_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=1), encoding="utf-8")
        return self.view(record)

    # ---- entries, each gated by medsafe.workflow.ENTRIES ------------------------------------

    def admit(self, actor: dict[str, str], fields: dict[str, Any], medication_list: str,
              consent_id: str | None = None) -> dict[str, Any]:
        """A nurse opens a record with the patient's details and the list as written. eGFR is
        the lab's entry, so a new record has none until a lab technician adds it.

        With ``consent_id``, the record notes that its list started from records fetched through
        the ABHA sandbox under that consent, and keeps any eGFR in them for the lab to confirm.
        """
        self._allow(actor, "admit")
        self._allow(actor, "medication_list")
        lines = split_lines(medication_list)
        if not lines:
            raise WardError("the medication list is empty")
        consent = self._usable_consent(consent_id) if consent_id else None
        with self.lock:
            record_id = f"WARD-{len(self.records) + 1:04d}"
            record = {"id": record_id, "created_at": now(), "created_by": actor["user"],
                      "fields": {f: str(fields.get(f) or "").strip() for f in FIELDS},
                      "egfr": None,
                      "lines": [{"raw": line, "confirmed": None} for line in lines],
                      "history": [], "review_requested": False,
                      "source": None if consent is None else {
                          "kind": "abha_sandbox", "consent_id": consent["id"], "address": consent["address"]},
                      "abha_egfr": None if consent is None else self._bundle(consent)["lab"]["egfr"]}
            detail = f"{len(lines)} line(s) entered" + (f", starting from ABHA consent {consent['id']}" if consent else "")
            return self._save(record, actor, "admit", detail)

    # ---- the ABHA sandbox: simulated, synthetic, never connected to ABDM --------------------

    def abha_examples(self, n: int = 6) -> list[str]:
        """Addresses to try in the sandbox: the first ``n`` synthetic patients with eight or more lines."""
        return [a for a, p in sorted(self.abha.items()) if len(p.medications) >= 8][:n]

    def request_consent(self, actor: dict[str, str], address: str, purpose: str = "care management") -> dict[str, Any]:
        """A nurse asks for a patient's records. Nothing is shared until the patient approves."""
        self._allow(actor, "abha_pull")
        address = address.strip().lower()
        if address not in self.abha:
            raise WardError(f"no ABHA address {address!r} in the sandbox", HTTPStatus.NOT_FOUND)
        with self.lock:
            consent = {"id": f"C-{len(self.consents) + 1:04d}", "address": address, "purpose": purpose,
                       "status": "requested", "requested_by": actor["user"], "role": actor["role"],
                       "requested_at": now(), "expires_at": (datetime.now(timezone.utc) + CONSENT_LIFETIME).isoformat(timespec="seconds"),
                       "approved_at": None, "fetched_at": None}
            self.consents[consent["id"]] = consent
            self._save_consents()
        return consent

    def approve_consent(self, consent_id: str) -> dict[str, Any]:
        """The patient approves on their phone. In the sandbox this is a button, not a phone."""
        with self.lock:
            consent = self._consent(consent_id)
            consent.update(status="granted", approved_at=now(), approved_by="patient (simulated in the sandbox)")
            self._save_consents()
        return consent

    def fetch(self, actor: dict[str, str], consent_id: str) -> dict[str, Any]:
        """The records a granted, unexpired consent allows, as one bundle for the admission form."""
        self._allow(actor, "abha_pull")
        consent = self._usable_consent(consent_id)
        with self.lock:
            consent["fetched_at"] = now()
            self._save_consents()
        return {"consent": consent, **self._bundle(consent)}

    def _bundle(self, consent: dict[str, Any]) -> dict[str, Any]:
        """What the sandbox hands over: details, the medication lines and eGFR of one synthetic patient."""
        p = self.abha[consent["address"]]
        return {"fields": {"age": "" if p.age is None else str(p.age), "sex": p.sex or "",
                           "weight_kg": "" if p.weight_kg is None else f"{p.weight_kg:g}",
                           "pregnant": "NA" if p.pregnant is None else "Y" if p.pregnant else "N",
                           "diagnoses": "; ".join(p.diagnoses), "allergies": p.allergies or "",
                           "prescriber_count": "" if p.prescriber_count is None else str(p.prescriber_count)},
                "medication_list": "\n".join(m.raw for m in p.medications),
                "lab": {"egfr": None if p.egfr is None else f"{p.egfr:g}"},
                "source": f"simulated ABHA sandbox: synthetic patient {p.patient_id} from the pack's test split"}

    def _consent(self, consent_id: str) -> dict[str, Any]:
        if consent_id not in self.consents:
            raise WardError(f"no consent {consent_id}", HTTPStatus.NOT_FOUND)
        return self.consents[consent_id]

    def _usable_consent(self, consent_id: str) -> dict[str, Any]:
        """A consent the patient granted and that has not expired, or WardError 409."""
        consent = self._consent(consent_id)
        if consent["status"] != "granted":
            raise WardError(f"consent {consent_id} is {consent['status']}: the patient has not approved it",
                            HTTPStatus.CONFLICT)
        if datetime.fromisoformat(consent["expires_at"]) < datetime.now(timezone.utc):
            raise WardError(f"consent {consent_id} expired at {consent['expires_at']}", HTTPStatus.CONFLICT)
        return consent

    def _save_consents(self) -> None:
        self.consents_path.write_text(json.dumps(self.consents, ensure_ascii=False, indent=1), encoding="utf-8")

    def set_medication_list(self, actor: dict[str, str], record_id: str, medication_list: str) -> dict[str, Any]:
        """A nurse replaces the list. Confirmations on lines that are still written the same stay."""
        self._allow(actor, "medication_list")
        lines = split_lines(medication_list)
        if not lines:
            raise WardError("the medication list is empty")
        with self.lock:
            record = self.get(record_id)
            kept = {line["raw"]: line.get("confirmed") for line in record["lines"]}
            record["lines"] = [{"raw": line, "confirmed": kept.get(line)} for line in lines]
            return self._save(record, actor, "medication_list", f"{len(lines)} line(s)")

    def set_egfr(self, actor: dict[str, str], record_id: str, egfr: str) -> dict[str, Any]:
        """A lab technician records eGFR; the renal checks re-run on it."""
        self._allow(actor, "egfr")
        value = str(egfr).strip()
        if not re.fullmatch(r"\d{1,3}(\.\d+)?", value):
            raise WardError("eGFR must be a number in mL/min/1.73m2")
        with self.lock:
            record = self.get(record_id)
            record["egfr"] = value
            return self._save(record, actor, "egfr", f"eGFR {value}")

    def confirm_name(self, actor: dict[str, str], record_id: str, line: int,
                     generics: list[str]) -> dict[str, Any]:
        """A pharmacist names the generic(s) on a line the resolver would not guess."""
        self._allow(actor, "confirm_name")
        unknown = [g for g in generics if g not in self.generics]
        if not generics or unknown:
            raise WardError(f"choose generics from the drug reference (unknown: {unknown or 'none given'})")
        with self.lock:
            record = self.get(record_id)
            if not 0 <= line < len(record["lines"]):
                raise WardError(f"no line {line} on record {record_id}")
            record["lines"][line]["confirmed"] = {"generics": sorted(set(generics)), "by": actor["user"],
                                                  "role": actor["role"], "at": now()}
            return self._save(record, actor, "confirm_name",
                              f"\"{record['lines'][line]['raw']}\" is {' + '.join(sorted(set(generics)))}")

    def request_review(self, actor: dict[str, str], record_id: str, note: str = "") -> dict[str, Any]:
        """Anyone on the ward may ask a pharmacist to review a record; a pharmacist closes it."""
        with self.lock:
            record = self.get(record_id)
            closing = actor["role"] == "pharmacist" and record.get("review_requested")
            record["review_requested"] = not closing
            record["history"].append({"at": now(), "user": actor["user"], "role": actor["role"],
                                      "entry": "review_closed" if closing else "review_requested",
                                      "detail": note.strip()})
            self.records_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=1), encoding="utf-8")
            return self.view(record)

    # ---- alert decisions, gated by medsafe.workflow.check ----------------------------------

    def record_event(self, actor: dict[str, str], record_id: str, alert: str, event: str,
                     reason: str | None = None, note: str | None = None) -> dict[str, Any]:
        """Append one alert event to the audit log, after medsafe.workflow.check allows it."""
        record = self.get(record_id)
        if alert not in {a["key"] for a in record["result"]["medsafe"]["alerts"] or ()}:
            raise WardError(f"record {record_id} has no alert {alert}")
        try:
            checked = workflow.check(workflow.AuditEvent(now(), actor["user"], actor["role"], record_id,
                                                         alert, event, reason or None, (note or "").strip() or None))
        except workflow.NotAllowed as error:
            raise WardError(str(error), HTTPStatus.FORBIDDEN) from error
        with self.lock, self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(checked), ensure_ascii=False) + "\n")
        return self.view(record)

    def patterns(self) -> list[dict[str, Any]]:
        """W9 override patterns over the whole audit log, from medsafe.workflow.override_patterns."""
        events = [workflow.AuditEvent(**e) for e in self.events()]
        return [{"issue_type": p.issue_type, "shown": p.shown, "overridden": p.overridden,
                 "rate": round(p.rate, 4), "reasons": [list(r) for r in p.reasons]}
                for p in workflow.override_patterns(events)]

    @staticmethod
    def _allow(actor: dict[str, str], entry: str) -> None:
        """WardError 403 unless the actor's role may make this entry."""
        try:
            workflow.check_entry(actor.get("role", ""), entry)
        except workflow.NotAllowed as error:
            raise WardError(str(error), HTTPStatus.FORBIDDEN) from error


def route(ward: Ward, method: str, path: str, body: dict[str, Any]) -> Any:
    """Dispatch one API request. Raises WardError for anything the ward refuses."""
    parts = [p for p in path.split("/") if p][1:]           # drop the leading "api"
    actor = body.get("actor") or {}
    if method == "POST" and not (actor.get("user") and actor.get("role")):
        raise WardError("every change needs an actor: {user, role}", HTTPStatus.UNAUTHORIZED)
    if method == "GET" and parts == ["health"]:
        return {"ok": True, "records": len(ward.records), "store": str(ward.store)}
    if method == "GET" and parts == ["records"]:
        return ward.listing()
    if method == "GET" and parts == ["abha", "examples"]:
        return ward.abha_examples()
    if method == "POST" and parts == ["abha", "consents"]:
        return ward.request_consent(actor, body.get("address", ""), body.get("purpose") or "care management")
    if method == "POST" and len(parts) == 4 and parts[:2] == ["abha", "consents"] and parts[3] == "approve":
        return ward.approve_consent(parts[2])
    if method == "POST" and len(parts) == 4 and parts[:2] == ["abha", "consents"] and parts[3] == "fetch":
        return ward.fetch(actor, parts[2])
    if method == "GET" and parts == ["patterns"]:
        return ward.patterns()
    if method == "GET" and len(parts) == 2 and parts[0] == "records":
        return ward.view(ward.get(parts[1]))
    if method == "POST" and parts == ["records"]:
        return ward.admit(actor, body.get("fields") or {}, body.get("medication_list", ""), body.get("consent_id"))
    if method == "POST" and len(parts) == 3 and parts[0] == "records":
        record_id, action = parts[1], parts[2]
        if action == "medication_list":
            return ward.set_medication_list(actor, record_id, body.get("medication_list", ""))
        if action == "egfr":
            return ward.set_egfr(actor, record_id, body.get("egfr", ""))
        if action == "confirm":
            return ward.confirm_name(actor, record_id, int(body.get("line", -1)), list(body.get("generics") or []))
        if action == "events":
            return ward.record_event(actor, record_id, body.get("alert", ""), body.get("event", ""),
                                     body.get("reason"), body.get("note"))
        if action == "review":
            return ward.request_review(actor, record_id, body.get("note", ""))
    raise WardError(f"no route {method} {path}", HTTPStatus.NOT_FOUND)


def make_handler(ward: Ward, ui_dist: Path | None) -> type[BaseHTTPRequestHandler]:
    """An HTTP handler bound to one ward: JSON under /api/, the built UI everywhere else."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _api(self, method: str) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if method == "POST" else {}
                payload, status = route(ward, method, urlparse(self.path).path, body), HTTPStatus.OK
            except WardError as error:
                payload, status = {"error": str(error)}, error.status
            except (ValueError, KeyError, TypeError) as error:
                payload, status = {"error": f"bad request: {error}"}, HTTPStatus.BAD_REQUEST
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")

        def _static(self) -> None:
            if ui_dist is None or not ui_dist.is_dir():
                self._send(404, b"UI not built: cd ui && npm run build", "text/plain")
                return
            path = (ui_dist / urlparse(self.path).path.lstrip("/")).resolve()
            if not path.is_file() or ui_dist.resolve() not in path.parents:
                path = ui_dist / "index.html"                    # single-page app: client routes
            self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            """Serve the API or the built UI."""
            self._api("GET") if self.path.startswith("/api/") else self._static()

        def do_POST(self) -> None:  # noqa: N802
            """Serve the API."""
            self._api("POST")

        def log_message(self, fmt: str, *args: Any) -> None:
            """Quiet: one line per API call, none for static files."""
            if self.path.startswith("/api/"):
                sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")

    return Handler


def archive_store(store: Path) -> Path | None:
    """Move a ward's records, consents and audit log into a dated folder under ``store/archive``,
    so a demo starts on an empty ward without deleting anything. Returns that folder, or None if
    there was nothing to move."""
    files = [store / name for name in ("records.json", "consents.json", "audit.jsonl") if (store / name).is_file()]
    if not files:
        return None
    target = store / "archive" / datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    for path in files:
        path.rename(target / path.name)
    return target


def main(argv: list[str] | None = None) -> int:
    """Load the reference tables once and serve the ward until interrupted."""
    parser = argparse.ArgumentParser(description="Local server for the ward portal.")
    parser.add_argument("--input", type=Path, default=data_dir(), help="the pack's data folder")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--fresh", action="store_true",
                        help="start on an empty ward: move existing records into store/archive/<time>")
    parser.add_argument("--open", action="store_true", help="open the portal in the default browser")
    args = parser.parse_args(argv)
    if args.fresh and (moved := archive_store(args.store)):
        print(f"previous ward records moved to {moved}")
    ward = Ward(load_dataset(args.input, "train"), args.store, sandbox=load_dataset(args.input, "test").patients)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(ward, UI_DIST))
    url = f"http://127.0.0.1:{args.port}"
    print(f"ward portal on {url}  (records in {args.store})")
    if not (UI_DIST / "index.html").is_file():
        print("the web app is not built: cd ui && npm ci && npm run build (or run demo.cmd)")
    if args.open:
        webbrowser.open(f"{url}/login")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
