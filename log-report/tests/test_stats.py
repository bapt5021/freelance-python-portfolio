"""Statistiques vérifiées sur un mini fichier dont on connaît le résultat."""

from pathlib import Path

import pandas as pd

from logreport.parsing import parse_log
from logreport.stats import errors_per_hour, level_counts, message_template, top_errors

FIX = Path(__file__).parent / "fixtures"


def test_parsing():
    log = parse_log(FIX / "mini_stats.log")
    assert len(log.entries) == 11
    assert log.unparsed == 1                      # la ligne « Traceback… »
    assert log.entries.iloc[4]["niveau"] == "WARNING"  # WARN -> WARNING
    assert log.entries.iloc[4]["ligne"] == 6


def test_level_counts():
    log = parse_log(FIX / "mini_stats.log")
    assert level_counts(log.entries) == {"INFO": 1, "WARNING": 1, "ERROR": 9}


def test_errors_per_hour():
    per_hour = errors_per_hour(parse_log(FIX / "mini_stats.log").entries)
    expected = {"2026-11-10 08:00": 3, "2026-11-10 09:00": 0,
                "2026-11-10 10:00": 2, "2026-11-10 11:00": 4}
    assert {f"{h:%Y-%m-%d %H:%M}": n for h, n in per_hour.items()} == expected


def test_top5_errors():
    top = top_errors(parse_log(FIX / "mini_stats.log").entries, n=5)
    assert list(top.itertuples(index=False, name=None)) == [
        ("Timeout de connexion à la base db-<N> après <N> s", 3),
        ("Échec du paiement : transaction <ID> refusée", 2),
        ("Disque plein sur /var", 1),
        ("Erreur SMTP <N> lors de l'envoi à <IP>", 1),
        ("Fichier introuvable : /data/import/clients.csv", 1),
    ]  # « Mémoire insuffisante… » (1) est 6e par ordre alphabétique


def test_message_template():
    assert message_template("Erreur SMTP 451 lors de l'envoi à 10.0.0.12") == \
        "Erreur SMTP <N> lors de l'envoi à <IP>"
    assert message_template("transaction 9f8e7d6c5b refusée") == "transaction <ID> refusée"
    assert message_template("Disque plein") == "Disque plein"


def test_fichier_vide(tmp_path):
    empty = tmp_path / "vide.log"
    empty.write_text("", encoding="utf-8")
    log = parse_log(empty)
    assert log.entries.empty
    assert errors_per_hour(log.entries).empty
    assert top_errors(log.entries).empty
