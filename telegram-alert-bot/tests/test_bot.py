"""Handlers et tâche planifiée, testés avec des objets simulés (aucun appel à Telegram)."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import Forbidden

import bot

CSV = ("horodatage,capteur,valeur\n"
       "2026-11-12T08:00:00,salle-1,22\n"
       "2026-11-12T08:00:00,salle-2,33.4\n")


@pytest.fixture
def csv_path(tmp_path) -> Path:
    p = tmp_path / "mesures.csv"
    p.write_text(CSV, encoding="utf-8")
    return p


@pytest.fixture
def bot_data(csv_path):
    data = {}
    bot.init_state(data, bot.Config(token="test", csv_path=csv_path, interval_min=1, initial_threshold=30))
    return data


def make_update(chat_id=111):
    return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id),
                           message=SimpleNamespace(reply_text=AsyncMock()))


def make_context(bot_data, args=None):
    return SimpleNamespace(bot_data=bot_data, args=args or [],
                           bot=SimpleNamespace(send_message=AsyncMock()))


def reply(update) -> str:
    return update.message.reply_text.await_args.args[0]


# --- Configuration ---
def test_config_token_obligatoire():
    with pytest.raises(bot.ConfigError, match="TELEGRAM_BOT_TOKEN"):
        bot.load_config({})


def test_config_complete():
    c = bot.load_config({"TELEGRAM_BOT_TOKEN": "x", "INTERVALLE_MINUTES": "2", "SEUIL_INITIAL": "28,5",
                         "ALLOWED_CHAT_IDS": "1, 2", "MESURES_CSV": "a.csv"})
    assert (c.interval_min, c.initial_threshold, c.allowed_chat_ids, c.csv_path) == (2, 28.5, {1, 2}, Path("a.csv"))


@pytest.mark.parametrize("env", [{"INTERVALLE_MINUTES": "0"}, {"INTERVALLE_MINUTES": "abc"},
                                 {"SEUIL_INITIAL": "abc"}, {"ALLOWED_CHAT_IDS": "moi"}])
def test_config_invalide(env):
    with pytest.raises(bot.ConfigError):
        bot.load_config({"TELEGRAM_BOT_TOKEN": "x", **env})


# --- Commandes ---
def test_start_abonne_le_chat(bot_data):
    u = make_update(42)
    asyncio.run(bot.start(u, make_context(bot_data)))
    assert 42 in bot_data["abonnes"]
    assert "alertes sont activées" in reply(u)


def test_aide(bot_data):
    u = make_update()
    asyncio.run(bot.aide(u, make_context(bot_data)))
    assert all(f"/{c}" in reply(u) for c in ("start", "statut", "seuil", "aide"))


def test_seuil_valide(bot_data):
    bot_data["deja_alerte"]["salle-2"] = "x"
    u = make_update()
    asyncio.run(bot.seuil(u, make_context(bot_data, ["35,5"])))
    assert bot_data["seuil"] == 35.5
    assert bot_data["deja_alerte"] == {}
    assert reply(u) == "✅ Nouveau seuil : 35.5"


@pytest.mark.parametrize("args", [["abc"], ["1", "2"], ["nan"]])
def test_seuil_invalide_ne_change_rien(bot_data, args):
    u = make_update()
    asyncio.run(bot.seuil(u, make_context(bot_data, args)))
    assert bot_data["seuil"] == 30
    assert "✅" not in reply(u)


def test_seuil_sans_argument_affiche_la_valeur(bot_data):
    u = make_update()
    asyncio.run(bot.seuil(u, make_context(bot_data, [])))
    assert reply(u).startswith("Seuil actuel : 30")


def test_statut(bot_data):
    u = make_update(7)
    bot_data["abonnes"].add(7)
    asyncio.run(bot.statut(u, make_context(bot_data)))
    text = reply(u)
    assert "Seuil actuel : 30" in text and "activées" in text
    assert "🔴 salle-2 : 33.4" in text and "🟢 salle-1 : 22" in text


def test_statut_csv_absent(bot_data, tmp_path):
    bot_data["config"].csv_path = tmp_path / "absent.csv"
    u = make_update()
    asyncio.run(bot.statut(u, make_context(bot_data)))
    assert reply(u).startswith("Impossible de lire les mesures")


# --- Tâche planifiée ---
def test_check_envoie_une_seule_fois_par_mesure(bot_data):
    bot_data["abonnes"].update({1, 2})
    ctx = make_context(bot_data)
    asyncio.run(bot.check_measures(ctx))
    assert ctx.bot.send_message.await_count == 2                 # un message par abonné
    assert "salle-2 : 33.4" in ctx.bot.send_message.await_args.kwargs["text"]
    asyncio.run(bot.check_measures(ctx))
    assert ctx.bot.send_message.await_count == 2                 # pas de répétition


def test_check_rien_sous_le_seuil(bot_data):
    bot_data["abonnes"].add(1)
    bot_data["seuil"] = 50
    ctx = make_context(bot_data)
    asyncio.run(bot.check_measures(ctx))
    ctx.bot.send_message.assert_not_awaited()


def test_check_desabonne_chat_bloque(bot_data):
    bot_data["abonnes"].update({1, 2})
    ctx = make_context(bot_data)
    async def send(chat_id, text):
        if chat_id == 1:
            raise Forbidden("bot was blocked by the user")
    ctx.bot.send_message = AsyncMock(side_effect=send)
    asyncio.run(bot.check_measures(ctx))
    assert bot_data["abonnes"] == {2}


def test_check_csv_absent_ne_plante_pas(bot_data, tmp_path):
    bot_data["config"].csv_path = tmp_path / "absent.csv"
    bot_data["abonnes"].add(1)
    ctx = make_context(bot_data)
    asyncio.run(bot.check_measures(ctx))
    ctx.bot.send_message.assert_not_awaited()


# --- Assemblage (construit l'application sans la démarrer : aucun appel réseau) ---
def test_build_application(csv_path):
    config = bot.Config(token="123456:FAUX-TOKEN-DE-TEST", csv_path=csv_path, interval_min=2,
                        allowed_chat_ids={99})
    app = bot.build_application(config)
    commands = {c for h in app.handlers[0] for c in h.commands}
    assert commands == {"start", "aide", "statut", "seuil"}
    job = app.job_queue.get_jobs_by_name("verification-seuil")[0]
    assert job.job.trigger.interval.total_seconds() == 120
    assert app.bot_data["seuil"] == 30
