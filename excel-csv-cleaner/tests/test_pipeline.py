"""Tests de bout en bout sur le jeu de données fictif généré."""

import re
from datetime import date, datetime

import pytest
from openpyxl import load_workbook

import clean
from cleaner.excel_report import write_report
from cleaner.normalize import CLIENT_INCONNU


def test_doublons_supprimes(result, dataset):
    _, _, truth = dataset
    assert result.stats["doublons"] == truth.n_duplicates == 8
    assert len(result.data) == len(truth.sales) == 60
    assert not result.data.duplicated(subset=["Date", "Client", "Produit", "Montant"]).any()


def test_lignes_rejetees_et_vides(result, dataset):
    _, _, truth = dataset
    assert result.stats["lignes_rejetees"] == truth.n_rejected
    assert result.stats["lignes_vides"] == truth.n_blank


def test_ventes_identiques_a_la_verite_terrain(result, dataset):
    _, _, truth = dataset
    obtenues = set(result.data[["Date", "Client", "Produit", "Montant"]].itertuples(index=False, name=None))
    assert obtenues == set(truth.sales)


def test_dates_iso(result):
    assert all(isinstance(d, date) for d in result.data["Date"])
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.isoformat()) for d in result.data["Date"])


def test_montants_numeriques(result):
    assert all(isinstance(m, float) for m in result.data["Montant"])


def test_total_hors_doublons(result, dataset):
    _, _, truth = dataset
    assert round(result.data["Montant"].sum(), 2) == pytest.approx(truth.total, abs=0.005)


def test_clients_ramenes_au_referentiel(result, dataset):
    _, reference, _ = dataset
    assert set(result.data["Client"]) <= set(reference) | {CLIENT_INCONNU}


def test_journal_trace_chaque_type_de_correction(result):
    champs = {c.champ for c in result.corrections}
    assert {"Date", "Montant", "Client", "Produit", "(ligne)"} <= champs
    assert sum("doublon" in c.avant for c in result.corrections) == result.stats["doublons"]
    assert all(c.ligne >= 2 for c in result.corrections)  # ligne 1 = en-tête


def test_rapport_excel(result, dataset, tmp_path):
    """Le fichier produit contient les 3 onglets, des dates ISO et des montants numériques."""
    _, _, truth = dataset
    out = tmp_path / "rapport.xlsx"
    write_report(result, out)
    wb = load_workbook(out)
    assert wb.sheetnames == ["Donnees_nettoyees", "Resume", "Journal_corrections"]

    ws = wb["Donnees_nettoyees"]
    rows = list(ws.iter_rows(min_row=2))
    assert len(rows) == len(truth.sales)
    for row in rows:
        assert isinstance(row[0].value, datetime) and row[0].number_format == "yyyy-mm-dd"
        assert isinstance(row[3].value, (int, float))

    ws = wb["Resume"]
    total_row = next(r for r in ws.iter_rows() if r[0].value == "Total")
    headers = [c.value for c in ws[1]]
    assert total_row[headers.index("Total")].value == pytest.approx(truth.total, abs=0.005)
    assert total_row[headers.index("Nb ventes")].value == len(truth.sales)

    ws = wb["Journal_corrections"]
    assert [c.value for c in ws[1]] == ["Fichier", "Ligne", "Champ", "Avant", "Après"]
    assert ws.max_row - 1 == len(result.corrections)


def test_cli(dataset, tmp_path, capsys):
    data_dir, _, _ = dataset
    out = tmp_path / "cli.xlsx"
    assert clean.main(["--input", str(data_dir), "--output", str(out),
                       "--clients", str(data_dir.parent / "clients.csv")]) == 0
    assert out.exists()
    assert "Ventes retenues : 60" in capsys.readouterr().out


def test_cli_dossier_vide(tmp_path):
    assert clean.main(["--input", str(tmp_path), "--output", str(tmp_path / "x.xlsx")]) == 1
