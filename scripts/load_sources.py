"""Upload the public documents listed in data/sources.csv into a running KoylaSetu API.

    python scripts/fetch_sources.py                      # 1. download them into data/raw/
    python scripts/load_sources.py                       # 2. upload every one that exists
    python scripts/load_sources.py --doc-type coal_inventory --doc-type monthly_stats
    python scripts/load_sources.py --match shortage --limit 5 --dry-run

Each file goes through the normal upload endpoint (POST /documents), one file per request,
with its doc_type, financial year, title and official source_url from sources.csv, so every
figure the app shows can be traced back to the public original (issue #15). Documents are
marked public, which only CIL HQ / Ministry / Admin users may do, so the default login is the
demo admin; use --private to upload as any operator instead.

Safe to re-run: the API recognises a file it already has by its sha256 and reports it as a
duplicate instead of storing it twice. Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_CSV = ROOT / "data" / "sources.csv"
DOC_TYPES = {"annual_report", "coal_inventory", "monthly_stats", "pq_answer", "other"}
MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
RESULTS = ("created", "duplicate", "rejected", "missing file", "error")


# --- Pure parts (unit-tested without a network) ---------------------------------------------


def read_sources(path: Path = SOURCES_CSV) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("file")]


def select_rows(
    rows: Iterable[dict[str, str]],
    doc_types: Iterable[str] = (),
    match: str | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    """Keep rows of the given doc types whose title or file name contains `match`."""
    wanted = set(doc_types)
    needle = (match or "").lower()
    picked = [
        r
        for r in rows
        if (not wanted or r.get("doc_type") in wanted)
        and (not needle or needle in f"{r.get('title', '')} {r.get('file', '')}".lower())
    ]
    return picked[:limit] if limit is not None else picked


def form_fields(row: dict[str, str], public: bool = True) -> dict[str, str]:
    """The upload form for one sources.csv row (field names as in POST /documents)."""
    doc_type = (row.get("doc_type") or "").strip() or "other"
    if doc_type not in DOC_TYPES:
        doc_type = "other"
    fields = {
        "doc_type": doc_type,
        "language": (row.get("language") or "").strip() or "en",
        "is_public": "true" if public else "false",
    }
    for key in ("fy", "source_url", "title"):
        value = " ".join((row.get(key) or "").split())
        if value:
            fields[key] = value
    return fields


def multipart_body(
    fields: dict[str, str], filename: str, content: bytes, mime: str, boundary: str
) -> bytes:
    """Encode form fields plus one file under "files" as multipart/form-data."""
    lines: list[bytes] = []
    for name, value in fields.items():
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            value.encode("utf-8"),
        ]
    safe_name = filename.replace('"', "'").replace("\r", " ").replace("\n", " ")
    lines += [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="files"; filename="{safe_name}"'.encode(),
        f"Content-Type: {mime}".encode(),
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines)


def outcome(response: list[dict]) -> tuple[str, str]:
    """(result, detail) from the API's per-file upload result list."""
    if not response:
        return "error", "empty response"
    first = response[0]
    result = first.get("result", "error")
    doc = first.get("document") or {}
    detail = first.get("error") or ""
    if doc.get("id"):
        detail = f"id={doc['id']}" + (f" ({detail})" if detail else "")
    return (result if result in RESULTS else "error"), detail


def summary_line(counts: Counter) -> str:
    keys = list(RESULTS) + sorted(k for k in counts if k not in RESULTS)
    return ", ".join(f"{counts.get(k, 0)} {k}" for k in keys)


# --- Network parts --------------------------------------------------------------------------


class ApiUnreachable(Exception):
    """The API did not answer (down, restarting, connection reset or timed out)."""


class LoginFailed(Exception):
    """The API answered the login with something other than a token."""


