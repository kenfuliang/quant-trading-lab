"""GitHub raw snapshots: receipted GETs of named URLs, GitHub hosts only.

Same receipt and manifest pattern as yahoo_snapshot: requests.json rows go reserved ->
received|failed (written atomically), raw files use exclusive create, the manifest is written
last, an existing snapshot id is refused and nothing is retried. A 403 or 429 stops the run;
the remaining requests are recorded as not_attempted (blocked).
"""
from __future__ import annotations

import errno
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from research.data.manifest import SCHEMA, ManifestError, check_dataset_id, sha256_file, write_manifest
from research.data.yahoo_snapshot import SnapshotIncomplete, _utc, _write_receipt

USER_AGENT = "research-snapshot/1"
HOSTS = ("api.github.com", "raw.githubusercontent.com")
TIMEOUT = 30
MAX_REQUESTS = 14
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")
RIGHTS = {"source": "github repo", "use": "private offline research",
          "redistribution": "not permitted unless licence allows; MIT text kept with snapshot",
          "ruling": "owner 2026-11-18 (membership sources)"}
BLOCKING = (403, 429)


def check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.port not in (None, 443) \
            or parsed.username or parsed.password:
        raise ValueError(f"URL not allowed (GitHub https hosts only: {', '.join(HOSTS)}): {url!r}")


def _first_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def fetch_urls(urls: dict, snapshot_id, root, opener=urllib.request.urlopen, now=None, *,
               expand=None, max_requests=MAX_REQUESTS, rights=None) -> Path:
    """Fetch each named URL once. ``expand(name, body) -> {name: url}`` may queue follow-up URLs
    (e.g. a file found in a contents listing); every URL is host-checked before its request and the
    total number of requests is capped at ``max_requests``."""
    root = Path(root)
    check_dataset_id(snapshot_id)
    queue = list(dict(urls).items())
    for name, url in queue:
        if not NAME_RE.fullmatch(name):
            raise ValueError(f"invalid name: {name!r}")
        check_url(url)
    if len({n for n, _ in queue}) != len(queue):
        raise ValueError("duplicate names")
    manifest_path = root / "manifests" / f"{snapshot_id}.json"
    if manifest_path.exists():
        raise FileExistsError(errno.EEXIST, "manifest already exists", str(manifest_path))
    folder = root / "raw" / "github" / snapshot_id
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(exist_ok=False)
    receipt = folder / "requests.json"
    rows, seen, stopped, index = [], {n for n, _ in queue}, False, 0
    while index < len(queue):
        name, url = queue[index]
        index += 1
        row = {"attempt": index, "name": name, "url": url, "utc": None, "status": "reserved",
               "http_status": None, "bytes": None, "sha256": None, "error": None, "rejected": None}
        rows.append(row)
        if stopped or index > max_requests:
            row.update(url=None if stopped else url, status="not_attempted",
                       error="run stopped after a 403/429 refusal" if stopped else f"request cap {max_requests}")
            continue
        try:
            check_url(url)
        except ValueError as error:  # an expanded URL on another host: recorded, never requested
            row.update(status="failed", error=f"ValueError: {error}")
            continue
        stamp = now if now is not None else datetime.now(timezone.utc)
        row["utc"] = _utc(stamp)
        _write_receipt(receipt, rows)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with opener(request, timeout=TIMEOUT) as response:
                row["http_status"] = getattr(response, "status", None)
                body = response.read()
            row["bytes"] = len(body)
            row["sha256"] = hashlib.sha256(body).hexdigest()
            if row["http_status"] != 200:
                raise ValueError(f"HTTP status {row['http_status']}")
            if name.endswith(".json"):
                try:
                    json.loads(body)
                except ValueError:
                    with open(folder / f"rejected-{name}", "xb") as handle:
                        handle.write(body)
                    row["rejected"] = f"raw/github/{snapshot_id}/rejected-{name}"
                    raise
        except Exception as error:  # recorded, never retried
            row["status"] = "failed"
            row["http_status"] = getattr(error, "code", row["http_status"])
            row["error"] = f"{type(error).__name__}: {error}"
            if row["http_status"] in BLOCKING:
                stopped = True
        else:
            with open(folder / name, "xb") as handle:
                handle.write(body)
            row["status"] = "received"
            if expand is not None:
                try:
                    for new_name, new_url in expand(name, body).items():
                        if new_name in seen or not NAME_RE.fullmatch(new_name):
                            raise ValueError(f"invalid or duplicate expanded name: {new_name!r}")
                        seen.add(new_name)
                        queue.append((new_name, new_url))
                except Exception as error:
                    row["error"] = f"expand failed: {type(error).__name__}: {error}"
        _write_receipt(receipt, rows)
    _write_receipt(receipt, rows)
    files = [{"path": f"raw/github/{snapshot_id}/{r['name']}", "sha256": r["sha256"]}
             for r in rows if r["status"] == "received"]
    for entry in files:
        if sha256_file(root / entry["path"]) != entry["sha256"]:
            raise ManifestError(f"{entry['path']}: sha256 mismatch after write")
    failed = [r["name"] for r in rows if r["status"] in ("failed", "not_attempted")]
    block = dict(rights or RIGHTS)
    block["licences"] = {r["name"]: {"sha256": r["sha256"], "first_line": _first_line(folder / r["name"])}
                         for r in rows if r["status"] == "received" and r["name"].endswith("LICENSE")}
    write_manifest(root, {
        "schema": SCHEMA, "dataset_id": snapshot_id, "kind": "raw-snapshot",
        "created_utc": _utc(now if now is not None else datetime.now(timezone.utc)),
        "source": f"GitHub ({', '.join(HOSTS)}); {len(rows)} requests receipted",
        "inputs": [], "recipe": None, "rights": block, "files": files,
        "notes": f"requests.json is the request receipt; failed or not attempted: {failed or 'none'}",
    })
    if failed:
        raise SnapshotIncomplete(f"failed or not attempted: {', '.join(failed)}", folder, failed)
    return folder


