"""Fonctions de normalisation unitaires : dates, montants, clients, produits.

Chaque fonction est pure (pas d'E/S) pour être facilement testée.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date, datetime
from difflib import get_close_matches
from pathlib import Path

CLIENT_INCONNU = "Client inconnu"
PRODUIT_INCONNU = "Non renseigné"

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def collapse_spaces(s: str) -> str:
    """Supprime les espaces en début/fin et réduit les espaces multiples."""
    return re.sub(r"\s+", " ", s).strip()


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


# --- Dates -------------------------------------------------------------------------

def parse_date(value) -> date | None:
    """Convertit une date en objet date, ou None si illisible.

    Formats acceptés : objet date/datetime (Excel), 2026-03-12, 12/03/2026,
    12-03-2026, 12.03.2026, « 12 mars 2026 », « 1er avril 2026 ».
    Les dates numériques sont lues au format français jour/mois/année.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if is_blank(value):
        return None
    s = strip_accents(collapse_spaces(str(value))).lower()
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if (m := re.fullmatch(r"(\d{1,2})(?:er)? ([a-z]+)\.? (\d{4})", s)) and m[2] in MOIS:
            return date(int(m[3]), MOIS[m[2]], int(m[1]))
    except ValueError:  # ex. 31/02/2026
        return None
    return None


# --- Montants ----------------------------------------------------------------------

def parse_amount(value) -> float | None:
    """Convertit un montant en float arrondi au centime, ou None si illisible.

    Gère : 1234.5 / "1234,50" / "1 234,50 €" / "1.234,50" / "1,234.50".
    Règle : si virgule ET point sont présents, le dernier est le séparateur décimal.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if value != value else round(float(value), 2)  # value != value <=> NaN
    s = re.sub(r"[\s  €]|eur", "", str(value), flags=re.IGNORECASE)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,50
        else:
            s = s.replace(",", "")                     # 1,234.50
    elif s.count(",") == 1:
        s = s.replace(",", ".")                        # 1234,50
    elif s.count(".") > 1:
        s = s.replace(".", "")                         # 1.234.567
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return round(float(s), 2)


def is_plain_number(value) -> bool:
    """Vrai si la valeur est déjà un nombre « propre » (aucune correction à journaliser)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value) is not None


# --- Clients et produits ----------------------------------------------------------

def client_key(name: str) -> str:
    """Clé de comparaison : sans accents, minuscules, « & » = « et », sans ponctuation."""
    s = strip_accents(name).casefold().replace("&", " et ")
    s = re.sub(r"[^\w\s]", " ", s)
    return collapse_spaces(s)


def load_reference(path: Path) -> list[str]:
    """Lit un référentiel CSV de clients (colonne « client »)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [row["client"].strip() for row in csv.DictReader(f) if row.get("client", "").strip()]


class ClientMatcher:
    """Ramène un nom de client saisi à la main vers son nom officiel.

    1. comparaison exacte sur la clé normalisée (casse, accents, espaces, &/et) ;
    2. sinon, rapprochement approximatif (difflib) pour les fautes de frappe ;
    3. sinon, le nom est seulement nettoyé (espaces) et conservé tel quel.
    Sans référentiel, seule l'étape 3 s'applique.
    """

    def __init__(self, reference: list[str] | None = None, cutoff: float = 0.85):
        self.by_key = {client_key(n): n for n in reference or []}
        self.cutoff = cutoff

    def match(self, raw) -> str:
        if is_blank(raw):
            return CLIENT_INCONNU
        cleaned = collapse_spaces(str(raw))
        key = client_key(cleaned)
        if key in self.by_key:
            return self.by_key[key]
        close = get_close_matches(key, list(self.by_key), n=1, cutoff=self.cutoff)
        return self.by_key[close[0]] if close else cleaned


def clean_product(raw) -> str:
    return PRODUIT_INCONNU if is_blank(raw) else collapse_spaces(str(raw))
