"""Logique pure : seuil, parsing de /seuil, lecture du CSV."""

from datetime import datetime

import pytest

from alerting import (Measure, ThresholdError, exceeds, format_alert, latest_by_sensor,
                      new_alerts, parse_threshold, read_measures)
from generate_sample_data import generate


# --- Parsing de /seuil ---
@pytest.mark.parametrize("args, attendu", [
    (["30"], 30.0), (["30.5"], 30.5), (["30,5"], 30.5), (["-5"], -5.0), (["0"], 0.0), ([" 42 "], 42.0),
])
def test_parse_threshold_valide(args, attendu):
    assert parse_threshold(args) == attendu


@pytest.mark.parametrize("args", [[], ["abc"], ["30", "40"], ["nan"], ["inf"], ["-inf"], [""], ["30°"], ["1e999"]])
def test_parse_threshold_invalide(args):
    with pytest.raises(ThresholdError):
        parse_threshold(args)


def test_parse_threshold_message_utilisateur():
    with pytest.raises(ThresholdError, match="« abc » n'est pas un nombre valide"):
        parse_threshold(["abc"])


# --- Logique de seuil ---
T = datetime(2026, 11, 12, 8, 0)
T2 = datetime(2026, 11, 12, 8, 15)


def test_exceeds_strictement_superieur():
    assert exceeds(Measure(T, "a", 30.1), 30)
    assert not exceeds(Measure(T, "a", 30.0), 30)  # égal au seuil : pas d'alerte
    assert not exceeds(Measure(T, "a", 12), 30)


def test_new_alerts_derniere_mesure_seulement():
    measures = [Measure(T, "a", 40), Measure(T2, "a", 20), Measure(T, "b", 35)]
    # « a » est redescendu sous le seuil : seule « b » alerte.
    assert new_alerts(measures, 30, {}) == [Measure(T, "b", 35)]


def test_new_alerts_pas_de_doublon():
    deja = {}
    measures = [Measure(T, "a", 40)]
    assert len(new_alerts(measures, 30, deja)) == 1
    assert new_alerts(measures, 30, deja) == []            # même mesure : pas de 2e alerte
    measures.append(Measure(T2, "a", 41))
    assert new_alerts(measures, 30, deja) == [Measure(T2, "a", 41)]  # nouvelle mesure : alerte


def test_latest_by_sensor():
    latest = latest_by_sensor([Measure(T2, "b", 1), Measure(T, "a", 2), Measure(T, "b", 3)])
    assert list(latest) == ["a", "b"] and latest["b"].value == 1


def test_format_alert():
    assert format_alert([Measure(T, "salle-1", 33.4)], 30) == "⚠️ Seuil 30 dépassé :\n• salle-1 : 33.4 (12/11/2026 08:00)"


# --- Lecture du CSV ---
def test_read_measures_valide_et_lignes_invalides(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("horodatage,capteur,valeur\n"
                 "2026-11-12T08:00:00,salle-1,22.5\n"
                 "2026-11-12 08:15:00,salle-1,\"23,5\"\n"
                 "pas-une-date,salle-1,20\n"
                 "2026-11-12T08:30:00,salle-1,abc\n"
                 "2026-11-12T08:30:00,,20\n"
                 "2026-11-12T08:45:00,salle-2\n", encoding="utf-8")
    mf = read_measures(p)
    assert mf.measures == [Measure(T, "salle-1", 22.5), Measure(T2, "salle-1", 23.5)]
    assert mf.invalid_rows == [4, 5, 6, 7]


def test_read_measures_colonne_manquante(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("date,capteur,valeur\n", encoding="utf-8")
    with pytest.raises(ValueError, match="horodatage"):
        read_measures(p)


def test_read_measures_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_measures(tmp_path / "absent.csv")


def test_donnees_generees(tmp_path):
    rows = generate(tmp_path / "mesures.csv")
    mf = read_measures(tmp_path / "mesures.csv")
    assert len(mf.measures) == len(rows) == 97 * 3 and mf.invalid_rows == []
    # La dernière mesure de salle-serveur-2 dépasse le seuil par défaut (30).
    assert [m.sensor for m in new_alerts(mf.measures, 30, {})] == ["salle-serveur-2"]
