"""Génère un fichier mesures.csv 100 % fictif (températures de locaux techniques).

    python generate_sample_data.py              # 24 h d'historique, une mesure / 15 min / capteur
    python generate_sample_data.py --ajouter    # ajoute une mesure « maintenant » par capteur
    python generate_sample_data.py --ajouter --pic salle-serveur-2   # ... avec un dépassement

L'option --ajouter sert au test manuel : le bot détecte la nouvelle mesure
au prochain passage de la tâche planifiée.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Capteur -> température normale (°C).
SENSORS = {"salle-serveur-1": 22.0, "salle-serveur-2": 24.0, "local-onduleur": 26.0}
END = datetime(2026, 11, 12, 8, 0)
SPIKE = (31.0, 36.0)


def _value(base: float, rng: random.Random, spike: bool = False) -> float:
    return round(rng.uniform(*SPIKE) if spike else base + rng.uniform(-2, 2.5), 1)


def generate(path: Path, seed: int = 3, hours: int = 24) -> list[tuple[str, str, float]]:
    """Historique sur `hours` heures. Quelques pics, et la dernière mesure de
    salle-serveur-2 au-dessus de 30 pour qu'une alerte parte dès le 1er passage."""
    rng = random.Random(seed)
    rows = []
    start = END - timedelta(hours=hours)
    steps = hours * 4
    for i in range(steps + 1):
        ts = start + timedelta(minutes=15 * i)
        for sensor, base in SENSORS.items():
            spike = rng.random() < 0.03 or (i == steps and sensor == "salle-serveur-2")
            rows.append((ts.isoformat(timespec="seconds"), sensor, _value(base, rng, spike)))
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["horodatage", "capteur", "valeur"])
        w.writerows(rows)
    return rows


def append_now(path: Path, spike_sensor: str | None = None) -> list[tuple[str, str, float]]:
    rng = random.Random()
    now = datetime.now().replace(microsecond=0).isoformat()
    rows = [(now, s, _value(base, rng, s == spike_sensor)) for s, base in SENSORS.items()]
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fichier", default="mesures.csv", type=Path)
    parser.add_argument("--ajouter", action="store_true", help="ajoute une mesure par capteur à l'heure actuelle")
    parser.add_argument("--pic", choices=list(SENSORS), help="avec --ajouter : force un dépassement sur ce capteur")
    args = parser.parse_args()

    if args.ajouter:
        for row in append_now(args.fichier, args.pic):
            print("ajouté :", *row)
    else:
        rows = generate(args.fichier)
        print(f"{args.fichier} : {len(rows)} mesures fictives")


if __name__ == "__main__":
    main()
