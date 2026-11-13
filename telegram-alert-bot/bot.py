"""Bot Telegram d'alertes sur seuil, à partir d'un CSV local de mesures.

Commandes : /start, /aide, /statut, /seuil <valeur>
Configuration par variables d'environnement (voir .env.example).

Lancement :
    python bot.py
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from telegram import BotCommand, Update
from telegram.error import Forbidden
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from alerting import (ThresholdError, fmt_value, format_alert, format_status,
                      new_alerts, parse_threshold, read_measures)

log = logging.getLogger("alert-bot")

COMMANDS = [
    ("start", "Activer les alertes pour ce chat"),
    ("aide", "Afficher l'aide"),
    ("statut", "Seuil, intervalle et dernières valeurs"),
    ("seuil", "Changer le seuil : /seuil 30.5"),
]


class ConfigError(Exception):
    pass


@dataclass
class Config:
    token: str
    csv_path: Path = Path("mesures.csv")
    interval_min: float = 5.0
    initial_threshold: float = 30.0
    allowed_chat_ids: set[int] = field(default_factory=set)  # vide = tout le monde


def load_config(env: dict[str, str] | None = None) -> Config:
    """Construit la configuration à partir des variables d'environnement."""
    env = os.environ if env is None else env
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("La variable d'environnement TELEGRAM_BOT_TOKEN n'est pas définie "
                          "(voir .env.example).")
    try:
        interval = float(env.get("INTERVALLE_MINUTES", "5"))
        threshold = parse_threshold([env.get("SEUIL_INITIAL", "30")])
        allowed = {int(x) for x in env.get("ALLOWED_CHAT_IDS", "").replace(" ", "").split(",") if x}
    except (ValueError, ThresholdError) as exc:
        raise ConfigError(f"Configuration invalide : {exc}") from None
    if interval <= 0:
        raise ConfigError("INTERVALLE_MINUTES doit être strictement positif.")
    return Config(token=token, csv_path=Path(env.get("MESURES_CSV", "mesures.csv")),
                  interval_min=interval, initial_threshold=threshold, allowed_chat_ids=allowed)


# --- État partagé (bot_data) --------------------------------------------------------
# bot_data["config"]        : Config
# bot_data["seuil"]         : seuil courant (float)
# bot_data["abonnes"]       : set des chat_id qui reçoivent les alertes
# bot_data["deja_alerte"]   : {capteur: horodatage déjà signalé}

def init_state(bot_data: dict, config: Config) -> None:
    bot_data.setdefault("config", config)
    bot_data.setdefault("seuil", config.initial_threshold)
    bot_data.setdefault("abonnes", set())
    bot_data.setdefault("deja_alerte", {})


# --- Commandes ---------------------------------------------------------------------

AIDE = (
    "Je surveille un fichier de mesures et vous préviens quand une valeur dépasse le seuil.\n\n"
    "/start — activer les alertes pour ce chat\n"
    "/statut — seuil, fréquence et dernières valeurs\n"
    "/seuil <valeur> — changer le seuil (ex. /seuil 30.5)\n"
    "/aide — cette aide"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot_data["abonnes"].add(update.effective_chat.id)
    # L'identifiant du chat sert à renseigner ALLOWED_CHAT_IDS (restriction d'accès).
    log.info("Chat %s abonné aux alertes", update.effective_chat.id)
    await update.message.reply_text(
        f"Bonjour ! Les alertes sont activées pour ce chat "
        f"(seuil actuel : {fmt_value(context.bot_data['seuil'])}).\n\n{AIDE}")


async def aide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(AIDE)


async def statut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    try:
        mf = read_measures(config.csv_path)
    except (OSError, ValueError) as exc:
        await update.message.reply_text(f"Impossible de lire les mesures : {exc}")
        return
    subscribed = update.effective_chat.id in context.bot_data["abonnes"]
    await update.message.reply_text(
        format_status(mf, context.bot_data["seuil"], config.interval_min, subscribed))


async def seuil(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"Seuil actuel : {fmt_value(context.bot_data['seuil'])}\nPour le changer : /seuil 30.5")
        return
    try:
        value = parse_threshold(context.args)
    except ThresholdError as exc:
        await update.message.reply_text(str(exc))
        return
    context.bot_data["seuil"] = value
    context.bot_data["deja_alerte"].clear()  # nouveau seuil : on réévalue tout
    log.info("Seuil modifié à %s par le chat %s", value, update.effective_chat.id)
    await update.message.reply_text(f"✅ Nouveau seuil : {fmt_value(value)}")


# --- Tâche planifiée --------------------------------------------------------------

async def check_measures(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Relit le CSV et envoie une alerte aux abonnés si une valeur dépasse le seuil."""
    # Personne d'abonné : on ne fait rien, sinon les alertes seraient marquées
    # « déjà envoyées » et le premier abonné ne les recevrait jamais.
    if not context.bot_data["abonnes"]:
        return
    config: Config = context.bot_data["config"]
    try:
        mf = read_measures(config.csv_path)
    except (OSError, ValueError) as exc:
        log.warning("Lecture des mesures impossible : %s", exc)
        return

    threshold = context.bot_data["seuil"]
    alerts = new_alerts(mf.measures, threshold, context.bot_data["deja_alerte"])
    if not alerts:
        return
    text = format_alert(alerts, threshold)
    for chat_id in list(context.bot_data["abonnes"]):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
        except Forbidden:  # l'utilisateur a bloqué le bot : on arrête de lui écrire
            log.info("Chat %s injoignable, désabonné", chat_id)
            context.bot_data["abonnes"].discard(chat_id)
    log.info("%d alerte(s) envoyée(s) à %d chat(s)", len(alerts), len(context.bot_data["abonnes"]))


# --- Assemblage -------------------------------------------------------------------

async def _post_init(app: Application) -> None:
    """Déclare les commandes (menu « / » dans Telegram)."""
    await app.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Erreur pendant le traitement d'une mise à jour", exc_info=context.error)


def build_application(config: Config) -> Application:
    app = Application.builder().token(config.token).post_init(_post_init).build()
    init_state(app.bot_data, config)

    # Si ALLOWED_CHAT_IDS est renseigné, les autres chats sont ignorés.
    chat_filter = filters.Chat(chat_id=config.allowed_chat_ids) if config.allowed_chat_ids else None
    for name, callback in (("start", start), ("aide", aide), ("statut", statut), ("seuil", seuil)):
        app.add_handler(CommandHandler(name, callback, filters=chat_filter))
    app.add_error_handler(_on_error)

    app.job_queue.run_repeating(check_measures, interval=timedelta(minutes=config.interval_min),
                                first=10, name="verification-seuil")
    return app


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s : %(message)s", level=logging.INFO)
    # httpx journalise les URL appelées, qui contiennent le token : on le fait taire.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        from dotenv import load_dotenv
        load_dotenv()  # lit .env s'il existe (sans écraser les variables déjà définies)
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"Erreur : {exc}") from None

    log.info("Démarrage : CSV=%s, intervalle=%s min, seuil=%s, chats autorisés=%s",
             config.csv_path, config.interval_min, config.initial_threshold,
             sorted(config.allowed_chat_ids) or "tous")
    build_application(config).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
