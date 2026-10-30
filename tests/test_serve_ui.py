"""The ward server runs the real pipeline on hand-entered patients and enforces medsafe.workflow.

Each role enters only what ENTRIES allows; every alert decision passes workflow.check before it
reaches the append-only audit log; a hand-entered patient is checked by the same adapter and
run_pipeline as the pack's patients.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from medsafe.data.adapter import Dataset
from tools.serve_ui import Ward, WardError, archive_store, make_handler, split_lines

NURSE = {"user": "Staff nurse", "role": "nurse"}
LAB = {"user": "Lab technician", "role": "lab"}
PHARMACIST = {"user": "Pharmacist", "role": "pharmacist"}
PRESCRIBER = {"user": "Dr. Iyer", "role": "prescriber"}
FIELDS = {"age": "72", "sex": "F", "weight_kg": "61", "pregnant": "N", "diagnoses": "HTN; DM2",
          "allergies": "NKDA", "prescriber_count": "2"}


@pytest.fixture
def ward(mini: Dataset, tmp_path: Path) -> Ward:
    return Ward(mini, tmp_path / "ward")


def alerts(view: dict) -> list[tuple[str, tuple[str, ...], str]]:
    return [(a["issue_type"], tuple(a["drugs"]), a["severity"]) for a in view["result"]["medsafe"]["alerts"]]


def test_split_matches_the_pack_rule() -> None:
    assert split_lines("Brufen 400 tds; Tab Warf 2mg OD\n\n T. PCM 650 ;") == [
        "Brufen 400 tds", "Tab Warf 2mg OD", "T. PCM 650"]


def test_nurse_admits_and_the_real_pipeline_checks(ward: Ward) -> None:
    view = ward.admit(NURSE, FIELDS, "Brufen 400 tds; Tab Warf 2mg OD")
    assert view["id"] == "WARD-0001"
    assert ("interaction", ("ibuprofen", "warfarin"), "major") in alerts(view)
    assert [m["raw"] for m in view["result"]["medications"]] == ["Brufen 400 tds", "Tab Warf 2mg OD"]
    assert view["history"][0]["entry"] == "admit"


@pytest.mark.parametrize("actor", [PRESCRIBER, LAB, PHARMACIST])
def test_only_a_nurse_admits(ward: Ward, actor: dict) -> None:
    with pytest.raises(WardError) as error:
        ward.admit(actor, FIELDS, "Brufen 400 tds")
    assert error.value.status == HTTPStatus.FORBIDDEN


def test_lab_egfr_reruns_the_renal_tiers(ward: Ward) -> None:
    record = ward.admit(NURSE, FIELDS, "tab Glycomet 500 BD")
    assert not [a for a in alerts(record) if a[0] == "renal_dose"]       # no eGFR yet: no renal check
    low = ward.set_egfr(LAB, record["id"], "28")
    assert ("renal_dose", ("metformin",), "major") in alerts(low)
    assert low["result"]["compare"]["medsafe"]["egfr_tier"]["egfr_below"] == 30
    high = ward.set_egfr(LAB, record["id"], "80")
    assert not [a for a in alerts(high) if a[0] == "renal_dose"]
    with pytest.raises(WardError):
        ward.set_egfr(NURSE, record["id"], "40")
    with pytest.raises(WardError):
        ward.set_egfr(LAB, record["id"], "twenty")


def test_pharmacist_confirms_a_line_the_resolver_would_not_guess(ward: Ward) -> None:
    record = ward.admit(NURSE, FIELDS, "Tab Qxzrvy 400; Tab Warf 2mg OD")
    line = record["result"]["medications"][0]
    assert line["method"] == "abstained" and line["status"] == "unresolved"
    assert record["pharmacist_queue"]
    confirmed = ward.confirm_name(PHARMACIST, record["id"], 0, ["ibuprofen"])
    first = confirmed["result"]["medications"][0]
    assert first["raw"] == "Tab Qxzrvy 400"                             # shown as written
    assert first["generics"] == ["ibuprofen"] and first["confirmed"]["by"] == "Pharmacist"
    assert ("interaction", ("ibuprofen", "warfarin"), "major") in alerts(confirmed)
    with pytest.raises(WardError):
        ward.confirm_name(PHARMACIST, record["id"], 0, ["not-a-drug"])
    with pytest.raises(WardError):
        ward.confirm_name(PRESCRIBER, record["id"], 0, ["ibuprofen"])


def test_alert_decisions_pass_the_workflow_policy(ward: Ward) -> None:
    record = ward.admit(NURSE, FIELDS, "Brufen 400 tds; Tab Warf 2mg OD")
    key = "interaction:ibuprofen;warfarin"
    with pytest.raises(WardError, match="reason"):
        ward.record_event(PRESCRIBER, record["id"], key, "override")
    with pytest.raises(WardError):
        ward.record_event(NURSE, record["id"], key, "accept")
    with pytest.raises(WardError):
        ward.record_event(LAB, record["id"], key, "escalate")
    ward.record_event(PRESCRIBER, record["id"], key, "shown")
    view = ward.record_event(PRESCRIBER, record["id"], key, "override", "intended therapy")
    assert view["alert_states"][key]["reason"] == "intended therapy"
    assert ward.patterns()[0]["issue_type"] == "interaction" and ward.patterns()[0]["overridden"] == 1
    escalated = ward.record_event(NURSE, record["id"], key, "escalate")
    assert any("escalated" in why for why in escalated["pharmacist_queue"])


def test_records_and_audit_log_survive_a_restart(mini: Dataset, ward: Ward) -> None:
    record = ward.admit(NURSE, FIELDS, "Brufen 400 tds; Tab Warf 2mg OD")
    ward.record_event(PRESCRIBER, record["id"], "interaction:ibuprofen;warfarin", "accept")
    again = Ward(mini, ward.store)
    assert again.get(record["id"])["result"] == record["result"]
    assert [e["event"] for e in again.events(record["id"])] == ["accept"]


def test_same_entry_same_check(ward: Ward) -> None:
    one = ward.admit(NURSE, FIELDS, "Dolo 650 SOS; Crocin 500 sos; Tab Warf 2mg OD")
    two = ward.admit(NURSE, FIELDS, "Dolo 650 SOS; Crocin 500 sos; Tab Warf 2mg OD")
    strip = lambda v: {**v["result"], "id": None}  # noqa: E731
    assert strip(one) == strip(two)


def test_tasks_follow_the_record_round_the_ward(ward: Ward) -> None:
    def roles(view: dict) -> list[str]:
        return [t["role"] for t in view["tasks"]]

    record = ward.admit(NURSE, FIELDS, "Tab Qxzrvy 400; Brufen 400 tds; Tab Warf 2mg OD")
    assert roles(record) == ["lab", "pharmacist", "prescriber"]           # eGFR, a name, a decision
    record = ward.set_egfr(LAB, record["id"], "60")
    record = ward.confirm_name(PHARMACIST, record["id"], 0, ["paracetamol"])
    assert roles(record) == ["prescriber"]
    key = "interaction:ibuprofen;warfarin"
    record = ward.record_event(PRESCRIBER, record["id"], key, "defer")
    assert [t["kind"] for t in record["tasks"]] == ["answer"]              # handed to the pharmacist
    assert record["decisions"] == {"submitted": 1, "decided": 0, "handed": 1, "undecided": 0}
    record = ward.record_event(PHARMACIST, record["id"], key, "accept")
    assert record["tasks"] == [] and record["decisions"]["decided"] == 1
    assert ward.listing()[0]["tasks"] == []


def test_fresh_moves_the_old_ward_aside(ward: Ward) -> None:
    ward.admit(NURSE, FIELDS, "Brufen 400 tds")
    moved = archive_store(ward.store)
    assert moved is not None and (moved / "records.json").is_file()
    assert not (ward.store / "records.json").exists()
    assert archive_store(ward.store) is None


def test_http_round_trip(ward: Ward) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ward, None))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/api"
    try:
        body = json.dumps({"actor": NURSE, "fields": FIELDS, "medication_list": "Brufen 400 tds"}).encode()
        request = urllib.request.Request(f"{base}/records", body, {"Content-Type": "application/json"})
        created = json.loads(urllib.request.urlopen(request).read())
        listed = json.loads(urllib.request.urlopen(f"{base}/records").read())
        assert [r["id"] for r in listed] == [created["id"]]
        refused = urllib.request.Request(f"{base}/records", json.dumps(
            {"actor": PRESCRIBER, "fields": FIELDS, "medication_list": "Brufen"}).encode())
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(refused)
        assert error.value.code == 403
    finally:
        server.shutdown()


# ---- the ABHA sandbox --------------------------------------------------------------------------

@pytest.fixture
def abha_ward(mini: Dataset, tmp_path: Path) -> Ward:
    """A ward whose sandbox holds the mini fixtures' test patients."""
    from medsafe.data.adapter import load_dataset
    from conftest import MINI_DIR
    return Ward(mini, tmp_path / "ward", sandbox=load_dataset(MINI_DIR, "test").patients)


