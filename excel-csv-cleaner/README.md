# excel-csv-cleaner

> Projet de démonstration — non réalisé pour un client.

Nettoie et fusionne plusieurs fichiers de ventes **CSV et Excel** hétérogènes, puis produit un rapport Excel
avec les données propres, un résumé mensuel et un **journal de chaque correction** (traçabilité complète).

Toutes les données sont **fictives**, générées par `generate_sample_data.py`.

## Ce que le script corrige

| Problème dans les fichiers source | Traitement |
|---|---|
| Séparateurs `;` ou `,`, encodage UTF-8 ou Windows (cp1252) | détection automatique |
| En-têtes différents (`Date vente`, `date_vente`, `Article`, `Montant (€)`…) | correspondance par synonymes |
| Dates `12/03/2026`, `2026-03-12`, `12 mars 2026`, `1er avril 2026`, vraies dates Excel | converties en ISO `AAAA-MM-JJ` |
| Montants `1234.50`, `1234,5`, `1 234,50 €`, `1.234,50` | convertis en nombres |
| Clients en casse différente, accents manquants, `&`/`et`, fautes (`Dupond`, `Garrage`) | ramenés au nom officiel du référentiel |
| Espaces parasites dans les produits | supprimés |
| Client ou produit vide | `Client inconnu` / `Non renseigné` (la vente est gardée) |
| Date ou montant vide/illisible | ligne rejetée et journalisée |
| Lignes vides | supprimées |
| Doublons (même date, client, produit, montant **après** normalisation) | supprimés, en gardant la 1re occurrence |

## Installation

```bash
cd excel-csv-cleaner
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt    # + requirements-dev.txt pour lancer les tests
```

Python 3.11 ou plus récent.

## Utilisation

```bash
python generate_sample_data.py                 # (re)crée data/ et referentiel/clients.csv
python clean.py --input data/ --output rapport.xlsx
```

Options :
- `--clients chemin.csv` : référentiel des noms de clients (une colonne `client`). Par défaut
  `referentiel/clients.csv` s'il existe ; sans référentiel, les noms sont seulement nettoyés (espaces).

## Exemple de sortie

```
Référentiel clients : referentiel/clients.csv
Lignes lues : 74 | vides : 2 | rejetées : 4 | doublons : 8
Ventes retenues : 60 | total : 38963.61 €
Corrections journalisées : 130
Rapport écrit : exemples/rapport.xlsx
```

Le fichier [`exemples/rapport.xlsx`](exemples/rapport.xlsx) contient :

1. **Donnees_nettoyees** — une ligne par vente : date ISO, client, produit, montant, fichier et ligne d'origine.
2. **Resume** — montants par mois × produit avec totaux, nombre de ventes, indicateurs de nettoyage.
3. **Journal_corrections** — fichier, ligne, champ, valeur avant, valeur après. Extrait :

| Fichier | Ligne | Champ | Avant | Après |
|---|---|---|---|---|
| ventes_boutique.csv | 2 | Date | 15 février 2026 | 2026-02-15 |
| ventes_boutique.csv | 2 | Client | MARTIN & FILS | Martin & Fils |
| ventes_boutique.csv | 3 | Montant | 820,30 € | 820.30 |
| ventes_boutique.csv | 4 | Client | Garrage Moreau | Garage Moreau |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

Les tests régénèrent les données dans un dossier temporaire et comparent le résultat à la « vérité terrain »
renvoyée par le générateur : nombre de doublons supprimés, dates ISO, montants numériques, total hors
doublons, clients ramenés au référentiel, contenu des 3 onglets, CLI.

## Structure

```
clean.py                 # CLI
cleaner/normalize.py     # dates, montants, clients, produits (fonctions pures)
cleaner/pipeline.py      # lecture CSV/XLSX, nettoyage, dédoublonnage, journal
cleaner/excel_report.py  # écriture et mise en forme du rapport
generate_sample_data.py  # données fictives + vérité terrain
```

## Limites

- Les dates numériques sont lues au format **français** (jour/mois/année) : `03/04/2026` = 3 avril.
- Un montant `1,234` ou `1.234` (un seul séparateur) est lu comme décimal (1,23) et non comme « mille deux cent… ».
- Deux ventes réellement identiques (même jour, client, produit et montant) seraient vues comme un doublon :
  en production, on s'appuierait plutôt sur un numéro de facture.
- Le rapprochement approximatif des clients (seuil 0,85) peut confondre deux noms très proches ;
  le journal permet de le vérifier.
- Seule la première feuille de chaque fichier Excel est lue ; pas de support `.xls` (ancien format).
