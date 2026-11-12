"""Compare deux fichiers .log et produit diff, statistiques et rapport PDF.

Exemple :
    python report.py old.log new.log --pdf rapport.pdf
    python report.py old.log new.log --pdf rapport.pdf --export-dir exemples/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from logreport.diff import diff_lines, format_diff
from logreport.parsing import parse_log
from logreport.pdf import ReportData, build_pdf, summary_sentences
from logreport.stats import errors_per_hour, level_counts, top_errors

PREVIEW_LINES = 10  # lignes de diff affichées dans le terminal


def analyse(old_path: Path, new_path: Path, top_n: int = 5) -> ReportData:
    old, new = parse_log(old_path), parse_log(new_path)
    return ReportData(
        old=old, new=new,
        diff=diff_lines(old.lines, new.lines),
        old_counts=level_counts(old.entries), new_counts=level_counts(new.entries),
        old_per_hour=errors_per_hour(old.entries), new_per_hour=errors_per_hour(new.entries),
        top=top_errors(new.entries, top_n),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff, statistiques et rapport PDF de deux fichiers .log.")
    parser.add_argument("old", type=Path, help="ancienne version du log")
    parser.add_argument("new", type=Path, help="nouvelle version du log")
    parser.add_argument("--pdf", type=Path, help="chemin du rapport PDF à produire")
    parser.add_argument("--export-dir", type=Path,
                        help="dossier où écrire diff.txt, erreurs_par_heure.csv et top_erreurs.csv")
    parser.add_argument("--top", type=int, default=5, help="nombre de messages d'erreur à classer (défaut 5)")
    args = parser.parse_args(argv)

    for p in (args.old, args.new):
        if not p.is_file():
            print(f"Erreur : fichier introuvable : {p}", file=sys.stderr)
            return 1

    d = analyse(args.old, args.new, args.top)
    diff_text = format_diff(d.diff, args.old.name, args.new.name)

    # --- Sortie terminal ---
    print("== Diff ==")
    lines = diff_text.splitlines()
    print("\n".join(lines[:3 + PREVIEW_LINES]))
    if len(lines) > 3 + PREVIEW_LINES:
        print(f"... ({len(lines) - 3 - PREVIEW_LINES} lignes de plus"
              f"{', voir diff.txt' if args.export_dir else ', utilisez --export-dir pour tout exporter'})")

    print(f"\n== Erreurs par heure ({args.new.name}) ==")
    for hour, n in d.new_per_hour.items():
        print(f"{hour:%Y-%m-%d %H}h  {n:3d}  {'#' * n}")

    print(f"\n== Top {args.top} des messages d'erreur ({args.new.name}) ==")
    for i, row in d.top.iterrows():
        print(f"{i + 1}. ({row['occurrences']}) {row['message']}")

    print("\n== Résumé ==")
    for s in summary_sentences(d):
        print(f"- {s}")

    # --- Fichiers produits ---
    if args.export_dir:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        (args.export_dir / "diff.txt").write_text(diff_text, encoding="utf-8")
        d.new_per_hour.rename_axis("heure").to_csv(args.export_dir / "erreurs_par_heure.csv")
        d.top.to_csv(args.export_dir / "top_erreurs.csv", index=False)
        print(f"\nExports écrits dans {args.export_dir}/")
    if args.pdf:
        build_pdf(d, args.pdf)
        print(f"Rapport PDF écrit : {args.pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
