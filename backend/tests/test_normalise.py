import pytest

from app.services.normalise import normalise_fy


@pytest.mark.parametrize(
    "raw",
    [
        "2023-24",
        "2023–24",
        "2023/24",
        "2023-2024",
        "FY 2023-24",
        "fy2023-24",
        "F.Y. 2023-24",
        "FY24",
        "FY 24",
        "FY2024",
        " 2023 - 24 ",
        "२०२३-२४",
    ],
)
def test_all_forms_give_the_same_fy(raw):
    assert normalise_fy(raw) == "FY 2023-24"


def test_century_rollover():
    assert normalise_fy("1999-00") == "FY 1999-00"
    assert normalise_fy("2099-00") == "FY 2099-00"


def test_blank_is_none():
    assert normalise_fy(None) is None
    assert normalise_fy("  ") is None


@pytest.mark.parametrize("raw", ["2023-25", "2024-23", "2023", "last year", "FY 2023-24-25"])
def test_rejects_unclear_values(raw):
    with pytest.raises(ValueError):
        normalise_fy(raw)
