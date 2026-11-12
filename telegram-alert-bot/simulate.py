"""SIMULATION hors ligne du bot : aucune connexion à Telegram, aucun token.

Les vrais handlers (/start, /aide, /statut, /seuil) et la vraie tâche planifiée
de bot.py sont appelés avec de faux objets « update » et « bot » qui
enregistrent les réponses au lieu de les envoyer. Les mesures sont fictives
(générées dans un dossier temporaire).

    python simulate.py                       # affiche la conversation simulée
    python simulate.py --json sortie.json    # l'enregistre aussi en JSON
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import bot
from generate_sample_data import generate

CHAT_ID = 1001  # identifiant de chat fictif


class FakeBot:
    """Remplace telegram.Bot : enregistre les messages au lieu de les envoyer."""

    def __init__(self, transcript: list[dict]):
        self.transcript = transcript

    async def send_message(self, chat_id: int, text: str) -> None:
        self.transcript.append({"role": "bot", "text": text})


async def run_scenario(csv_path: Path) -> list[dict]:
    transcript: list[dict] = []
    bot_data: dict = {}
    bot.init_state(bot_data, bot.Config(token="SIMULATION", csv_path=csv_path,
                                        interval_min=5, initial_threshold=30))
    fake_bot = FakeBot(transcript)

    async def command(text: str) -> None:
        transcript.append({"role": "user", "text": text})
        name, *args = text.lstrip("/").split()

        async def reply_text(answer: str) -> None:
            transcript.append({"role": "bot", "text": answer})

        update = SimpleNamespace(effective_chat=SimpleNamespace(id=CHAT_ID),
                                 message=SimpleNamespace(reply_text=reply_text))
        context = SimpleNamespace(bot_data=bot_data, args=args, bot=fake_bot)
        await {"start": bot.start, "aide": bot.aide, "statut": bot.statut, "seuil": bot.seuil}[name](update, context)

    async def scheduled_check(label: str) -> None:
        before = len(transcript)
        transcript.append({"role": "event", "text": f"Tâche planifiée ({label})"})
        await bot.check_measures(SimpleNamespace(bot_data=bot_data, bot=fake_bot))
        if len(transcript) == before + 1:
            transcript.append({"role": "event", "text": "→ aucune alerte envoyée"})

    def add_measure(ts: str, sensor: str, value: float) -> None:
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write(f"{ts},{sensor},{value}\n")
        transcript.append({"role": "event", "text": f"Nouvelle mesure fictive : {sensor} = {value}"})

    await command("/start")
    await command("/statut")
    await scheduled_check("1er passage")
    await scheduled_check("2e passage, même mesure")      # anti-doublon
    await command("/seuil abc")                          # valeur invalide
    await command("/seuil 35")
    await scheduled_check("seuil 35")                   # 34.2 < 35 : rien
    add_measure("2026-11-12T08:15:00", "local-onduleur", 36.8)
    await scheduled_check("après la nouvelle mesure")
    return transcript


def format_transcript(transcript: list[dict]) -> str:
    out = ["=== SIMULATION — aucune connexion à Telegram, données fictives ===", ""]
    for item in transcript:
        if item["role"] == "event":
            out.append(f"   [{item['text']}]")
        else:
            prefix = "Utilisateur" if item["role"] == "user" else "Bot"
            lines = item["text"].splitlines()
            out.append(f"{prefix:>11} : {lines[0]}")
            out += [f"{'':>11}   {line}" for line in lines[1:]]
        out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="enregistre la conversation en JSON")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        # Données fictives régénérées à l'identique : la simulation est reproductible
        # et ne modifie jamais votre mesures.csv.
        csv_path = Path(tmp) / "mesures.csv"
        generate(csv_path)
        transcript = asyncio.run(run_scenario(csv_path))

    print(format_transcript(transcript))
    if args.json:
        args.json.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
