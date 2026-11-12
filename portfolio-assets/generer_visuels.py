"""Génère les visuels du portfolio à partir des fichiers RÉELLEMENT produits par les démos.

Nature de chaque image (indiquée aussi dans l'image elle-même) :
  - log-report-page-1.png / -2.png : rendu exact des pages de log-report/exemples/rapport.pdf ;
  - excel-csv-cleaner-apercu.png    : rendu des cellules de excel-csv-cleaner/exemples/rapport.xlsx
                                      (aucun tableur disponible : ce n'est PAS une capture d'Excel) ;
  - telegram-alert-bot-simulation.png : conversation produite par telegram-alert-bot/simulate.py,
                                      sans connexion à Telegram (SIMULATION) ;
  - portfolio-apercu.png            : planche des trois visuels ci-dessus.

Toutes les données sont fictives. À lancer depuis la racine du dépôt :
    python portfolio-assets/generer_visuels.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "portfolio-assets"

INK = "#0b0b0b"
MUTED = "#52514e"
HEADER = "#305496"     # même bleu que les en-têtes du rapport Excel
ZEBRA = "#f4f3f0"
LINE = "#d9d8d3"


def caption(fig, title: str, subtitle: str) -> None:
    fig.text(0.02, 0.985, title, ha="left", va="top", fontsize=15, weight="bold", color=INK)
    fig.text(0.02, 0.945, subtitle, ha="left", va="top", fontsize=9.5, color=MUTED, style="italic")


# --- log-report : rendu réel du PDF -----------------------------------------------

def render_pdf_pages() -> list[Path]:
    pdf = pdfium.PdfDocument(ROOT / "log-report/exemples/rapport.pdf")
    paths = []
    for i, page in enumerate(pdf, start=1):
        img = page.render(scale=1.6).to_pil()  # 1.6 × 72 dpi ≈ 115 dpi
        path = OUT / f"log-report-page-{i}.png"
        img.save(path, optimize=True)
        paths.append(path)
    pdf.close()
    return paths


# --- excel-csv-cleaner : rendu des cellules du rapport ------------------------------

def _fmt(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return str(v)


def _table(ax, rows: list[list], title: str, col_widths: list[float] | None = None,
           bold_last: bool = False) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11, weight="bold", color=INK, pad=6)
    cells = [[_fmt(v) for v in r] for r in rows]
    t = ax.table(cellText=cells[1:], colLabels=cells[0], loc="upper left", cellLoc="left",
                 colLoc="left", colWidths=col_widths)
    t.auto_set_font_size(False)
    t.set_fontsize(8.5)
    t.scale(1, 1.35)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(LINE)
        cell.set_linewidth(0.5)
        if r == 0:
            cell.set_facecolor(HEADER)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor(ZEBRA if r % 2 == 0 else "white")
            if bold_last and r == len(cells) - 1:
                cell.get_text().set_weight("bold")
        if isinstance(rows[r][c] if r < len(rows) else None, (int, float)):
            cell.get_text().set_ha("right")
            cell._loc = "right"


def render_excel_preview() -> Path:
    wb = load_workbook(ROOT / "excel-csv-cleaner/exemples/rapport.xlsx")
    resume = [list(r) for r in wb["Resume"].iter_rows(values_only=True)]
    pivot = resume[: next(i for i, r in enumerate(resume) if r[0] == "Total") + 1]
    data = [list(r) for r in wb["Donnees_nettoyees"].iter_rows(max_row=7, values_only=True)]
    journal_all = [list(r) for r in wb["Journal_corrections"].iter_rows(values_only=True)]
    # Un échantillon varié du journal : un exemple de chaque type de correction.
    picked, seen = [journal_all[0]], set()
    for r in journal_all[1:]:
        kind = r[2] if r[2] != "(ligne)" else str(r[3]).split()[0]
        if r[4] and str(r[4]).startswith("ligne rejetée"):
            kind = "rejet"
        if kind not in seen:
            seen.add(kind)
            picked.append(r)
    stats = {r[0]: r[1] for r in resume if r[0] and r[1] is not None and not str(r[0]).startswith("20")}

    W, H, row = 13, 7.7, 0.235  # pouces ; hauteur approximative d'une ligne de tableau

    def place(top: float, n_rows: int) -> list[float]:
        """Axe positionné en pouces depuis le haut de la figure (titre + n lignes)."""
        h = 0.35 + n_rows * row
        return [0.02, (H - top - h) / H, 0.96, h / H]

    fig = plt.figure(figsize=(W, H), dpi=110)
    caption(fig, "excel-csv-cleaner — rapport Excel généré (3 onglets)",
            "Rendu des cellules réelles de exemples/rapport.xlsx (pas une capture d'écran d'Excel) · données 100 % fictives")
    fig.text(0.02, 1 - 0.85 / H,
             f"{stats.get('Lignes lues')} lignes lues dans 3 fichiers (2 CSV + 1 XLSX)  →  "
             f"{stats.get('Ventes retenues')} ventes retenues · {stats.get('Doublons supprimés')} doublons supprimés · "
             f"{stats.get('Lignes rejetées (date/montant illisible)')} lignes rejetées · "
             f"{stats.get('Corrections journalisées')} corrections journalisées",
             fontsize=10, color=INK)
    top = 1.15
    _table(fig.add_axes(place(top, len(pivot))), pivot,
           "Onglet « Resume » — montants (€) par mois et par produit",
           col_widths=[0.07] + [0.1125] * (len(pivot[0]) - 1), bold_last=True)
    top += 0.35 + len(pivot) * row + 0.3
    _table(fig.add_axes(place(top, len(picked))), picked,
           "Onglet « Journal_corrections » — un exemple par type de correction",
           col_widths=[0.16, 0.05, 0.07, 0.33, 0.35])
    top += 0.35 + len(picked) * row + 0.3
    _table(fig.add_axes(place(top, len(data))), data, "Onglet « Donnees_nettoyees » — premières lignes",
           col_widths=[0.11, 0.2, 0.18, 0.12, 0.18, 0.1])
    path = OUT / "excel-csv-cleaner-apercu.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# --- telegram-alert-bot : conversation simulée -------------------------------------

# Les polices de matplotlib n'ont pas d'émojis en couleur : symboles équivalents.
EMOJI = {"⚠️": "⚠", "✅": "✔", "🟢": "●", "🔴": "▲"}


def _plain(text: str) -> str:
    for k, v in EMOJI.items():
        text = text.replace(k, v)
    return text


def render_bot_simulation() -> Path:
    transcript = json.loads((ROOT / "telegram-alert-bot/exemples/simulation.json").read_text(encoding="utf-8"))
    W, line_h, pad = 8.0, 0.19, 0.12
    blocks = []  # (role, lignes)
    for item in transcript:
        lines = _plain(item["text"]).splitlines() or [""]
        blocks.append((item["role"], lines))
    height = 1.25 + sum(len(b[1]) * line_h + (2 * pad + 0.16 if b[0] != "event" else 0.3) for b in blocks)

    fig = plt.figure(figsize=(W, height), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, height)
    ax.axis("off")
    # Bandeau SIMULATION bien visible.
    ax.add_patch(FancyBboxPatch((0.2, height - 0.95), W - 0.4, 0.75, boxstyle="round,pad=0,rounding_size=0.08",
                                fc="#fff4d6", ec="#c98500", lw=1.2))
    ax.text(W / 2, height - 0.47, "SIMULATION — aucune connexion à Telegram", ha="center", va="center",
            fontsize=12, weight="bold", color=INK)
    ax.text(W / 2, height - 0.75, "Conversation produite par simulate.py (vrais handlers, faux objets Telegram) · données fictives",
            ha="center", va="center", fontsize=8.5, color=MUTED)

    renderer = fig.canvas.get_renderer()
    y = height - 1.25
    for role, lines in blocks:
        if role == "event":
            ax.text(W / 2, y - 0.12, " ".join(lines), ha="center", va="center", fontsize=8.5,
                    color=MUTED, style="italic")
            y -= 0.3
            continue
        text = "\n".join(lines)
        x = W - 0.45 if role == "user" else 0.45
        t = ax.text(x, y - pad - 0.08, text, ha="right" if role == "user" else "left", va="top",
                    fontsize=9.5, color=INK, linespacing=1.45)
        bb = t.get_window_extent(renderer).transformed(ax.transData.inverted())
        ax.add_patch(FancyBboxPatch((bb.x0 - pad, bb.y0 - pad), bb.width + 2 * pad, bb.height + 2 * pad,
                                    boxstyle="round,pad=0,rounding_size=0.12", zorder=0,
                                    fc="#dbe8f8" if role == "user" else "#f1f0ec", ec="none"))
        ax.text(bb.x1 if role == "user" else bb.x0, bb.y1 + pad + 0.02,
                "Utilisateur" if role == "user" else "Bot", ha="right" if role == "user" else "left",
                va="bottom", fontsize=7, color=MUTED)
        y = bb.y0 - pad - 0.2
    ax.text(0.2, 0.08, "Émojis remplacés par des symboles pour ce rendu (texte original : exemples/simulation.txt).",
            fontsize=7, color=MUTED)
    path = OUT / "telegram-alert-bot-simulation.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# --- Planche récapitulative --------------------------------------------------------

def render_overview(excel: Path, pdf_page: Path, bot: Path) -> Path:
    fig = plt.figure(figsize=(15, 7.2), dpi=100)
    caption(fig, "Portfolio Python — 3 projets de démonstration",
            "Projets de démonstration (non réalisés pour un client), développés avec assistance IA, "
            "vérifiés par tests automatisés · données 100 % fictives")
    panels = [(excel, "excel-csv-cleaner\nNettoyage et fusion Excel/CSV"),
              (pdf_page, "log-report\nDiff de logs + rapport PDF"),
              (bot, "telegram-alert-bot\nAlertes sur seuil (simulation)")]
    for i, (img, label) in enumerate(panels):
        ax = fig.add_axes([0.02 + i * 0.33, 0.04, 0.30, 0.74])
        ax.imshow(plt.imread(img))
        ax.set_anchor("N")  # vignettes alignées en haut
        ax.set_title(label, fontsize=11, color=INK, weight="bold", pad=8)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(LINE)
    path = OUT / "portfolio-apercu.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    pages = render_pdf_pages()
    excel = render_excel_preview()
    bot = render_bot_simulation()
    overview = render_overview(excel, pages[0], bot)
    for p in [*pages, excel, bot, overview]:
        print(f"{p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
