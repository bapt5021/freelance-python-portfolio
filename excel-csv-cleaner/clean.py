"""Nettoie et fusionne des fichiers de ventes CSV/XLSX, puis produit un rapport Excel.

Exemple :
    python clean.py --input data/ --output rapport.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cleaner.excel_report import write_report
from cleaner.normalize import load_reference
from cleaner.pipeline import clean_directory

DEFAULT_REFERENCE = Path("referentiel/clients.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nettoyage et fusion de fichiers de ventes CSV/XLSX.")
    parser.add_argument("--input", required=True, type=Path, help="dossier contenant les .csv/.xlsx")
    parser.add_argument("--output", required=True, type=Path, help="rapport Excel à produire")
    parser.add_argument("--clients", type=Path, default=None,
                        help=f"référentiel des noms de clients (défaut : {DEFAULT_REFERENCE} s'il existe)")
    args = parser.parse_args(argv)

    ref_path = args.clients or (DEFAULT_REFERENCE if DEFAULT_REFERENCE.exists() else None)
    try:
        reference = load_reference(ref_path) if ref_path else None
        result = clean_directory(args.input, reference)
        write_report(result, args.output)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    s = result.stats
    print(f"Référentiel clients : {ref_path or 'aucun (noms seulement nettoyés)'}")
    print(f"Lignes lues : {s['lignes_lues']} | vides : {s['lignes_vides']} | "
          f"rejetées : {s['lignes_rejetees']} | doublons : {s['doublons']}")
    print(f"Ventes retenues : {s['ventes_retenues']} | total : {result.data['Montant'].sum():.2f} €")
    print(f"Corrections journalisées : {len(result.corrections)}")
    print(f"Rapport écrit : {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
