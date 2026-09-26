"""Depth-wise resources (#97): reading the inventory's Table II and adding up bands.

The lines are copied from the National Inventory for Coal and Lignite 2025 (pages 19-21),
including the PDF's quirks: names run into the coal type, a total wrapped onto its own line.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.core.db import get_db
from app.main import app
from app.services.depth_figures import bands_of, by_state, one_document_per_period
from worker.depth import Line, period_of, rows_from_lines, state_of

TABLE_II = """\
Table- II
STATE-WISE AND DEPTH-WISE RESOURCE OF INDIAN COAL
State Coal Type Depth Indicated Inferred Inferred Total
(m) (331) (332) (333) (333)
GONDWANA
JHARKHAND PRIME COKING 0-300 2.21 0.00 0.00 2.21
0-600 4509.27 87.28 0.00 4596.55
300-600 0.34 0.00 0.00 0.34
600-1200 620.83 223.48 0.00 844.31
0-1200 5132.65 310.76 0.00 5443.41
SEMI-COKING 0-300 223.34 95.33 0.55 319.22
300-600 0.00 376.22 52.90 429.12
0-600 223.34 471.55 53.45 748.34
BIHAR NON-COKING COAL 0-300 1265.47 1040.05 15.45 2320.97
300-600 819.16 3245.252 18.72 4083.132
600-1200 261.73 2685.113 2.49 2949.333
TOTAL FOR BIHAR 0-1200 2346.36 6970.42 36.66 9353.44
17
MADHYA PRADESHMEDIUM COKING 0-300 369.96 357.10 18.42 745.48
UTTAR PRADESH NON-COKING COAL 0-300 884.04 177.76 0.00 1061.80
ASSAM NON-COKING COAL 0-300 0.00 10.64 0.00 10.64
300-600 0.00 3.46 0.00 3.46
0-600 0.00 14.10 0.00 14.10
TERTIARY
ASSAM High Sulphur 0-300 278.93 26.57 0.50 2.52 308.52
300-600 185.85 16.15 0.00 0.00 202.00
0-600 464.78 42.72 0.50 2.52 510.52
ARUNACHAL PRADHigh Sulphur 0-300 61.49 22.74 0.00 6.00 90.23
GRAND TOTAL 0-300 144965.80 56430.12 8055.32 748.58 210199.82
0-600* 15229.16 153.93 29.63 0.00
15412.72
300-600 50213.44 67194.75 15040.60 0.00 132448.79
220412.34 149048.07 30506.46 748.58 400715.45
* only for Jharia coalfield for which break-up is not available
"""


def lines(text: str) -> list[Line]:
    return [Line(t.split(), [0, i, 1, i + 1], 19) for i, t in enumerate(text.splitlines())]


@pytest.fixture(scope="module")
def rows():
    return rows_from_lines(lines(TABLE_II))


def find(rows, state, coal_type, depth):
    (row,) = [r for r in rows if (r.state, r.coal_type, r.depth_range) == (state, coal_type, depth)]
    return row


def test_values_are_copied_as_printed(rows):
    r = find(rows, "Bihar", "NON-COKING COAL", "300-600")
    assert r.values_raw == ["819.16", "3245.252", "18.72", "4083.132"]
    assert (r.measured, r.indicated, r.inferred, r.total) == (819.16, 3245.252, 18.72, 4083.132)


def test_state_names_run_into_the_coal_type_or_cut_short(rows):
    assert find(rows, "Madhya Pradesh", "MEDIUM COKING", "0-300").total == 745.48
    assert find(rows, "Arunachal Pradesh", "HIGH SULPHUR", "0-300").total == 90.23
    assert state_of("ARUNACHAL PRAD") == "Arunachal Pradesh"
    assert state_of("PRAD") is None  # too short to be sure


def test_jharia_0_600_is_a_band_but_0_600_after_its_parts_is_a_total(rows):
    assert not find(rows, "Jharkhand", "PRIME COKING", "0-600").is_total
    assert find(rows, "Jharkhand", "PRIME COKING", "0-1200").is_total
    assert find(rows, "Jharkhand", "SEMI-COKING", "0-600").is_total
    assert find(rows, "Assam", "HIGH SULPHUR", "0-600").is_total


def test_mapping_column_is_part_of_inferred(rows):
    r = find(rows, "Assam", "HIGH SULPHUR", "0-300")
    assert r.inferred == pytest.approx(3.02) and r.total == 308.52


def test_wrapped_total_is_joined(rows):
    r = find(rows, None, None, "0-600")
    assert r.values_raw[-1] == "15412.72" and r.section is None


def test_sections_and_single_row_blocks(rows):
    assert find(rows, "Assam", "NON-COKING COAL", "0-300").section == "GONDWANA"
    assert find(rows, "Assam", "HIGH SULPHUR", "0-300").section == "TERTIARY"
    up = find(rows, "Uttar Pradesh", "NON-COKING COAL", "0-300")
    assert not up.is_total  # its only row is a band
    assert find(rows, "Bihar", None, "0-1200").is_total


def test_row_that_does_not_add_up_is_skipped():
    out = rows_from_lines(lines("ODISHA NON-COKING COAL 0-300 42182.89 11955.52 2115.19 99999.99"))
    assert out == []


def test_block_whose_bands_do_not_add_up_is_dropped():
    text = """\
