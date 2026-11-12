# log-report

> Projet de démonstration — non réalisé pour un client.

Compare deux versions d'un fichier `.log` et produit :
- le **diff** (lignes ajoutées / supprimées, avec numéros de ligne) ;
- des **statistiques** : nombre d'erreurs par heure, top 5 des messages d'erreur ;
- un **rapport PDF** de 2 pages : résumé rédigé automatiquement, chiffres clés, 2 graphiques, extrait du diff.

Les logs sont **fictifs**, générés par `generate_sample_data.py` (application web imaginaire ; le même fichier
capturé avant et après une rotation et le déploiement d'une « v2.4 » qui introduit une nouvelle erreur).

## Format de log attendu

```
2026-11-10 14:00:00 INFO Déploiement de la version 2.4 terminé
2026-11-10 15:12:40 ERROR KeyError 'customer_id' dans OrderSerializer.to_dict
```
Horodatage `AAAA-MM-JJ HH:MM:SS` (millisecondes et `T` acceptés), niveau `INFO` / `WARNING` (ou `WARN`) / `ERROR`,
puis le message. Les autres lignes (ex. traces Python) sont comptées comme « non reconnues » mais restent dans le diff.

## Installation

```bash
cd log-report
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt    # + requirements-dev.txt pour les tests
```

Python 3.11 ou plus récent.

## Utilisation

```bash
python generate_sample_data.py                      # crée data/old.log et data/new.log
python report.py data/old.log data/new.log --pdf rapport.pdf
python report.py data/old.log data/new.log --pdf rapport.pdf --export-dir exemples/
```

Options : `--export-dir` écrit `diff.txt` (diff complet), `erreurs_par_heure.csv` et `top_erreurs.csv` ;
`--top N` change la taille du classement (5 par défaut).

## Exemple de sortie

```
== Erreurs par heure (new.log) ==
2026-11-10 14h    4  ####
2026-11-10 15h   10  ##########
2026-11-10 16h    6  ######

== Top 5 des messages d'erreur (new.log) ==
1. (15) Timeout de connexion à la base db-<N> après <N> s
2. (8) KeyError 'customer_id' dans OrderSerializer.to_dict
3. (6) Erreur SMTP <N> lors de l'envoi à <IP>
4. (4) Échec du paiement : transaction <ID> refusée
5. (3) Fichier introuvable : /data/import/clients.csv

== Résumé ==
- new.log contient 235 entrées dont 39 erreurs (16.6 %), contre 180 entrées et 19 erreurs (10.6 %) pour old.log.
- Le diff fait apparaître 106 ligne(s) ajoutée(s) et 43 ligne(s) supprimée(s).
- Pic d'erreurs dans new.log : 10 erreur(s) le 10/11/2026 entre 15h et 16h.
```

Fichiers produits : [`exemples/rapport.pdf`](exemples/rapport.pdf), [`exemples/diff.txt`](exemples/diff.txt),
[`exemples/erreurs_par_heure.csv`](exemples/erreurs_par_heure.csv), [`exemples/top_erreurs.csv`](exemples/top_erreurs.csv).

**Regroupement des messages** : pour que « Timeout … db-01 » et « Timeout … db-02 » comptent comme la même erreur,
les parties variables sont remplacées par des marqueurs : adresses IP → `<IP>`, identifiants hexadécimaux → `<ID>`,
nombres → `<N>`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

- diff exact sur des fixtures connues (`tests/fixtures/mini_old.log`, `mini_new.log`), ligne modifiée, lignes répétées ;
- statistiques vérifiées sur `tests/fixtures/mini_stats.log` (erreurs par heure, heure à 0 incluse, top 5 avec ex æquo) ;
- CLI, exports, et PDF valide de 2 pages au maximum.

## Structure

```
report.py                # CLI
logreport/parsing.py     # lecture et découpage des lignes
logreport/diff.py        # diff ligne à ligne (difflib)
logreport/stats.py       # erreurs par heure, top des messages
logreport/charts.py      # graphiques matplotlib
logreport/pdf.py         # rapport PDF (reportlab)
generate_sample_data.py  # logs fictifs
```

## Limites

- Diff **ligne à ligne exact** : deux exécutions différentes (horodatages différents) apparaissent entièrement
  modifiées. Pour comparer deux versions d'une application, il faudrait comparer les messages sans l'horodatage.
- `difflib` convient à quelques dizaines de milliers de lignes ; au-delà, `diff` système ou un traitement en flux
  serait plus adapté.
- Un seul format de log est reconnu (regex dans `parsing.py`, facile à adapter).
- Le regroupement par modèle peut fusionner des messages qui ne diffèrent que par un nombre significatif
  (ex. codes HTTP 404 et 500).
- Les statistiques et le top 5 portent sur le **nouveau** fichier ; le graphique horaire compare les deux.
- Le PDF borne l'extrait du diff à 12 lignes pour tenir sur 2 pages ; le diff complet est dans l'export texte.
