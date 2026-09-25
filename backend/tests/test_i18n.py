"""Every English label must have a Hindi one (#41).

The Hindi toggle is in the header on every screen and reads as a finished feature. It
drifted to 171 of 294 labels because nothing checked it: a new feature adds its English
strings, the Hindi is "later", and the screen quietly half-translates.

Lives in the backend suite because that is what CI runs; the frontend has no test
runner yet.
"""

import re
from pathlib import Path

import pytest

I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "i18n.tsx"
KEY = re.compile(r'^\s{2}(?:"([^"]+)"|([A-Za-z0-9_]+))\s*:', re.M)


def labels() -> tuple[list[str], list[str]]:
    source = I18N.read_text(encoding="utf-8")
    english = source[source.index("const en = {") : source.index("export type LabelKey")]
    hindi = source[source.index("const hi") : source.index("export type Lang")]
    read = lambda block: [m.group(1) or m.group(2) for m in KEY.finditer(block)]  # noqa: E731
    return read(english), read(hindi)


@pytest.fixture(scope="module")
def en_hi() -> tuple[list[str], list[str]]:
    return labels()


def test_the_file_still_parses(en_hi):
    """If this fails the regex has drifted from the file, not the translations."""
    english, hindi = en_hi
    assert len(english) > 100 and len(hindi) > 100


def test_every_english_label_has_a_hindi_one(en_hi):
    english, hindi = en_hi
    missing = [k for k in english if k not in set(hindi)]
    assert not missing, (
        f"{len(missing)} label(s) have no Hindi and will fall back to English: "
        f"{', '.join(missing[:15])}{'…' if len(missing) > 15 else ''}"
    )


def test_no_hindi_label_is_left_behind(en_hi):
    """A key renamed in English leaves a Hindi orphan that can never be shown."""
    english, hindi = en_hi
    orphans = [k for k in hindi if k not in set(english)]
    assert not orphans, f"Hindi labels with no English key: {', '.join(orphans)}"


def test_no_duplicate_keys(en_hi):
    for name, keys in zip(("en", "hi"), en_hi, strict=True):
        duplicates = {k for k in keys if keys.count(k) > 1}
        assert not duplicates, f"{name} defines these twice: {', '.join(sorted(duplicates))}"