ODISHA NON-COKING COAL 0-300 100.00 0.00 0.00 100.00
300-600 50.00 0.00 0.00 50.00
0-600 200.00 0.00 0.00 200.00
SIKKIM NON-COKING COAL 0-300 0.00 58.25 42.98 101.23
"""
    out = rows_from_lines(lines(text))
    assert [r.state for r in out] == ["Sikkim"]


def test_unknown_state_is_skipped_not_guessed():
    out = rows_from_lines(lines("ATLANTIS NON-COKING COAL 0-300 1.00 0.00 0.00 1.00"))
    assert out == []


def test_period_from_as_on():
    assert period_of("(As on 01.04.2025)") == "2025-04"
    assert period_of("no date") is None


# --- adding up ------------------------------------------------------------------------------


def test_state_uses_its_total_rows_or_its_only_coal_type(rows):
    states = by_state(rows)
    bihar = {b.depth_range: round(b.total, 3) for b in states["Bihar"]}
    assert bihar == {"0-300": 2320.97, "300-600": 4083.132, "600-1200": 2949.333}
    # Jharkhand here has no TOTAL FOR block, so its coal types are added, bands only
    jh = {b.depth_range: round(b.total, 2) for b in states["Jharkhand"]}
    assert jh == {"0-300": 321.43, "0-600": 4596.55, "300-600": 429.46, "600-1200": 844.31}


def test_assam_sections_are_added(rows):
    assam = {b.depth_range: round(b.total, 2) for b in by_state(rows)["Assam"]}
    assert assam == {"0-300": 319.16, "300-600": 205.46}


def test_all_india_is_the_grand_total_block(rows):
    india = bands_of([r for r in rows if r.state is None])
    assert [(b.depth_range, b.total) for b in india] == [
        ("0-300", 210199.82),
        ("0-600", 15412.72),
        ("300-600", 132448.79),
    ]


def test_one_copy_of_a_twice_uploaded_inventory():
    a, b = uuid.uuid4(), uuid.uuid4()
    rs = [SimpleNamespace(period="2025-04", document_id=a)] * 3 + [
        SimpleNamespace(period="2025-04", document_id=b)
    ] * 2
    assert {r.document_id for r in one_document_per_period(rs)} == {a}


# --- API ------------------------------------------------------------------------------------


class StubSession:
    """Answers the depth query with depth rows and the facts query with nothing."""

    def __init__(self, depth_rows):
        self.depth_rows = depth_rows

    def execute(self, stmt):
        is_depth = "depth_resources" in str(stmt)
        return SimpleNamespace(all=lambda: self.depth_rows if is_depth else [])


def stored(rows):
    doc = uuid.uuid4()
    out = []
    for r in rows:
        out.append(
            (SimpleNamespace(**r.__dict__, period="2025-04", document_id=doc), "Inventory 2025")
        )
    return out


def test_depth_view_of_a_state(client_as, rows):
    client = client_as(["viewer"], "CIL_HQ")
    app.dependency_overrides[get_db] = lambda: StubSession(stored(rows))
    body = client.get("/map/depth", params={"state": "BIHAR"}).json()
    assert body["state"] == "Bihar" and body["period"] == "2025-04"
    assert [b["depth_range"] for b in body["bands"]] == ["0-300", "300-600", "600-1200"]
    assert body["total"] == 9353.43
    src = body["bands"][1]["sources"][0]
    assert src["values_raw"] == ["819.16", "3245.252", "18.72", "4083.132"]
    assert src["document_title"] == "Inventory 2025" and src["page_no"] == 19


def test_depth_view_of_all_india_and_unknown_state(client_as, rows):
    client = client_as(["viewer"], "CIL_HQ")
    app.dependency_overrides[get_db] = lambda: StubSession(stored(rows))
    assert client.get("/map/depth").json()["state"] is None
    assert client.get("/map/depth").json()["total"] == 358061.33
    assert client.get("/map/depth", params={"state": "Atlantis"}).json()["bands"] == []


def test_map_shades_states_by_one_depth_band(client_as, rows):
    client = client_as(["viewer"], "CIL_HQ")
    app.dependency_overrides[get_db] = lambda: StubSession(stored(rows))
    res = client.get(
        "/map/figures",
        params={"metric": "coal_resource", "depth": "300-600", "category": "Inferred"},
    )
    body = res.json()
    assert res.status_code == 200 and body["depth"] == "300-600"
    assert body["depths"] == ["0-300", "0-600", "300-600", "600-1200"]
    items = {i["key"]: (i["value"], i["value_raw"]) for i in body["items"]}
    assert items["Bihar"] == (18.72, "18.72")
    # Assam's two printed cells are both shown; the mapping column joins the exploration one
    assert items["Assam"] == (0.0, "0.00 + 0.00 + 0.00")


def test_depth_is_ignored_for_production(client_as):
    client = client_as(["viewer"], "CIL_HQ")
    app.dependency_overrides[get_db] = lambda: StubSession([])
    body = client.get("/map/figures", params={"metric": "coal_production", "depth": "0-300"}).json()
    assert body["depth"] is None and body["depths"] == []


def test_unknown_depth_is_rejected(client_as):
    client = client_as(["viewer"], "CIL_HQ")
    assert client.get("/map/figures", params={"depth": "0-9999"}).status_code == 422
