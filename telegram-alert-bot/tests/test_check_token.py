"""check_token.py : erreurs claires et token JAMAIS affiché (aucun appel réseau)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import InvalidToken, NetworkError

import check_token

FAKE = "123456789:FAUX_TOKEN_DE_TEST_abcdefghijklmnopqrs"


def run(monkeypatch, capsys, token=FAKE, get_me=None):
    monkeypatch.setattr(check_token, "load_dotenv", lambda: None, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    if token is None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    fake_bot = AsyncMock()
    fake_bot.__aenter__.return_value = fake_bot
    fake_bot.get_me = get_me or AsyncMock()
    with patch.object(check_token, "Bot", return_value=fake_bot):
        code = check_token.main()
    out = capsys.readouterr()
    return code, out.out + out.err


def test_token_absent(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, token=None)
    assert code == 1 and "TELEGRAM_BOT_TOKEN" in out


def test_token_valide(monkeypatch, capsys):
    me = SimpleNamespace(username="demo_alertes_bot", first_name="Démo", id=42)
    code, out = run(monkeypatch, capsys, get_me=AsyncMock(return_value=me))
    assert code == 0 and "@demo_alertes_bot" in out
    assert FAKE not in out


def test_token_refuse_sans_fuite(monkeypatch, capsys):
    # Le message d'InvalidToken de la bibliothèque peut contenir le token : il ne doit pas être affiché.
    err = InvalidToken(f"The token `{FAKE}` was rejected by the server.")
    code, out = run(monkeypatch, capsys, get_me=AsyncMock(side_effect=err))
    assert code == 1 and "refusé" in out
    assert FAKE not in out and "FAUX_TOKEN" not in out


def test_erreur_reseau_sans_fuite(monkeypatch, capsys):
    err = NetworkError(f"https://api.telegram.org/bot{FAKE}/getMe unreachable")
    code, out = run(monkeypatch, capsys, get_me=AsyncMock(side_effect=err))
    assert code == 1 and "réseau" in out and FAKE not in out
