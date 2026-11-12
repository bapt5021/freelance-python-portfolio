"""Rapport PDF (2 pages maximum) : résumé, chiffres clés, 2 graphiques, extrait du diff."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .charts import errors_per_hour_chart, top_errors_chart
from .diff import DiffResult
from .parsing import ParsedLog

DIFF_EXCERPT_LINES = 12  # borne l'extrait du diff pour tenir sur 2 pages


@dataclass
class ReportData:
    old: ParsedLog
    new: ParsedLog
    diff: DiffResult
    old_counts: dict[str, int]
    new_counts: dict[str, int]
    old_per_hour: pd.Series
    new_per_hour: pd.Series
    top: pd.DataFrame


def summary_sentences(d: ReportData) -> list[str]:
    """Résumé rédigé automatiquement à partir des chiffres."""
    o, n = d.old.path.name, d.new.path.name
    old_total, new_total = sum(d.old_counts.values()), sum(d.new_counts.values())
    old_rate = d.old_counts["ERROR"] / old_total * 100 if old_total else 0
    new_rate = d.new_counts["ERROR"] / new_total * 100 if new_total else 0
    out = [
        f"{n} contient {new_total} entrées dont {d.new_counts['ERROR']} erreurs "
        f"({new_rate:.1f} %), contre {old_total} entrées et {d.old_counts['ERROR']} erreurs "
        f"({old_rate:.1f} %) pour {o}.",
        f"Le diff fait apparaître {len(d.diff.added)} ligne(s) ajoutée(s) et "
        f"{len(d.diff.removed)} ligne(s) supprimée(s).",
    ]
    if d.new_per_hour.sum():
        peak = d.new_per_hour.idxmax()
        out.append(f"Pic d'erreurs dans {n} : {int(d.new_per_hour.max())} erreur(s) "
                   f"le {peak:%d/%m/%Y} entre {peak:%H}h et {peak.hour + 1}h.")
    if not d.top.empty:
        first = d.top.iloc[0]
        out.append(f"Erreur la plus fréquente : « {first['message']} » "
                   f"({first['occurrences']} occurrence(s)).")
    return out


def build_pdf(d: ReportData, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=7, leading=8.5)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)

    doc = SimpleDocTemplate(str(output), pagesize=A4, title="Rapport d'analyse de logs",
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    width = A4[0] - doc.leftMargin - doc.rightMargin
    story = [
        Paragraph("Rapport d'analyse de logs", styles["Title"]),
        Paragraph(f"{escape(d.old.path.name)} → {escape(d.new.path.name)} · généré le "
                  f"{datetime.now():%d/%m/%Y %H:%M}", body),
        Paragraph("Résumé", h2),
        *[Paragraph(escape(s), body) for s in summary_sentences(d)],
        Spacer(1, 6),
    ]

    # Tableau des chiffres clés.
    rows = [["", d.old.path.name, d.new.path.name]]
    for lvl in ("INFO", "WARNING", "ERROR"):
        rows.append([lvl, d.old_counts[lvl], d.new_counts[lvl]])
    rows.append(["Lignes non reconnues", d.old.unparsed, d.new.unparsed])
    table = Table(rows, colWidths=[5 * cm, 4 * cm, 4 * cm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#52514e")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f3f0")]),
    ]))
    story += [table, Spacer(1, 10)]

    def image(png: bytes) -> Image:
        img = Image(io.BytesIO(png))
        ratio = img.imageHeight / img.imageWidth
        img.drawWidth, img.drawHeight = width, width * ratio
        return img

    story.append(image(errors_per_hour_chart(d.old_per_hour, d.new_per_hour,
                                             d.old.path.name, d.new.path.name)))
    story.append(PageBreak())
    if not d.top.empty:
        story.append(image(top_errors_chart(d.top)))

    # Extrait du diff (le diff complet est exportable en texte).
    excerpt = ([f"- [l.{n}] {t}" for n, t in d.diff.removed[:DIFF_EXCERPT_LINES // 2]]
               + [f"+ [l.{n}] {t}" for n, t in d.diff.added[:DIFF_EXCERPT_LINES // 2]])
    hidden = len(d.diff.removed) + len(d.diff.added) - len(excerpt)
    diff_block = [Paragraph("Extrait du diff", h2)]
    diff_block += [Paragraph(escape(line[:130]), mono) for line in excerpt] or [
        Paragraph("Aucune différence.", body)]
    if hidden > 0:
        diff_block.append(Paragraph(f"… et {hidden} autre(s) ligne(s) (voir l'export texte du diff).", body))
    story.append(KeepTogether(diff_block))

    doc.build(story)
