"""Lecture des fichiers .log au format « AAAA-MM-JJ HH:MM:SS NIVEAU message »."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LEVELS = ("INFO", "WARNING", "ERROR")

# Horodatage (millisecondes facultatives), niveau, message.
LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})(?:[.,]\d+)?\s+"
    r"(?P<level>INFO|WARNING|WARN|ERROR)\s+(?P<msg>.*?)\s*$"
)


@dataclass
class ParsedLog:
    path: Path
    lines: list[str]          # toutes les lignes brutes (pour le diff)
    entries: pd.DataFrame     # colonnes : ligne, horodatage, niveau, message
    unparsed: int             # lignes non reconnues (ex. traces Python)


def read_lines(path: Path) -> list[str]:
    """Lit un fichier texte ligne à ligne, sans les fins de ligne."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def parse_log(path: Path) -> ParsedLog:
    lines = read_lines(Path(path))
    rows, unparsed = [], 0
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            unparsed += 1
            continue
        level = "WARNING" if m["level"] == "WARN" else m["level"]
        rows.append((lineno, m["ts"].replace("T", " "), level, m["msg"]))

    entries = pd.DataFrame(rows, columns=["ligne", "horodatage", "niveau", "message"])
    entries["horodatage"] = pd.to_datetime(entries["horodatage"], format="%Y-%m-%d %H:%M:%S")
    return ParsedLog(path=Path(path), lines=lines, entries=entries, unparsed=unparsed)