class Api:
    def __init__(self, base_url: str, email: str, password: str, timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.email, self.password, self.timeout = email, password, timeout
        self.token = ""

    def _send(self, req: urllib.request.Request) -> tuple[int, object]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                return e.code, json.loads(body)
            except ValueError:
                return e.code, body.decode("utf-8", "replace")[:300]
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            reason = getattr(e, "reason", None) or e
            raise ApiUnreachable(f"cannot reach API at {self.base_url}: {reason}") from None

    def login(self) -> None:
        payload = json.dumps({"email": self.email, "password": self.password}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/auth/login",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        code, body = self._send(req)
        if code != 200 or not isinstance(body, dict) or "access_token" not in body:
            detail = body.get("detail") if isinstance(body, dict) else body
            raise LoginFailed(f"login as {self.email} failed (HTTP {code}): {detail}")
        self.token = body["access_token"]

    def upload(self, fields: dict[str, str], path: Path) -> tuple[int, object]:
        boundary = uuid.uuid4().hex
        mime = MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
        data = multipart_body(fields, path.name, path.read_bytes(), mime, boundary)
        for attempt in range(2):  # the access token is short-lived: log in again once on 401
            req = urllib.request.Request(
                f"{self.base_url}/documents",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                method="POST",
            )
            code, body = self._send(req)
            if code != 401 or attempt:
                return code, body
            self.login()
        return code, body


def load_rows(
    rows: list[dict[str, str]], api: Api, public: bool = True, dry_run: bool = False
) -> Counter:
    """Upload each row and print its result. A file the API could not take (unreachable,
    timed out, HTTP error) counts as `error` and the run goes on; if logging in again fails
    mid-run, the rest of the rows are left and the summary is still printed."""
    counts: Counter = Counter()
    for i, row in enumerate(rows):
        path = ROOT / row["file"]
        fields = form_fields(row, public=public)
        stop = False
        if not path.is_file():
            result, detail = "missing file", "run scripts/fetch_sources.py first"
        elif dry_run:
            result, detail = "dry run", json.dumps(fields)[:120]
        else:
            try:
                code, body = api.upload(fields, path)
            except ApiUnreachable as e:
                result, detail = "error", str(e)
            except LoginFailed as e:
                result, detail, stop = "error", f"{e}; stopping", True
            else:
                if code == 200 and isinstance(body, list):
                    result, detail = outcome(body)
                else:
                    detail = body.get("detail") if isinstance(body, dict) else body
                    result, detail = "error", f"HTTP {code}: {detail}"
        counts[result] += 1
        print(f"  [{result:12}] {row.get('title', '')[:60]:60} {detail}")
        if stop:
            counts["not tried"] += len(rows) - i - 1
            break
    return counts


def exit_code(counts: Counter) -> int:
    """1 if anything failed, or if nothing was loaded because the files were never fetched."""
    if counts["error"] or counts["rejected"] or counts["not tried"]:
        return 1
    if counts["missing file"] and not (counts["created"] or counts["duplicate"]):
        return 1
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Hindi titles on a cp1252 Windows console
        try:
            sys.stdout.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=os.environ.get("KOYLA_API", "http://localhost:8000"))
    parser.add_argument("--email", default=os.environ.get("KOYLA_EMAIL", "admin@koylasetu.local"))
    parser.add_argument(
        "--password",
        default=os.environ.get("KOYLA_PASSWORD") or os.environ.get("SEED_DEMO_PASSWORD"),
        help="prefer $KOYLA_PASSWORD (stays out of shell history); then $SEED_DEMO_PASSWORD, "
        "then the seed default",
    )
    parser.add_argument("--sources", type=Path, default=SOURCES_CSV)
    parser.add_argument(
        "--doc-type", action="append", default=[], choices=sorted(DOC_TYPES), help="repeatable"
    )
    parser.add_argument("--match", help="only rows whose title or file name contains this")
    parser.add_argument("--limit", type=int, help="upload at most this many rows")
    parser.add_argument("--private", action="store_true", help="do not mark documents public")
    parser.add_argument("--dry-run", action="store_true", help="list what would be uploaded")
    args = parser.parse_args()

    rows = select_rows(read_sources(args.sources), args.doc_type, args.match, args.limit)
    print(f"{len(rows)} documents selected from {args.sources.name}")
    api = Api(args.api, args.email, args.password or "change-me-too")
    if not args.dry_run:
        try:
            api.login()
        except (ApiUnreachable, LoginFailed) as e:
            print(str(e), file=sys.stderr)
            return 1

    counts = load_rows(rows, api, public=not args.private, dry_run=args.dry_run)
    print(f"\nDone: {summary_line(counts)}.")
    if counts["missing file"] and not (counts["created"] or counts["duplicate"]):
        print("Nothing was loaded: download the files first with scripts/fetch_sources.py.")
    return exit_code(counts)


if __name__ == "__main__":
    sys.exit(main())
