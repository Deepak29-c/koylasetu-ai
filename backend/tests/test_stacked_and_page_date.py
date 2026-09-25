"""Two layouts from National Coal & Lignite Inventory 2025, page 29 (values from that page):
a date printed once above the tables, and two states read by PyMuPDF as one row."""

from app.models.enums import Metric, PeriodType
from worker.extract import _split_stacked_rows, facts_from_table
from worker.parse import Block, _is_running_header, _with_page_date

TABLE_BOX = [50.0, 400.0, 550.0, 700.0]
TITLE = "Table-IVC: STATE-WISE BREAK-UP OF INDIAN COAL RESOURCE (Resource in million tonne)"
HEADING = Block(
    "Table IV RESOURCE OF DIFFERENT TYPES OF INDIAN COAL\n(As on 01.04.2025)\nTable-IVA",
    [50.0, 60.0, 550.0, 110.0],
)

ROWS = [
    ["State", "Measured\n(331)", "Indicated\n(332)", "Inferred\n(333)", "Resource"],
    ["ODISHA", "55009.74", "38780.51", "7185.53", "100975.78"],
    ["JHARKHAND\nCHHATTISGARH", "60290.47\n45462.69", "27121.64\n38340.18",
     "5841.95\n1460.35", "93254.06\n85263.22"],
    ["Total", "220412.34", "149048.07", "31255.04", "400715.45"],
]  # fmt: skip


# --- page date ------------------------------------------------------------------------------


def test_page_as_on_heading_is_added_to_an_undated_title():
    assert _with_page_date(TITLE, TABLE_BOX, [HEADING]) == f"{TITLE} (As on 01.04.2025)"


def test_title_with_its_own_period_is_left_alone():
    title = "Coal production during Dec'2024 (MT)"
    assert _with_page_date(title, TABLE_BOX, [HEADING]) == title


def test_two_different_dates_or_a_date_in_a_sentence_change_nothing():
    other = Block("(As on 01.04.2024)", [50.0, 120.0, 550.0, 130.0])
    assert _with_page_date(TITLE, TABLE_BOX, [HEADING, other]) == TITLE
    sentence = Block(
        "Resources as on 01.04.2025 increased over the previous year.", [50, 60, 550, 80]
    )
    assert _with_page_date(TITLE, TABLE_BOX, [sentence]) == TITLE


def test_repeated_as_on_heading_is_not_dropped_as_a_running_header():
    # The Coal Inventory prints "(As on 01.04.2025)" at the top of many pages
    running = {"as on", "annual report ministry of coal"}
    assert not _is_running_header(Block("(As on 01.04.2025)"), running)
    assert _is_running_header(Block("Annual Report 2024-25 Ministry of Coal"), running)


def test_a_date_below_the_table_is_not_used():
    below = Block("(As on 01.04.2025)", [50.0, 720.0, 550.0, 730.0])
    assert _with_page_date(TITLE, TABLE_BOX, [below]) == TITLE


# --- stacked rows -------------------------------------------------------------------------------


def test_stacked_row_is_split_and_keeps_its_cell_boxes():
    boxes = [[[c, r, c + 1, r + 1] for c in range(5)] for r in range(len(ROWS))]
    grid, out_boxes = _split_stacked_rows(ROWS, boxes)
    assert [r[0] for r in grid] == ["State", "ODISHA", "JHARKHAND", "CHHATTISGARH", "Total"]
    assert grid[3] == ["CHHATTISGARH", "45462.69", "38340.18", "1460.35", "85263.22"]
    assert out_boxes[2] == out_boxes[3] == boxes[2]  # both highlight the original cell
    assert out_boxes[4] == boxes[3]


def test_two_line_header_and_glued_sub_headers_are_not_split():
    rows = [
        ["Sl No", "Subs", "Monthly\nTarget", "Production during Dec"],
        ["1", "ECL", "5.43", "FY 25\n5.06"],  # sub-header glued into the first data row
    ]
    assert _split_stacked_rows(rows, None) == (rows, None)


def test_inventory_table_gives_every_state_with_its_date():
    title = _with_page_date(TITLE, TABLE_BOX, [HEADING])
    facts = {
        (f.state or f.subsidiary, f.category): f
        for f in facts_from_table(ROWS, title=title)
        if f.metric == Metric.COAL_RESOURCE
    }
    assert facts[("Jharkhand", "Measured")].value == 60290.47
    assert facts[("Chhattisgarh", None)].value == 85263.22
    india = facts[("INDIA", None)]
    assert (india.value, india.period_type, india.period) == (
        400715.45,
        PeriodType.MONTH,
        "2025-04",
    )
