"""Génère deux fichiers .log 100 % fictifs pour la démo log-report.

Scénario : le même fichier de log d'une application web fictive, capturé à
deux moments.
  - data/old.log : de 06h à 14h ;
  - data/new.log : de 08h à 18h. La rotation a purgé 06h-08h (lignes
    « supprimées ») et de nouvelles lignes sont arrivées après le déploiement
    d'une version 2.4 à 14h, qui introduit une nouvelle erreur (lignes « ajoutées »).
Quelques erreurs sont suivies d'une trace Python (lignes non reconnues).
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

DAY = datetime(2026, 11, 10)
DEPLOY_HOUR = 14

INFO = [
    lambda r: f"Requête GET /api/orders/{r.randint(1000, 9999)} traitée en {r.randint(12, 180)} ms",
    lambda r: f"Utilisateur {r.randint(1, 500)} connecté",
    lambda r: "Tâche planifiée export_quotidien terminée",
    lambda r: f"Cache rafraîchi ({r.randint(100, 900)} entrées)",
]
WARNING = [
    lambda r: f"Temps de réponse élevé sur /api/search : {r.randint(900, 3000)} ms",
    lambda r: f"Quota disque à {r.randint(80, 95)} %",
    lambda r: f"Nouvelle tentative de connexion SMTP ({r.randint(1, 3)}/3)",
]
# (fonction de message, poids)
ERRORS = [
    (lambda r: f"Timeout de connexion à la base db-0{r.randint(1, 3)} après 30 s", 5),
    (lambda r: f"Échec du paiement : transaction {r.getrandbits(40):010x} refusée", 3),
    (lambda r: f"Fichier introuvable : /data/import/{r.choice(['clients', 'stocks'])}.csv", 2),
    (lambda r: f"Erreur SMTP 451 lors de l'envoi à 10.0.{r.randint(0, 9)}.{r.randint(2, 254)}", 2),
    (lambda r: f"Mémoire insuffisante dans le worker {r.randint(1, 8)}", 1),
]
# Nouvelle erreur introduite par la version 2.4.
NEW_ERROR = (lambda r: "KeyError 'customer_id' dans OrderSerializer.to_dict", 9)


def _entries_for_hour(hour: int, rng: random.Random) -> list[tuple[datetime, list[str]]]:
    """Entrées (horodatage, lignes) pour une heure donnée."""
    after_deploy = hour >= DEPLOY_HOUR
    error_rate = 0.10 + (0.08 if hour == 11 else 0) + (0.12 if after_deploy else 0)
    errors = ERRORS + ([NEW_ERROR] if after_deploy else [])
    out = []
    seconds = sorted(rng.sample(range(3600), rng.randint(18, 28)))
    for s in seconds:
        ts = DAY + timedelta(hours=hour, seconds=s)
        p = rng.random()
        if p < error_rate:
            msg_fn = rng.choices([e[0] for e in errors], weights=[e[1] for e in errors])[0]
            lines = [f"{ts:%Y-%m-%d %H:%M:%S} ERROR {msg_fn(rng)}"]
            if rng.random() < 0.15:  # trace Python sur plusieurs lignes
                lines += ["Traceback (most recent call last):",
                          '  File "app/orders.py", line 42, in serialize']
        elif p < error_rate + 0.15:
            lines = [f"{ts:%Y-%m-%d %H:%M:%S} WARNING {rng.choice(WARNING)(rng)}"]
        else:
            lines = [f"{ts:%Y-%m-%d %H:%M:%S} INFO {rng.choice(INFO)(rng)}"]
        out.append((ts, lines))
    if hour == DEPLOY_HOUR:
        out.insert(0, (DAY + timedelta(hours=hour),
                       [f"{DAY:%Y-%m-%d} {hour:02d}:00:00 INFO Déploiement de la version 2.4 terminé"]))
    return out


def generate(out_dir: Path, seed: int = 7) -> tuple[Path, Path]:
    rng = random.Random(seed)
    timeline = [e for hour in range(6, 18) for e in _entries_for_hour(hour, rng)]
    old = [line for ts, lines in timeline if ts.hour < DEPLOY_HOUR for line in lines]
    new = [line for ts, lines in timeline if ts.hour >= 8 for line in lines]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    old_path, new_path = out_dir / "old.log", out_dir / "new.log"
    old_path.write_text("\n".join(old) + "\n", encoding="utf-8")
    new_path.write_text("\n".join(new) + "\n", encoding="utf-8")
    return old_path, new_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", default="data", type=Path)
    parser.add_argument("--seed", default=7, type=int)
    args = parser.parse_args()
    for p in generate(args.output_dir, args.seed):
        print(f"{p} : {len(p.read_text(encoding='utf-8').splitlines())} lignes")


if __name__ == "__main__":
    main()
