"""Logique métier du bot, sans aucune dépendance à Telegram (testable hors réseau).

- lecture du CSV de mesures ;
- analyse de l'argument de /seuil ;
- détection des dépassements de seuil ;
- mise en forme des messages.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS = ("horodatage", "capteur", "valeur")


@dataclass(frozen=True)
class Measure:
    timestamp: datetime
    sensor: str
    value: float


@dataclass
class MeasureFile:
    measures: list[Measure]
    invalid_rows: list[int]   # numéros de ligne ignorés (valeur ou date illisible)


class ThresholdError(ValueError):
    """Argument de /seuil invalide ; le message est destiné à l'utilisateur."""


# --- Lecture du CSV ----------------------------------------------------------------

def _parse_number(text: str) -> float:
    """« 30.5 » ou « 30,5 » -> 30.5 ; lève ValueError si non numérique ou non fini."""
    value = float(text.strip().replace(",", "."))
    if not math.isfinite(value):
        raise ValueError(f"valeur non finie : {text}")
    return value


def read_measures(path: Path) -> MeasureFile:
    """Lit mesures.csv (horodatage, capteur, valeur). Les lignes invalides sont ignorées.

    Lève FileNotFoundError si le fichier n'existe pas, ValueError s'il manque une colonne.
    """
    measures, invalid = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} : colonne(s) manquante(s) : {', '.join(missing)}")
        for row in reader:
            try:
                ts = datetime.fromisoformat(row["horodatage"].strip())
                sensor = row["capteur"].strip()
                if not sensor:
                    raise ValueError("capteur vide")
                measures.append(Measure(ts, sensor, _parse_number(row["valeur"])))
            except (ValueError, AttributeError):  # AttributeError : cellule absente (None)
                invalid.append(reader.line_num)
    return MeasureFile(measures, invalid)


def latest_by_sensor(measures: list[Measure]) -> dict[str, Measure]:
    """Dernière mesure (la plus récente) de chaque capteur, triée par nom de capteur."""
    latest: dict[str, Measure] = {}
    for m in measures:
        if m.sensor not in latest or m.timestamp >= latest[m.sensor].timestamp:
            latest[m.sensor] = m
    return dict(sorted(latest.items()))


# --- Seuil -------------------------------------------------------------------------

def parse_threshold(args: list[str]) -> float:
    """Analyse les arguments de « /seuil <valeur> ».

    Accepte un seul nombre fini (point ou virgule décimale, négatif possible).
    """
    if not args:
        raise ThresholdError("Indiquez une valeur, par exemple : /seuil 30")
    if len(args) > 1:
        raise ThresholdError("Une seule valeur est attendue, par exemple : /seuil 30.5")
    try:
        return _parse_number(args[0])
    except ValueError:
        raise ThresholdError(f"« {args[0]} » n'est pas un nombre valide. Exemple : /seuil 30.5") from None


def exceeds(measure: Measure, threshold: float) -> bool:
    """Une mesure déclenche une alerte si elle est STRICTEMENT supérieure au seuil."""
    return measure.value > threshold


def new_alerts(measures: list[Measure], threshold: float,
               already_alerted: dict[str, datetime]) -> list[Measure]:
    """Mesures à signaler : dernière mesure de chaque capteur au-dessus du seuil,
    si elle n'a pas déjà fait l'objet d'une alerte.

    `already_alerted` (capteur -> horodatage déjà signalé) est mis à jour : une même
    mesure n'est donc envoyée qu'une fois, même si la tâche tourne toutes les minutes.
    """
    alerts = []
    for sensor, m in latest_by_sensor(measures).items():
        if exceeds(m, threshold) and already_alerted.get(sensor) != m.timestamp:
            alerts.append(m)
            already_alerted[sensor] = m.timestamp
    return alerts


# --- Messages ---------------------------------------------------------------------

def fmt_value(x: float) -> str:
    return f"{x:g}"


def format_alert(alerts: list[Measure], threshold: float) -> str:
    lines = [f"⚠️ Seuil {fmt_value(threshold)} dépassé :"]
    lines += [f"• {m.sensor} : {fmt_value(m.value)} ({m.timestamp:%d/%m/%Y %H:%M})" for m in alerts]
    return "\n".join(lines)


def format_status(mf: MeasureFile, threshold: float, interval_min: float, subscribed: bool) -> str:
    lines = [
        f"Seuil actuel : {fmt_value(threshold)}",
        f"Vérification toutes les {fmt_value(interval_min)} min",
        f"Alertes pour ce chat : {'activées' if subscribed else 'désactivées (envoyez /start)'}",
        f"Mesures lues : {len(mf.measures)}"
        + (f" ({len(mf.invalid_rows)} ligne(s) ignorée(s))" if mf.invalid_rows else ""),
    ]
    latest = latest_by_sensor(mf.measures)
    if latest:
        lines.append("")
        lines.append("Dernières valeurs :")
        for m in latest.values():
            flag = "🔴" if exceeds(m, threshold) else "🟢"
            lines.append(f"{flag} {m.sensor} : {fmt_value(m.value)} ({m.timestamp:%d/%m %H:%M})")
    return "\n".join(lines)
