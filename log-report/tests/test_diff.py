"""Diff exact sur de petites fixtures dont on connaît le résultat."""

from pathlib import Path

from logreport.diff import diff_lines, format_diff
from logreport.parsing import read_lines

FIX = Path(__file__).parent / "fixtures"


def test_diff_fixtures():
    result = diff_lines(read_lines(FIX / "mini_old.log"), read_lines(FIX / "mini_new.log"))
    assert result.removed == [(1, "2026-11-10 08:00:01 INFO Démarrage du service")]
    assert result.added == [
        (5, "2026-11-10 10:00:00 ERROR Timeout de connexion à la base db-02 après 30 s"),
        (6, "2026-11-10 10:01:00 ERROR KeyError 'customer_id' dans OrderSerializer"),
    ]


def test_ligne_modifiee_suppression_plus_ajout():
    result = diff_lines(["a", "b", "c"], ["a", "x", "c"])
    assert result.removed == [(2, "b")]
    assert result.added == [(2, "x")]


def test_fichiers_identiques():
    result = diff_lines(["a", "b"], ["a", "b"])
    assert result.removed == [] and result.added == []


def test_lignes_repetees():
    # Lignes identiques répétées : autojunk désactivé, le diff reste exact.
    old = ["x"] * 300 + ["fin"]
    new = ["x"] * 301 + ["fin"]
    result = diff_lines(old, new)
    assert result.removed == [] and len(result.added) == 1


def test_format_diff():
    text = format_diff(diff_lines(["a", "b"], ["a", "c"]), "old.log", "new.log")
    assert text == ("--- old.log\n+++ new.log\n"
                    "# 1 ligne(s) supprimée(s), 1 ligne(s) ajoutée(s)\n"
                    "- [l.2] b\n+ [l.2] c\n")
