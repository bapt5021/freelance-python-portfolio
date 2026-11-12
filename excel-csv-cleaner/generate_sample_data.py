"""Génère des données de ventes 100 % fictives pour la démo excel-csv-cleaner.

Trois fichiers sont produits dans data/ :
  - ventes_boutique.csv : séparateur « ; », encodage Windows (cp1252), montants « 1 234,50 »
  - ventes_web.csv      : séparateur « , », UTF-8, montants avec point ou virgule
  - ventes_export.xlsx  : vraies dates Excel et nombres, mêlés de quelques textes

Défauts introduits volontairement : doublons (entre fichiers ou dans un même
fichier), dates en formats mélangés, noms de clients mal orthographiés ou en
casse différente, cellules vides, lignes vides, montants illisibles.

La fonction generate() renvoie la « vérité terrain » (ventes uniques et
valides, nombre de doublons…) : les tests s'en servent pour vérifier le
nettoyage sans dépendre de valeurs codées en dur.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

# Clients fictifs : nom canonique -> variantes « sales » rencontrées dans les fichiers.
CLIENTS: dict[str, list[str]] = {
    "Dupont SARL": ["DUPONT SARL", "dupont sarl", "Dupond SARL", "  Dupont  SARL "],
    "Martin & Fils": ["Martin et Fils", "MARTIN & FILS", "Martn & Fils"],
    "Boulangerie Leroy": ["boulangerie leroy", "Boulangerie Lerroy", "BOULANGERIE LEROY"],
    "Café des Arts": ["Cafe des Arts", "café des arts", "Café des  Arts"],
    "Garage Moreau": ["garage moreau", "Garrage Moreau", "GARAGE MOREAU "],
    "Librairie Fontaine": ["librairie fontaine", "Librairie Fontaines", "LIBRAIRIE FONTAINE"],
}

# Produits fictifs et fourchette de prix (en euros).
PRODUITS: dict[str, tuple[int, int]] = {
    "Abonnement Basic": (29, 99),
    "Abonnement Pro": (99, 399),
    "Formation": (450, 2400),
    "Maintenance": (120, 900),
    "Licence": (250, 1500),
}

CLIENT_INCONNU = "Client inconnu"
PRODUIT_INCONNU = "Non renseigné"

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

# Nom de fichier -> style de rendu des valeurs.
FICHIERS = {
    "ventes_boutique.csv": "boutique",
    "ventes_web.csv": "web",
    "ventes_export.xlsx": "export",
}

# En-têtes volontairement différents d'un fichier à l'autre.
ENTETES = {
    "boutique": ["Date", "Client", "Produit", "Montant"],
    "web": ["date_vente", "nom_client", "produit", "montant_eur"],
    "export": ["Date vente", "Client", "Article", "Montant (€)"],
}

Sale = tuple[date, str, str, float]  # (date, client canonique, produit, montant)


@dataclass
class GroundTruth:
    """Ce que le nettoyage doit retrouver."""

    sales: list[Sale]      # ventes uniques et exploitables
    n_duplicates: int      # lignes en double ajoutées
    n_rejected: int        # lignes inexploitables (date ou montant manquant/illisible)
    n_blank: int           # lignes entièrement vides

    @property
    def total(self) -> float:
        return round(sum(s[3] for s in self.sales), 2)


# --- Rendu « sale » des valeurs ------------------------------------------------

def _date_longue(d: date) -> str:
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS_FR[d.month - 1]} {d.year}"


def _render_date(d: date, style: str, rng: random.Random):
    if style == "export" and rng.random() < 0.7:
        return d  # vraie date Excel
    choix = rng.choice(["dmy", "iso", "long"])
    if choix == "dmy":
        return d.strftime("%d/%m/%Y")
    if choix == "iso":
        return d.isoformat()
    return _date_longue(d)


def _montant_fr(x: float) -> str:
    """1234.5 -> '1 234,50'"""
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def _render_montant(x: float, style: str, rng: random.Random):
    if style == "boutique":
        return rng.choice([_montant_fr(x), str(x).replace(".", ","), f"{x:.2f} €".replace(".", ",")])
    if style == "web":
        return rng.choice([f"{x:.2f}", str(x), f"{x:.2f}".replace(".", ",")])
    # export (xlsx)
    return x if rng.random() < 0.75 else _montant_fr(x)


def _render_client(client: str, rng: random.Random) -> str:
    if client == CLIENT_INCONNU:
        return ""
    return rng.choice(CLIENTS[client]) if rng.random() < 0.4 else client


def _render_produit(produit: str, rng: random.Random) -> str:
    if produit == PRODUIT_INCONNU:
        return ""
    r = rng.random()
    if r < 0.08:
        return f" {produit}"
    if r < 0.15:
        return produit.replace(" ", "  ") if " " in produit else f"{produit}  "
    return produit


def _render(sale: Sale, style: str, rng: random.Random) -> list:
    d, client, produit, montant = sale
    return [
        _render_date(d, style, rng),
        _render_client(client, rng),
        _render_produit(produit, rng),
        _render_montant(montant, style, rng),
    ]


# --- Génération ------------------------------------------------------------------

def _random_sale(rng: random.Random) -> Sale:
    d = date(2026, 1, 1) + timedelta(days=rng.randrange(120))  # janvier -> avril 2026
    client = rng.choice(list(CLIENTS))
    produit = rng.choice(list(PRODUITS))
    lo, hi = PRODUITS[produit]
    return (d, client, produit, round(rng.uniform(lo, hi), 2))


def generate(out_dir: Path, ref_path: Path | None = None, seed: int = 42,
             n_sales: int = 60, n_duplicates: int = 8) -> GroundTruth:
    """Écrit les fichiers d'entrée dans out_dir et renvoie la vérité terrain."""
    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ventes uniques (aucune paire identique, sinon un « doublon » serait légitime).
    sales: list[Sale] = []
    while len(sales) < n_sales:
        s = _random_sale(rng)
        if s not in sales:
            sales.append(s)
    # Deux cas de cellules vides récupérables : client vide, produit vide.
    sales[3] = (sales[3][0], CLIENT_INCONNU, sales[3][2], sales[3][3])
    sales[7] = (sales[7][0], sales[7][1], PRODUIT_INCONNU, sales[7][3])

    rows: dict[str, list[list]] = {name: [] for name in FICHIERS}
    names = list(FICHIERS)

    # 2. Chaque vente va dans un fichier au hasard.
    for s in sales:
        name = rng.choice(names)
        rows[name].append(_render(s, FICHIERS[name], rng))

    # 3. Doublons : la même vente réapparaît (même fichier ou autre), formatée autrement.
    for s in rng.sample(sales, n_duplicates):
        name = rng.choice(names)
        rows[name].append(_render(s, FICHIERS[name], rng))

    # 4. Lignes inexploitables : montant vide, montant illisible, date vide.
    defauts = [(3, ""), (3, ""), (3, "N/A"), (0, "")]  # (colonne, valeur forcée)
    for col, valeur in defauts:
        s = _random_sale(rng)
        name = rng.choice(names)
        ligne = _render(s, FICHIERS[name], rng)
        ligne[col] = valeur
        rows[name].append(ligne)

    for name in names:
        rng.shuffle(rows[name])

    # 5. Lignes entièrement vides au milieu de deux fichiers.
    n_blank = 0
    for name in ("ventes_boutique.csv", "ventes_export.xlsx"):
        rows[name].insert(rng.randrange(1, len(rows[name])), [])
        n_blank += 1

    # 6. Écriture des fichiers.
    for name, style in FICHIERS.items():
        path = out_dir / name
        if style == "export":
            wb = Workbook()
            ws = wb.active
            ws.title = "Export"
            ws.append(ENTETES[style])
            for r in rows[name]:
                ws.append(r)
            wb.save(path)
        else:
            delim, enc = (";", "cp1252") if style == "boutique" else (",", "utf-8")
            with open(path, "w", newline="", encoding=enc) as f:
                w = csv.writer(f, delimiter=delim)
                w.writerow(ENTETES[style])
                w.writerows(rows[name])

    # 7. Référentiel des noms de clients officiels (utilisé pour corriger les fautes).
    if ref_path is not None:
        ref_path = Path(ref_path)
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ref_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["client"])
            w.writerows([c] for c in CLIENTS)

    return GroundTruth(sales=sales, n_duplicates=n_duplicates,
                       n_rejected=len(defauts), n_blank=n_blank)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", default="data", type=Path)
    parser.add_argument("--referentiel", default="referentiel/clients.csv", type=Path)
    parser.add_argument("--seed", default=42, type=int)
    args = parser.parse_args()

    truth = generate(args.output_dir, args.referentiel, seed=args.seed)
    print(f"Fichiers écrits dans {args.output_dir}/ (référentiel : {args.referentiel})")
    print(f"  ventes uniques attendues : {len(truth.sales)}")
    print(f"  doublons introduits      : {truth.n_duplicates}")
    print(f"  lignes inexploitables    : {truth.n_rejected}")
    print(f"  lignes vides             : {truth.n_blank}")
    print(f"  total attendu            : {truth.total:.2f} €")


if __name__ == "__main__":
    main()