# --- the three membership sources -------------------------------------------------------------

FJA = "fja05680/sp500"
HANSHOF = "hanshof/sp500_constituents"
SEARCH_URL = "https://api.github.com/search/repositories?q=index-constitution"
_DATE_IN_NAME = re.compile(r"\((\d{2})-(\d{2})-(\d{4})\)")
_SP500_WORDS = re.compile(r"s&p\s*500|sp500|s&p500|sp-500", re.IGNORECASE)


def contents_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents"


def membership_sources() -> dict:
    return {"fja05680-contents.json": contents_url(FJA),
            "hanshof-contents.json": contents_url(HANSHOF),
            "index-constitution-search.json": SEARCH_URL}


def _files(body: bytes) -> list:
    items = json.loads(body)
    if not isinstance(items, list):
        raise ValueError("contents listing must be a list")
    return [i for i in items if isinstance(i, dict) and i.get("type") == "file" and i.get("download_url")]


def _fja_key(item) -> tuple:
    match = _DATE_IN_NAME.search(item["name"])
    return (match.group(3), match.group(1), match.group(2)) if match else ("", "", "")


def _pick_components(items):
    cands = [i for i in items if "historical components" in i["name"].lower() and i["name"].lower().endswith(".csv")]
    # "(Updated)" is the maintained file; the plain file stopped at 2019-01-11. Then latest dated, then name.
    return max(cands, key=lambda i: ("(updated)" in i["name"].lower(), _fja_key(i), i["name"])) if cands else None


def _pick_constituents(items):
    cands = [i for i in items if i["name"].lower().endswith((".csv", ".json"))
             and re.search(r"constituent|sp500|s&p", i["name"], re.IGNORECASE)]
    cands.sort(key=lambda i: (not i["name"].lower().endswith(".csv"), i["name"]))
    return cands[0] if cands else None


def _license(items):
    return next((i for i in items if i["name"].upper().startswith("LICENSE")), None)


def expand_membership(name: str, body: bytes) -> dict:
    """Follow-up URLs from a contents listing or the repository search."""
    out = {}
    if name == "fja05680-contents.json":
        items = _files(body)
        for key, pick in (("components.csv", _pick_components(items)), ("LICENSE", _license(items))):
            if pick:
                out[f"fja05680-{key}"] = pick["download_url"]
    elif name in ("hanshof-contents.json", "index-constitution-contents.json"):
        prefix = name.split("-contents")[0]
        items = _files(body)
        pick, lic = _pick_constituents(items), _license(items)
        if pick:
            out[f"{prefix}-constituents{Path(pick['name']).suffix.lower()}"] = pick["download_url"]
        if lic:
            out[f"{prefix}-LICENSE"] = lic["download_url"]
    elif name == "index-constitution-search.json":
        for item in json.loads(body).get("items", []):
            text = f"{item.get('name', '')} {item.get('description') or ''}"
            full = item.get("full_name", "")
            if _SP500_WORDS.search(text) and full.lower() not in (FJA, HANSHOF) \
                    and re.fullmatch(r"[\w.-]+/[\w.-]+", full):
                out["index-constitution-contents.json"] = contents_url(quote(full, safe="/"))
                break
    return out
