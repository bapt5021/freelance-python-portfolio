"""Graphiques matplotlib renvoyés en PNG (octets) pour insertion dans le PDF."""

from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")  # rendu sans affichage (serveur, CI)
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Palette sobre et lisible (bleu / orange : distinguables par les daltoniens).
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


def _style(ax) -> None:
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
    ax.set_axisbelow(True)


def _to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def errors_per_hour_chart(old: pd.Series, new: pd.Series, old_label: str, new_label: str) -> bytes:
    """Barres groupées : erreurs par heure, ancien vs nouveau fichier."""
    hours = old.index.union(new.index)
    old, new = old.reindex(hours, fill_value=0), new.reindex(hours, fill_value=0)
    x = range(len(hours))
    width = 0.4

    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    ax.bar([i - width / 2 for i in x], old.values, width, label=old_label,
           color=SERIES_1, edgecolor="white", linewidth=1)
    ax.bar([i + width / 2 for i in x], new.values, width, label=new_label,
           color=SERIES_2, edgecolor="white", linewidth=1)

    _style(ax)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_xticks(list(x))
    multi_day = hours.normalize().nunique() > 1
    ax.set_xticklabels([h.strftime("%d/%m %Hh" if multi_day else "%Hh") for h in hours])
    ax.set_ylabel("Erreurs", color=TEXT_SECONDARY, fontsize=8)
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_PRIMARY, loc="upper left")
    ax.set_title("Erreurs par heure", loc="left", fontsize=10, color=TEXT_PRIMARY)
    return _to_png(fig)


def top_errors_chart(top: pd.DataFrame) -> bytes:
    """Barres horizontales : messages d'erreur les plus fréquents (le 1er en haut)."""
    labels = [textwrap.shorten(m, 70, placeholder="…") for m in top["message"]][::-1]
    values = list(top["occurrences"])[::-1]

    fig, ax = plt.subplots(figsize=(7.2, 0.45 * max(len(values), 1) + 0.8))
    bars = ax.barh(labels, values, color=SERIES_1, height=0.6)
    ax.bar_label(bars, padding=3, fontsize=8, color=TEXT_PRIMARY)
    _style(ax)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelcolor=TEXT_PRIMARY)
    ax.set_title(f"Top {len(values)} des messages d'erreur", loc="left",
                 fontsize=10, color=TEXT_PRIMARY)
    return _to_png(fig)
