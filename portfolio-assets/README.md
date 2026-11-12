# portfolio-assets

Visuels du portfolio, **tous générés à partir des fichiers réellement produits par les démonstrations**
(données 100 % fictives). Aucun visuel n'est une maquette inventée.

| Fichier | Nature | Source |
|---|---|---|
| `log-report-page-1.png`, `log-report-page-2.png` | **Rendu exact** des pages du PDF | `log-report/exemples/rapport.pdf` |
| `excel-csv-cleaner-apercu.png` | **Rendu des cellules** du classeur (pas une capture d'Excel : aucun tableur n'était disponible) | `excel-csv-cleaner/exemples/rapport.xlsx` |
| `telegram-alert-bot-simulation.png` | **Simulation** : conversation produite par les vrais handlers avec de faux objets Telegram, sans réseau ni token ; émojis remplacés par des symboles | `telegram-alert-bot/exemples/simulation.json` |
| `portfolio-apercu.png` | Planche des trois visuels ci-dessus | — |

Chaque image porte elle-même la mention de sa nature (rendu, simulation, données fictives).

## Régénérer

Depuis la racine du dépôt, après avoir exécuté les démos (et `python simulate.py --json exemples/simulation.json`
dans `telegram-alert-bot/`) :

```bash
python3 -m venv .venv-assets
.venv-assets/bin/pip install -r portfolio-assets/requirements.txt
.venv-assets/bin/python portfolio-assets/generer_visuels.py
```
