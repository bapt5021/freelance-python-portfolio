"""Statistiques : erreurs par heure, messages d'erreur les plus fréquents."""

from __future__ import annotations

import re

import pandas as pd

# Les parties variables d'un message (IP, identifiants, nombres) sont remplacées
# par des marqueurs pour regrouper les erreurs « de même nature ».
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_HEX_ID = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{8,}\b")
_NUMBER = re.compile(r"\d+")


def message_template(message: str) -> str:
    """« Timeout base db-02 après 30 s » -> « Timeout base db-<N> après <N> s »."""
    message = _IP.sub("<IP>", message)
    message = _HEX_ID.sub("<ID>", message)
    return _NUMBER.sub("<N>", message)


def level_counts(entries: pd.DataFrame) -> dict[str, int]:
    counts = entries["niveau"].value_counts()
    return {lvl: int(counts.get(lvl, 0)) for lvl in ("INFO", "WARNING", "ERROR")}


def errors_per_hour(entries: pd.DataFrame) -> pd.Series:
    """Nombre d'erreurs par heure, heures sans erreur incluses (valeur 0).

    La plage couvre toutes les heures du fichier, de la première à la dernière ligne.
    """
    if entries.empty:
        return pd.Series(dtype=int, name="erreurs")
    hours = entries["horodatage"].dt.floor("h")
    full_range = pd.date_range(hours.min(), hours.max(), freq="h")
    counts = hours[entries["niveau"] == "ERROR"].value_counts()
    return counts.reindex(full_range, fill_value=0).astype(int).rename("erreurs")


def top_errors(entries: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Les n messages d'erreur (regroupés par modèle) les plus fréquents.

    Ordre : occurrences décroissantes, puis ordre alphabétique (résultat déterministe).
    """
    errors = entries.loc[entries["niveau"] == "ERROR", "message"].map(message_template)
    counts = errors.value_counts().rename_axis("message").reset_index(name="occurrences")
    counts = counts.sort_values(["occurrences", "message"], ascending=[False, True], kind="stable")
    return counts.head(n).reset_index(drop=True)
