"""Lecture des fichiers, nettoyage ligne à ligne, dédoublonnage et journalisation."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterator

import pandas as pd
from openpyxl import load_workbook

from .normalize import (ClientMatcher, clean_product, client_key, is_blank,
                        is_plain_number, parse_amount, parse_date)

# Noms de colonnes acceptés (après normalisation) pour chaque champ.
COLUMN_ALIASES = {
    "date": {"date", "date vente", "date de vente"},
    "client": {"client", "nom client", "nom du client"},
    "produit": {"produit", "article"},
    "montant": {"montant", "montant eur", "montant (€)", "montant ttc", "prix"},
}

SUPPORTED_SUFFIXES = {".csv", ".xlsx"}


@dataclass
class Correction:
    fichier: str
    ligne: int
    champ: str
    avant: str
    apres: str


@dataclass
class CleaningResult:
    data: pd.DataFrame                      # une ligne par vente retenue
    corrections: list[Correction]
    stats: dict[str, int] = field(default_factory=dict)


# --- Lecture brute (en conservant les numéros de ligne d'origine) ------------------

def _map_header(header: list, fichier: str) -> dict[str, int]:
    """Associe chaque champ attendu à l'index de sa colonne."""
    mapping = {}
    for idx, col in enumerate(header):
        if col is None:
            continue
        norm = client_key(str(col).replace("_", " "))
        norm_raw = str(col).strip().lower().replace("_", " ")
        for champ, aliases in COLUMN_ALIASES.items():
            if norm in aliases or norm_raw in aliases:
                mapping.setdefault(champ, idx)
    manquants = set(COLUMN_ALIASES) - set(mapping)
    if manquants:
        raise ValueError(f"{fichier} : colonnes introuvables {sorted(manquants)} (en-tête : {header})")
    return mapping


def _read_text(path: Path) -> str:
    """Lit un CSV en UTF-8, ou en cp1252 (exports Excel Windows) en repli."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def read_rows(path: Path) -> Iterator[tuple[int, dict]]:
    """Renvoie (numéro de ligne dans le fichier, {champ: valeur brute})."""
    if path.suffix.lower() == ".xlsx":
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        mapping = _map_header(list(next(rows)), path.name)
        for line, row in enumerate(rows, start=2):
            yield line, {champ: (row[i] if i < len(row) else None) for champ, i in mapping.items()}
        wb.close()
    else:
        text = _read_text(path)
        first_line = text.split("\n", 1)[0]
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        mapping = _map_header(next(reader), path.name)
        for row in reader:
            yield reader.line_num, {champ: (row[i] if i < len(row) else None) for champ, i in mapping.items()}


# --- Nettoyage --------------------------------------------------------------------

def _fmt(value) -> str:
    """Représentation lisible d'une valeur brute pour le journal."""
    if value is None:
        return "(vide)"
    if isinstance(value, date):
        return value.isoformat()
    s = str(value)
    return f"« {s} »" if s != s.strip() or "  " in s else (s or "(vide)")


def list_input_files(input_dir: Path) -> list[Path]:
    files = sorted(p for p in Path(input_dir).iterdir()
                   if p.suffix.lower() in SUPPORTED_SUFFIXES and not p.name.startswith("~$"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier .csv ou .xlsx dans {input_dir}")
    return files


def clean_directory(input_dir: Path, client_reference: list[str] | None = None) -> CleaningResult:
    """Nettoie et fusionne tous les fichiers .csv/.xlsx d'un dossier."""
    matcher = ClientMatcher(client_reference)
    log: list[Correction] = []
    records: list[dict] = []
    first_seen: dict[tuple, tuple[str, int]] = {}  # clé de vente -> (fichier, ligne) de 1re occurrence
    stats = {"lignes_lues": 0, "lignes_vides": 0, "lignes_rejetees": 0, "doublons": 0}

    for path in list_input_files(input_dir):
        f = path.name
        for line, raw in read_rows(path):
            stats["lignes_lues"] += 1

            # Lignes entièrement vides : ignorées.
            if all(is_blank(v) for v in raw.values()):
                stats["lignes_vides"] += 1
                log.append(Correction(f, line, "(ligne)", "ligne vide", "supprimée"))
                continue

            d = parse_date(raw["date"])
            montant = parse_amount(raw["montant"])

            # Sans date ou montant exploitable, la vente ne peut pas être comptée.
            if d is None or montant is None:
                stats["lignes_rejetees"] += 1
                champ = "Date" if d is None else "Montant"
                avant = raw["date"] if d is None else raw["montant"]
                log.append(Correction(f, line, champ, _fmt(avant),
                                      f"ligne rejetée ({champ.lower()} manquant(e) ou illisible)"))
                continue

            client = matcher.match(raw["client"])
            produit = clean_product(raw["produit"])

            # Journal des corrections champ par champ.
            if not isinstance(raw["date"], date) and str(raw["date"]).strip() != d.isoformat():
                log.append(Correction(f, line, "Date", _fmt(raw["date"]), d.isoformat()))
            if not is_plain_number(raw["montant"]):
                log.append(Correction(f, line, "Montant", _fmt(raw["montant"]), f"{montant:.2f}"))
            if raw["client"] != client:
                log.append(Correction(f, line, "Client", _fmt(raw["client"]), client))
            if raw["produit"] != produit:
                log.append(Correction(f, line, "Produit", _fmt(raw["produit"]), produit))

            # Doublon = même date, client, produit et montant après normalisation.
            key = (d, client, produit, montant)
            if key in first_seen:
                stats["doublons"] += 1
                src_f, src_l = first_seen[key]
                log.append(Correction(f, line, "(ligne)", f"doublon de {src_f} ligne {src_l}", "supprimée"))
                continue
            first_seen[key] = (f, line)

            records.append({"Date": d, "Client": client, "Produit": produit, "Montant": montant,
                            "Fichier source": f, "Ligne source": line})

    data = pd.DataFrame(records, columns=["Date", "Client", "Produit", "Montant",
                                          "Fichier source", "Ligne source"])
    data = data.sort_values(["Date", "Client", "Produit"], kind="stable").reset_index(drop=True)
    stats["ventes_retenues"] = len(data)
    return CleaningResult(data=data, corrections=log, stats=stats)


def build_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Tableau croisé : montant des ventes par mois (lignes) et par produit (colonnes)."""
    tmp = data.assign(Mois=pd.to_datetime(data["Date"]).dt.strftime("%Y-%m"))
    pivot = pd.pivot_table(tmp, index="Mois", columns="Produit", values="Montant",
                           aggfunc="sum", fill_value=0, margins=True, margins_name="Total")
    pivot = pivot.round(2)
    counts = tmp.groupby("Mois").size()
    pivot["Nb ventes"] = list(counts) + [int(counts.sum())]
    pivot.columns.name = None
    return pivot
