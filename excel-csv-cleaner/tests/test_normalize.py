"""Tests unitaires des fonctions de normalisation."""

from datetime import date, datetime

import pytest

from cleaner.normalize import (CLIENT_INCONNU, PRODUIT_INCONNU, ClientMatcher,
                               clean_product, parse_amount, parse_date)


@pytest.mark.parametrize("raw", [
    "12/03/2026", "2026-03-12", "12 mars 2026", "12 Mars 2026", " 12-03-2026 ",
    "12.03.2026", datetime(2026, 3, 12, 0, 0), date(2026, 3, 12),
])
def test_parse_date_formats(raw):
    assert parse_date(raw) == date(2026, 3, 12)


def test_parse_date_premier_et_accents():
    assert parse_date("1er février 2026") == date(2026, 2, 1)
    assert parse_date("15 aout 2026") == date(2026, 8, 15)


@pytest.mark.parametrize("raw", ["", None, "   ", "31/02/2026", "32 mars 2026", "hier", "2026/13/45"])
def test_parse_date_invalide(raw):
    assert parse_date(raw) is None


@pytest.mark.parametrize("raw, attendu", [
    ("1234.50", 1234.5), ("1234,50", 1234.5), ("1 234,50 €", 1234.5), ("1 234,5", 1234.5),
    ("1.234,50", 1234.5), ("1,234.50", 1234.5), ("99", 99.0), (1234.5, 1234.5), (42, 42.0),
    ("1234,567", 1234.57), ("12 EUR", 12.0),
])
def test_parse_amount(raw, attendu):
    assert parse_amount(raw) == attendu


@pytest.mark.parametrize("raw", ["", None, "N/A", "abc", "12,3,4", float("nan"), True])
def test_parse_amount_invalide(raw):
    assert parse_amount(raw) is None


def test_client_matcher():
    m = ClientMatcher(["Dupont SARL", "Martin & Fils", "Café des Arts"])
    assert m.match("DUPONT SARL") == "Dupont SARL"
    assert m.match("  dupont   sarl ") == "Dupont SARL"
    assert m.match("Dupond SARL") == "Dupont SARL"          # faute de frappe
    assert m.match("Martin et Fils") == "Martin & Fils"     # & / et
    assert m.match("cafe des arts") == "Café des Arts"      # accents
    assert m.match("Société Inconnue  ") == "Société Inconnue"  # gardé, nettoyé
    assert m.match("") == CLIENT_INCONNU
    assert m.match(None) == CLIENT_INCONNU


def test_clean_product():
    assert clean_product("  Abonnement   Pro ") == "Abonnement Pro"
    assert clean_product("") == PRODUIT_INCONNU
