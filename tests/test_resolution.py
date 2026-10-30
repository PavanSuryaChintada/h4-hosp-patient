"""Phase 2: brand, misspelling and abbreviation -> generic(s). Abstains rather than guessing.

Unit tests run on the mini fixtures. The named near-miss and stopped-medicine tests run on the
real pack and skip without it.
"""

from __future__ import annotations

import csv
import re

import pytest

from conftest import requires_pack
from eval.pack import data_dir, pack_present
from medsafe.data.adapter import Dataset
from medsafe.data.schema import CombinationBrand, Drug
from medsafe.pipeline import Settings, build_resolver
from medsafe.resolve.normalise import key, normalise
from medsafe.resolve.resolver import NameIndex, Resolver, similarity


@pytest.fixture(scope="module")
def resolver(mini: Dataset) -> Resolver:
    """A resolver over the mini fixtures' tables, at the shipped thresholds."""
    return build_resolver(mini, Settings())


def drug(generic: str, *brands: str) -> Drug:
    """A minimal drug-reference row."""
    return Drug(generic, None, None, None, None, brands, (), None, None, None, None, None, None)


# --- Stage 1: normalise -------------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "name"), [
    ("T. Glycomet-GP 1 1-0-1 after food", ("glycomet-gp",)),
    ("Tab Shylcal500 BID", ("shylcal",)),
    ("cap Razo - D", ("razo-d",)),
    ("x Brufen 400 PRN stopped", ("brufen",)),
    ("STOP syr Potklor 15 ml 10ml HS", ("potklor",)),
    ("Sach. CALCIROL 60000 IU weekly", ("calcirol",)),
    ("Meftal Forte tds", ("meftal", "forte")),
    ("T Zerodol P BID", ("zerodol", "p")),
    ("1-0-1", ()),
])
def test_normalise_extracts_the_name_words(raw: str, name: tuple[str, ...]) -> None:
    assert normalise(raw).name_words == name


def test_normalise_splits_explicit_combinations_and_keeps_head_words() -> None:
    assert normalise("T telmisartan + amlodipine od").parts == (("telmisartan",), ("amlodipine",))
    assert normalise("MDI budesonide/formoterol 400").parts == (("budesonide",), ("formoterol",))
    assert normalise("Inj huminsulin 30/70 12U").head_words[:2] == ("huminsulin", "30/70")
    assert key("Glycomet-GP") == key(" glycomet  gp ") == "glycometgp"


# --- Stages 2-7 ----------------------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "generics", "method"), [
    ("Dolo 650 SOS", ("paracetamol",), "exact"),
    ("tab paracetamol 650 if pain", ("paracetamol",), "exact"),
    ("Tab Glycomet-GP 1 1-0-1", ("glimepiride", "metformin"), "exact"),
    ("tab Glycomet 500 BD (stopped)", ("metformin",), "exact"),        # stopped still resolves
    ("T Telma AM 0-0-1", ("amlodipine", "telmisartan"), "exact"),      # spaced brand suffix
    ("T. PCM 650 SOS", ("paracetamol",), "synonym"),
    ("Vit D3 60000 IU weekly", ("cholecalciferol",), "synonym"),
    ("Physiotherapy", (), "non_drug"),
    ("Insulin pen needles", (), "non_drug"),
    ("T telmisartan + amlodipine OD", ("amlodipine", "telmisartan"), "parts"),
    ("monteleukast-LC HS", ("levocetirizine", "montelukast"), "parts"),
    ("Tab Glyciph 500", ("metformin",), "prefix"),
    ("Tab Glycomett 500 BD", ("metformin",), "fuzzy"),
    ("Amlopress-AT od", ("amlodipine", "atenolol"), "fuzzy"),
])
def test_each_stage(resolver: Resolver, raw: str, generics: tuple[str, ...], method: str) -> None:
    resolution = resolver.resolve(raw)
    assert (resolution.generics, resolution.method) == (generics, method), resolution


def test_longest_brand_wins(resolver: Resolver) -> None:
    assert resolver.resolve("Glycomet 500 BD").generics == ("metformin",)
    assert resolver.resolve("Glycomet-GP 2 BD").generics == ("glimepiride", "metformin")


def test_abstains_on_no_name_and_no_confident_match(resolver: Resolver) -> None:
    assert resolver.resolve("1-0-1").abstain_reason == "no_name"
    nothing = resolver.resolve("Tab Zzqxvk 10")
    assert (nothing.generics, nothing.method, nothing.abstain_reason) == (
        (), "abstained", "no_confident_match")
    assert nothing.verify_manually and nothing.resolved_generic is None


def test_a_tie_between_two_drugs_always_abstains() -> None:
    index = NameIndex.build({"alphazine": drug("alphazine", "Abcdel"),
                             "betazine": drug("betazine", "Abcdek")}, [])
    tie = Resolver(index, min_confidence=0.0, min_margin=0.0).resolve("Abcdex 10")
    assert (tie.method, tie.abstain_reason) == ("abstained", "ambiguous")


