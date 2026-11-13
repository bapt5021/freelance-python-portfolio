"""Vérifie que le token Telegram est valide, SANS jamais l'afficher.

Lit TELEGRAM_BOT_TOKEN (variable d'environnement ou fichier .env), appelle
l'API getMe et affiche le nom du bot. Aucun message n'est envoyé.

    python check_token.py
"""

from __future__ import annotations

import asyncio
import sys

from telegram import Bot
from telegram.error import InvalidToken, NetworkError, TelegramError

import bot as bot_module


async def describe_bot(token: str) -> str:
    async with Bot(token) as tg_bot:
        me = await tg_bot.get_me()
    return f"Token valide : bot @{me.username} (« {me.first_name} », id {me.id})"


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        config = bot_module.load_config()
    except bot_module.ConfigError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    try:
        print(asyncio.run(describe_bot(config.token)))
    except InvalidToken:
        print("Erreur : token refusé par Telegram (invalide ou révoqué).", file=sys.stderr)
        return 1
    except NetworkError as exc:
        print(f"Erreur réseau : impossible de joindre Telegram ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except TelegramError as exc:
        print(f"Erreur Telegram : {type(exc).__name__}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
