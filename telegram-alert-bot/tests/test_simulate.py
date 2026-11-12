"""La simulation hors ligne déroule le scénario attendu (anti-doublon compris)."""

import asyncio

from generate_sample_data import generate
from simulate import format_transcript, run_scenario


def test_simulation(tmp_path):
    csv_path = tmp_path / "mesures.csv"
    generate(csv_path)
    transcript = asyncio.run(run_scenario(csv_path))
    alerts = [t["text"] for t in transcript if t["role"] == "bot" and t["text"].startswith("⚠️")]
    # 1re alerte (salle-serveur-2 à 34.2), puis seulement celle de la nouvelle mesure.
    assert len(alerts) == 2
    assert "salle-serveur-2 : 34.2" in alerts[0] and "local-onduleur : 36.8" in alerts[1]
    assert sum(t["text"] == "→ aucune alerte envoyée" for t in transcript) == 2
    assert "SIMULATION" in format_transcript(transcript)
