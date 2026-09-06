"""An acquisition inventory independent of successful document extraction.

The registered URL set defines explicit expectations. Historical profile entries
and acquired PDFs are retained with their own provenance, not relabelled as proof
that no other filing is missing. PDF identity is its bytes, not its mutable URL.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

KINDS = frozenset({"consolidated", "unconsolidated"})
_FILENAME = re.compile(
    r"^([A-Z0-9]+)_(\d{4}Q[1-4])_(consolidated|unconsolidated)\.pdf$", re.I)
_PERIOD = re.compile(r"^\d{4}Q[1-4]$")
_BANK = re.compile(r"^[A-Z0-9]+$")


@dataclass(frozen=True, order=True)
class Filing:
    bank_ticker: str
    period: str
    kind: str

    def __post_init__(self):
        if not _BANK.fullmatch(self.bank_ticker):
            raise ValueError(f"Invalid bank ticker: {self.bank_ticker!r}")
        if not _PERIOD.fullmatch(self.period) or self.kind not in KINDS:
            raise ValueError(f"Invalid filing period/basis: {self.period!r} {self.kind!r}")

    @property
    def filename(self) -> str:
        return f"{self.bank_ticker}_{self.period}_{self.kind}.pdf"

    def as_dict(self) -> dict:
        return asdict(self)


def filing_from_filename(path: str | Path) -> Filing | None:
    match = _FILENAME.fullmatch(str(path).replace("\\", "/").rsplit("/", 1)[-1])
    if match is None:
        return None
    bank, period, kind = match.groups()
    return Filing(bank.upper(), period.upper(), kind.lower())


def registered_sources(config: dict) -> dict[Filing, list[str]]:
    """Expand explicit configured sources; ZIP is transport, not reporting basis.

    Retain alternative URLs for the same filing instead of silently choosing one.
    A malformed configuration fails the inventory instead of shrinking its scope.
    """
    result: dict[Filing, list[str]] = {}
    for bank, metadata in config["banks"].items():
        for transport_kind, periods in metadata.get("urls", {}).items():
            kind = transport_kind.removesuffix("_zip")
            for period, url in periods.items():
                filing = Filing(bank.upper(), period.upper(), kind)
                if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                    raise ValueError(f"Invalid source URL for {filing.filename}")
                urls = result.setdefault(filing, [])
                if url not in urls:
                    urls.append(url)
    return result


def reconcile_inventory(registered: dict[Filing, list[str]],
                        acquired: Iterable[tuple[str, str, str, str]],
                        local_paths: Iterable[Path] = ()) -> dict:
    """List acquisition gaps and additional acquired filings without a success filter."""
    objects: dict[Filing, list[str]] = {}
    for bank, period, kind, key in acquired:
        filing = Filing(bank.upper(), period.upper(), kind.lower())
        if filing_from_filename(key) != filing:
            raise ValueError(f"Object key disagrees with filing identity: {key}")
        objects.setdefault(filing, []).append(key)
    local: dict[Filing, list[str]] = {}
    for path in local_paths:
        filing = filing_from_filename(path)
        if filing:
            local.setdefault(filing, []).append(str(path))
    rows = []
    for filing in sorted(registered.keys() | objects.keys() | local.keys()):
        rows.append({
            **filing.as_dict(), "registered": filing in registered,
            "source_urls": registered.get(filing, []),
            "object_keys": sorted(set(objects.get(filing, []))),
            "local_paths": sorted(local.get(filing, [])),
            "acquisition_status": "acquired" if filing in objects else "missing",
        })
    return {"registered_filings": len(registered), "acquired_filings": len(objects),
            "local_filings": len(local),
            "registered_missing": [f.as_dict() for f in sorted(registered.keys() - objects.keys())],
            "acquired_without_url": [f.as_dict() for f in sorted(objects.keys() - registered.keys())],
            "duplicate_object_bindings": [f.as_dict() for f, ks in sorted(objects.items())
                                          if len(set(ks)) > 1],
            "filings": rows}


def source_identity(path: str | Path, filing: Filing, *, source_url: str | None = None,
                    object_key: str | None = None) -> dict:
    """Hash the complete original input, preserving source identity across rebuilds."""
    path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError(f"Source is not a PDF: {path.name}")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {**filing.as_dict(), "pdf_sha256": digest.hexdigest(), "byte_count": size,
            "source_url": source_url, "object_key": object_key}


def preserve_original(source: Path, destination: Path, identity: dict) -> bool:
    """Keep the exact original beside its evidence, under its content identity."""
    filing = Filing(identity["bank_ticker"], identity["period"], identity["kind"])

    def matches(path):
        observed = source_identity(path, filing)
        return (observed["pdf_sha256"], observed["byte_count"]) == (
            identity["pdf_sha256"], identity["byte_count"])

    if destination.exists():
        if not matches(destination):
            raise ValueError("Archived original fails its content identity")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with source.open("rb") as original, tempfile.NamedTemporaryFile(
                dir=destination.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            shutil.copyfileobj(original, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if not matches(temporary):
            raise ValueError("Source changed before its original could be archived")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True
