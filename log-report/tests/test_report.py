"""Tests de bout en bout : CLI, exports, PDF (2 pages max)."""

import re
from pathlib import Path

import pytest

import report
from generate_sample_data import generate

FIX = Path(__file__).parent / "fixtures"


def pdf_page_count(path: Path) -> int:
    """Compte les objets /Type /Page (sans lib externe de lecture PDF)."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", path.read_bytes()))


def test_cli_fixtures(tmp_path, capsys):
    pdf = tmp_path / "r.pdf"
    assert report.main([str(FIX / "mini_old.log"), str(FIX / "mini_new.log"),
                        "--pdf", str(pdf), "--export-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "- [l.1] 2026-11-10 08:00:01 INFO Démarrage du service" in out
    assert pdf.read_bytes().startswith(b"%PDF")
    assert 1 <= pdf_page_count(pdf) <= 2
    assert (tmp_path / "diff.txt").read_text(encoding="utf-8").count("\n+ ") == 2
    assert (tmp_path / "top_erreurs.csv").exists()
    assert (tmp_path / "erreurs_par_heure.csv").exists()


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("logs"))


def test_donnees_generees_scenario(sample):
    """La rotation supprime 06h-08h et l'après-déploiement ajoute des lignes."""
    old, new = sample
    d = report.analyse(old, new)
    assert all(t[11:13] in ("06", "07") for _, t in d.diff.removed if t[:4] == "2026")
    assert all(t[11:13] >= "14" for _, t in d.diff.added if t[:4] == "2026")
    # La nouvelle erreur de la v2.4 entre dans le top 5 et n'existe pas dans l'ancien log.
    assert any(m.startswith("KeyError") for m in d.top["message"])
    assert not d.old.entries["message"].str.startswith("KeyError").any()


def test_pdf_deux_pages_max(sample, tmp_path):
    old, new = sample
    pdf = tmp_path / "rapport.pdf"
    assert report.main([str(old), str(new), "--pdf", str(pdf)]) == 0
    assert pdf_page_count(pdf) == 2


def test_fichier_absent(tmp_path):
    assert report.main([str(tmp_path / "x.log"), str(tmp_path / "y.log")]) == 1
