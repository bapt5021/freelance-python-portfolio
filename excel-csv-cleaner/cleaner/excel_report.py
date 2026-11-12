"""Écriture du rapport Excel (3 onglets) avec une mise en forme lisible."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .pipeline import CleaningResult, build_summary

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="305496")
TOTAL_FONT = Font(bold=True)
MONEY = '#,##0.00 "€"'
ISO_DATE = "yyyy-mm-dd"


def _style_sheet(ws, widths: dict[str, int]) -> None:
    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"


def write_report(result: CleaningResult, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = build_summary(result.data) if len(result.data) else pd.DataFrame()
    journal = pd.DataFrame(
        [(c.fichier, c.ligne, c.champ, c.avant, c.apres) for c in result.corrections],
        columns=["Fichier", "Ligne", "Champ", "Avant", "Après"],
    )

    data = result.data.rename(columns={"Montant": "Montant (€)"})
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data.to_excel(writer, sheet_name="Donnees_nettoyees", index=False)
        summary.to_excel(writer, sheet_name="Resume", index=True)
        journal.to_excel(writer, sheet_name="Journal_corrections", index=False)

    # Mise en forme avec openpyxl (formats de date/montant, largeurs, totaux en gras).
    wb = load_workbook(output)

    ws = wb["Donnees_nettoyees"]
    _style_sheet(ws, {"A": 12, "B": 22, "C": 20, "D": 14, "E": 22, "F": 12})
    for (date_cell,), (amount_cell,) in zip(ws.iter_rows(min_row=2, min_col=1, max_col=1),
                                            ws.iter_rows(min_row=2, min_col=4, max_col=4)):
        date_cell.number_format = ISO_DATE
        amount_cell.number_format = MONEY

    ws = wb["Resume"]
    _style_sheet(ws, {get_column_letter(i): 18 for i in range(1, ws.max_column + 1)})
    ws["A1"].value = "Mois"
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=ws.max_column - 1):
        for cell in row:
            cell.number_format = MONEY
    for cell in ws[ws.max_row]:  # ligne « Total »
        cell.font = TOTAL_FONT
    # Indicateurs de qualité sous le tableau croisé.
    start = ws.max_row + 2
    ws.cell(start, 1, "Indicateurs de nettoyage").font = TOTAL_FONT
    s = result.stats
    indicateurs = [
        ("Lignes lues", s["lignes_lues"]),
        ("Lignes vides supprimées", s["lignes_vides"]),
        ("Lignes rejetées (date/montant illisible)", s["lignes_rejetees"]),
        ("Doublons supprimés", s["doublons"]),
        ("Ventes retenues", s["ventes_retenues"]),
        ("Corrections journalisées", len(result.corrections)),
    ]
    for i, (label, value) in enumerate(indicateurs, start=start + 1):
        ws.cell(i, 1, label)
        ws.cell(i, 2, value)
    ws.column_dimensions["A"].width = 40

    ws = wb["Journal_corrections"]
    _style_sheet(ws, {"A": 22, "B": 8, "C": 10, "D": 34, "E": 44})
    ws.auto_filter.ref = ws.dimensions

    wb.save(output)
