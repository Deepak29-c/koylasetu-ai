"""Download the public coal documents we build and test on, and record each one.

    python scripts/fetch_sources.py              # key documents + parliamentary Q&A archive
    python scripts/fetch_sources.py --no-pq      # key documents only
    python scripts/fetch_sources.py --pq-pages 2 # only the first 2 archive pages

Files go to data/raw/ (git-ignored). Every file is recorded in data/sources.csv with its
official URL, publisher, download date and sha256, so every figure we show can be traced
back to a public government source. Safe to re-run: files already recorded are skipped.

This is a developer tool that needs the internet. The KoylaSetu app itself makes no
external calls (ALLOW_EXTERNAL_CALLS=false); downloaded files are uploaded into it.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SOURCES_CSV = ROOT / "data" / "sources.csv"
FIELDS = [
    "file", "title", "source_url", "publisher", "doc_type", "fy", "notes",
    "downloaded_on", "sha256", "size_bytes",
]  # fmt: skip

USER_AGENT = "Mozilla/5.0 (compatible; KoylaSetu-research/0.1; SIH 2026 PS 26023)"

# Key documents from the research phase (see the session handoff, section 4).
# fy is only filled where the document itself states it; notes say what the file is.
DOCUMENTS = [
    {
        "url": "https://www.cmpdi.co.in/sites/default/files/2024-12/National%20Coal%20Inventory%202024.pdf",
        "title": "National Coal Inventory 2024",
        "publisher": "CMPDI",
        "doc_type": "coal_inventory",
        "fy": "",
        "notes": "Coal resources by category (Measured / Indicated / Inferred)",
    },
    {
        "url": "https://www.cmpdi.co.in/sites/default/files/2025-10/National%20Inventory%20for%20Coal%20and%20lignite_2025.pdf",
        "title": "National Inventory for Coal and Lignite 2025",
        "publisher": "CMPDI",
        "doc_type": "coal_inventory",
        "fy": "",
        "notes": "Resources as on 1-4-2025, seams 0.9 m and above, depth up to 1200 m",
    },
    {
        "url": "https://coal.nic.in/sites/default/files/2025-01/msg-dec24.pdf",
        "title": "Monthly Coal Statistics - December 2024",
        "publisher": "Ministry of Coal",
        "doc_type": "monthly_stats",
        "fy": "FY 2024-25",
        "notes": "Production and dispatch by subsidiary, December 2024",
    },
    {
        "url": "https://coal.gov.in/sites/default/files/2025-02/chap12AnnualReport2025en2.pdf",
        "title": "Ministry of Coal Annual Report 2024-25 - Chapter 12",
        "publisher": "Ministry of Coal",
        "doc_type": "annual_report",
        "fy": "FY 2024-25",
        "notes": "One chapter of the annual report",
    },
    {
        "url": "https://coal.gov.in/sites/default/files/2022-09/1658897790_1681.pdf",
        "title": "Parliament question answer (example)",
        "publisher": "Ministry of Coal",
        "doc_type": "pq_answer",
        "fy": "",
        "notes": "Example PQ answer PDF from the Ministry archive",
    },
]

# Ministry of Coal parliamentary Q&A archive pages (paginated lists of PQ answer PDFs).
# Add other divisions here once their URLs are confirmed on coal.gov.in.
PQ_ARCHIVES = [
    {"url": "https://coal.gov.in/lok-sabha-pqa/cpd", "house": "Lok Sabha", "division": "cpd"},
]

_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_SUBJECT = re.compile(r'views-field-title">\s*(.*?)\s*</td>', re.S)
_PDF_LINK = re.compile(r'href="([^"]+\.pdf)"', re.I)
_PAGES = re.compile(r"(?:[?&]|&amp;)page=(\d+)")  # pager links are HTML-escaped


def fetch(url: str, retries: int = 3, timeout: int = 90) -> bytes:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"failed after {retries} tries: {last}")


def load_records() -> dict[str, dict]:
    if not SOURCES_CSV.exists():
        return {}
    with SOURCES_CSV.open(newline="", encoding="utf-8") as f:
        return {row["source_url"]: row for row in csv.DictReader(f) if row.get("source_url")}


def save_records(records: dict[str, dict]) -> None:
    rows = sorted(records.values(), key=lambda r: r["file"])
    tmp = SOURCES_CSV.with_suffix(".csv.part")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(SOURCES_CSV)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def download(item: dict, dest_dir: Path, records: dict[str, dict], delay: float) -> str:
    """Download one PDF and record it. Returns 'new', 'skipped' or 'failed: ...'."""
    url = item["url"]
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    dest = dest_dir / name
    known = records.get(url)
    if known and (ROOT / known["file"]).exists():
        return "skipped"

    try:
        data = fetch(url)
    except RuntimeError as e:
        return f"failed: {e}"
    finally:
        time.sleep(delay)  # be polite to government servers
    if not data.startswith(b"%PDF-"):
        return "failed: response is not a PDF"

    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    part.write_bytes(data)
    part.replace(dest)
    records[url] = {
        "file": dest.relative_to(ROOT).as_posix(),
        "title": item["title"],
        "source_url": url,
        "publisher": item["publisher"],
        "doc_type": item["doc_type"],
        "fy": item.get("fy", ""),
        "notes": item.get("notes", ""),
        "downloaded_on": date.today().isoformat(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": str(len(data)),
    }
    save_records(records)  # save after every file so an interrupted run keeps its progress
    return "new"


def archive_items(archive: dict, max_pages: int | None, delay: float) -> list[dict]:
    """Read the paginated archive list and return one item per PQ answer PDF."""
    items: list[dict] = []
    first = fetch(archive["url"]).decode("utf-8", "replace")
    last_page = max((int(p) for p in _PAGES.findall(first)), default=0)
    if max_pages is not None:
        last_page = min(last_page, max_pages - 1)

    for page in range(last_page + 1):
        if page == 0:
            text = first
        else:
            time.sleep(delay)
            text = fetch(f"{archive['url']}?page={page}").decode("utf-8", "replace")
        for row in _ROW.findall(text):
            link, subject = _PDF_LINK.search(row), _SUBJECT.search(row)
            if not link:
                continue
            title = ""
            if subject:
                title = html.unescape(re.sub(r"<[^>]+>", "", subject.group(1))).strip()
            items.append(
                {
                    "url": urllib.parse.urljoin(archive["url"], html.unescape(link.group(1))),
                    "title": title or "Parliament question answer",
                    "publisher": "Ministry of Coal",
                    "doc_type": "pq_answer",
                    "fy": "",
                    "notes": f"{archive['house']} PQ archive, division '{archive['division']}'",
                }
            )
        print(f"  archive page {page + 1}/{last_page + 1}: {len(items)} PDFs listed so far")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-pq", action="store_true", help="skip the parliamentary Q&A archive")
    parser.add_argument("--pq-pages", type=int, help="only read this many archive pages")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = parser.parse_args()

    records = load_records()
    counts = {"new": 0, "skipped": 0, "failed": 0}
    failures: list[str] = []

    def run(item: dict, dest_dir: Path) -> None:
        result = download(item, dest_dir, records, args.delay)
        key = result.split(":")[0]
        counts[key] += 1
        if key == "failed":
            failures.append(f"{item['url']} -> {result}")
        print(f"  [{result.split(':')[0]:7}] {item['title'][:70]}")

    print("Key documents:")
    for item in DOCUMENTS:
        run(item, RAW_DIR / slug(item["publisher"]))

    if not args.no_pq:
        for archive in PQ_ARCHIVES:
            print(f"\nParliament Q&A archive: {archive['url']}")
            try:
                items = archive_items(archive, args.pq_pages, args.delay)
            except RuntimeError as e:
                failures.append(f"{archive['url']} -> {e}")
                counts["failed"] += 1
                continue
            dest = RAW_DIR / "pq" / slug(archive["house"]) / archive["division"]
            for item in items:
                run(item, dest)

    new, skipped, failed = counts["new"], counts["skipped"], counts["failed"]
    print(f"\nDone: {new} new, {skipped} already had, {failed} failed.")
    print(f"Record: {SOURCES_CSV.relative_to(ROOT)} ({len(records)} files)")
    for f in failures:
        print("  FAILED", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