def test_abha_needs_the_patient_to_consent_before_anything_is_shared(abha_ward: Ward) -> None:
    address = abha_ward.abha_examples(n=99)[0] if abha_ward.abha_examples(n=99) else sorted(abha_ward.abha)[0]
    assert address.endswith("@sbx")
    consent = abha_ward.request_consent(NURSE, address)
    assert consent["status"] == "requested"
    with pytest.raises(WardError) as error:
        abha_ward.fetch(NURSE, consent["id"])
    assert error.value.status == HTTPStatus.CONFLICT
    abha_ward.approve_consent(consent["id"])
    bundle = abha_ward.fetch(NURSE, consent["id"])
    assert bundle["medication_list"] and "synthetic patient" in bundle["source"]
    record = abha_ward.admit(NURSE, bundle["fields"], bundle["medication_list"] + "\nT. PCM 650 SOS", consent["id"])
    assert record["source"] == {"kind": "abha_sandbox", "consent_id": consent["id"], "address": address}
    assert record["lines"][-1]["raw"] == "T. PCM 650 SOS"          # the nurse adds what ABHA did not have
    assert record["egfr"] is None                                    # eGFR stays the lab's entry


@pytest.mark.parametrize("actor", [LAB, PRESCRIBER, PHARMACIST])
def test_only_the_nurse_requests_abha_records(abha_ward: Ward, actor: dict) -> None:
    with pytest.raises(WardError) as error:
        abha_ward.request_consent(actor, sorted(abha_ward.abha)[0])
    assert error.value.status == HTTPStatus.FORBIDDEN


def test_unknown_address_and_expired_consent_are_refused(abha_ward: Ward) -> None:
    with pytest.raises(WardError) as error:
        abha_ward.request_consent(NURSE, "someone@abdm")
    assert error.value.status == HTTPStatus.NOT_FOUND
    consent = abha_ward.request_consent(NURSE, sorted(abha_ward.abha)[0])
    abha_ward.approve_consent(consent["id"])
    abha_ward.consents[consent["id"]]["expires_at"] = "2000-01-01T00:00:00+00:00"
    with pytest.raises(WardError, match="expired"):
        abha_ward.fetch(NURSE, consent["id"])