def test_hyphen_fragments_are_not_fuzzy_matched_into_a_fake_combination(resolver: Resolver) -> None:
    assert resolver.resolve("Dolo-Pan").method == "parts"             # exact parts are fine
    assert resolver.resolve("Dlo-Pnn").method != "parts"              # loose fragments are not


def test_transposed_letters_count_as_one_edit() -> None:
    assert similarity("telam", "telma") > similarity("telam", "telmaam")


def test_index_drops_unknown_synonyms_and_marks_clashes() -> None:
    index = NameIndex.build({"aspirin": drug("aspirin", "Ecosprin"),
                             "clopidogrel": drug("clopidogrel", "Ecosprin")}, [],
                            synonyms={"asa": ("aspirin",), "mtx": ("methotrexate",)})
    assert index.dropped_synonyms == ["mtx"]
    assert index.exact("ecosprin") is None and "ecosprin" in index.ambiguous
    assert index.exact("asa").generics == ("aspirin",)


def test_combination_brands_index_their_components() -> None:
    combo = CombinationBrand("Zerodol-P", None, "tab", None, ("aceclofenac", "paracetamol"))
    index = NameIndex.build({}, [combo])
    assert index.exact("zerodolp").generics == ("aceclofenac", "paracetamol")


def test_resolution_is_deterministic_and_order_independent(mini: Dataset) -> None:
    lines = [m.raw for p in mini.patients for m in p.medications]
    forward = [build_resolver(mini).resolve(raw) for raw in lines]
    backward = [build_resolver(mini).resolve(raw) for raw in reversed(lines)][::-1]
    assert forward == backward


def test_every_mini_line_resolves_correctly(mini: Dataset, resolver: Resolver) -> None:
    from conftest import MINI_DIR
    with (MINI_DIR / "train_resolution.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            want = tuple(sorted(filter(None, row["resolved_generic"].split(";"))))
            assert resolver.resolve(row["written_token"]).generics == want, row["written_token"]


# --- The real pack -------------------------------------------------------------------------------

def _pack_tokens(select) -> list:
    """Truth rows of train_resolution.csv chosen by ``select``, as pytest params (empty without
    the pack)."""
    if not pack_present():
        return []
    with (data_dir() / "train_resolution.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [pytest.param(r["written_token"], r["resolved_generic"],
                         id=f"{r['patient_id']}:{r['written_token']}") for r in select(rows)]


def _near_miss_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Every written line behind one of the 90 seeded near-misses."""
    with (data_dir() / "train_labels.csv").open(newline="", encoding="utf-8") as handle:
        issues = [r for r in csv.DictReader(handle) if r["near_miss"] == "1"]
    wanted = []
    for issue in issues:
        drugs = set(issue["drugs_involved"].split(";"))
        wanted += [r for r in rows if r["patient_id"] == issue["patient_id"]
                   and drugs & set(r["resolved_generic"].split(";")) and r not in wanted]
    return wanted


STOPPED = re.compile(r"\b(stop|stopped|discontinued|discont|held|hold|omit|not taking)\b|^\s*x\s",
                     re.IGNORECASE)


@pytest.fixture(scope="module")
def pack_resolver(pack_train: Dataset) -> Resolver:
    """A resolver over the real reference tables at the shipped thresholds."""
    return build_resolver(pack_train, Settings())


@requires_pack
@pytest.mark.parametrize(("written", "expected"), _pack_tokens(_near_miss_rows))
def test_near_miss_line_resolves(pack_resolver: Resolver, written: str, expected: str) -> None:
    """Every line behind the 90 seeded near-misses, named. A wrong drug here would be a
    confidently wrong alert on exactly the cases the brief cares most about."""
    assert pack_resolver.resolve(written).resolved_generic == (expected or None)


@requires_pack
@pytest.mark.parametrize(("written", "expected"),
                         _pack_tokens(lambda rows: [r for r in rows if STOPPED.search(r["written_token"])]))
def test_stopped_medicine_still_resolves_to_its_generic(pack_resolver: Resolver, written: str,
                                                       expected: str) -> None:
    """Resolution is not the regimen: a line marked stopped is still a medicine and the
    resolution file must name it. (Excluding it from the regimen is checked with Phase 3.)"""
    assert expected, "a stopped medicine carries its generic in the truth"
    assert pack_resolver.resolve(written).resolved_generic == expected


@requires_pack
def test_slice_resolves_with_no_false_resolution(train_slice: Dataset, pack_resolver: Resolver) -> None:
    """Day-to-day check on the first 100 training patients."""
    ids = {p.patient_id for p in train_slice.patients}
    with (data_dir() / "train_resolution.csv").open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["patient_id"] in ids]
    wrong = [r["written_token"] for r in rows
             if pack_resolver.resolve(r["written_token"]).resolved_generic != (r["resolved_generic"] or None)]
    false = [w for w in wrong if pack_resolver.resolve(w).generics]
    assert not false, false
    assert len(wrong) / len(rows) <= 0.01, wrong
