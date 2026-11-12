# telegram-alert-bot

> Projet de démonstration — non réalisé pour un client.

Bot Telegram qui surveille un fichier CSV de mesures (`horodatage, capteur, valeur`) et **envoie une alerte**
quand la dernière valeur d'un capteur dépasse un seuil. Le seuil se règle depuis Telegram.

Les mesures sont **fictives** (températures de locaux techniques), générées par `generate_sample_data.py`.

## Commandes

| Commande | Effet |
|---|---|
| `/start` | active les alertes pour ce chat |
| `/aide` | liste des commandes |
| `/statut` | seuil, fréquence de vérification, dernière valeur de chaque capteur (🟢 / 🔴) |
| `/seuil <valeur>` | change le seuil (`/seuil 30`, `/seuil 30.5`, `/seuil 30,5`) ; sans valeur : affiche le seuil |

Une **tâche planifiée** relit le CSV toutes les N minutes. Pour chaque capteur, si la mesure la plus récente est
**strictement supérieure** au seuil, une alerte part vers tous les chats ayant fait `/start` :

```
⚠️ Seuil 30 dépassé :
• salle-serveur-2 : 34.2 (12/11/2026 08:00)
```

Une même mesure n'est signalée qu'une fois ; changer le seuil remet ce suivi à zéro.

## 1. Créer un bot avec BotFather

1. Dans Telegram, ouvrez une conversation avec **@BotFather** (compte officiel, coche bleue).
2. Envoyez `/newbot`, choisissez un nom affiché, puis un identifiant se terminant par `bot` (ex. `demo_alertes_bot`).
3. BotFather répond avec un **token** du type `123456789:AA…`. Ce token donne le contrôle total du bot :
   ne le partagez pas et ne le commitez jamais. S'il fuite : `/revoke` dans BotFather.

## 2. Installer et configurer

```bash
cd telegram-alert-bot
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # puis éditez .env et collez votre token
python generate_sample_data.py     # crée mesures.csv
```

Variables (dans `.env` ou dans l'environnement) :

| Variable | Défaut | Rôle |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — (obligatoire) | token BotFather |
| `MESURES_CSV` | `mesures.csv` | fichier surveillé |
| `INTERVALLE_MINUTES` | `5` | fréquence de vérification (décimales acceptées : `0.5` = 30 s) |
| `SEUIL_INITIAL` | `30` | seuil au démarrage |
| `ALLOWED_CHAT_IDS` | vide (tout le monde) | identifiants de chats autorisés, séparés par des virgules |

`.env` est dans le `.gitignore`. Le bot masque aussi les logs de `httpx`, qui contiendraient le token dans les URL.

## 3. Lancer le bot

```bash
python bot.py
```

Envoyez `/start` au bot dans Telegram. Avec les données générées, `salle-serveur-2` dépasse 30 : une alerte
arrive environ 10 s après le démarrage, puis à chaque nouvelle mesure en dépassement.

Pour simuler de nouvelles mesures pendant que le bot tourne :

```bash
python generate_sample_data.py --ajouter                          # valeurs normales
python generate_sample_data.py --ajouter --pic local-onduleur     # avec un dépassement
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

Les tests **n'utilisent pas le réseau** (toute connexion socket est bloquée par `tests/conftest.py`) :
logique de seuil (égalité, dernière mesure, pas de doublon), parsing de `/seuil` (valeurs valides et invalides),
lecture du CSV (lignes invalides, colonne manquante, fichier absent), handlers et tâche planifiée avec des objets
simulés (`AsyncMock`), configuration, et construction de l'application (commandes et intervalle du job).

## Structure

```
bot.py                   # configuration, commandes, tâche planifiée, lancement
alerting.py              # logique pure : CSV, seuil, messages (sans Telegram)
generate_sample_data.py  # mesures.csv fictif, option --ajouter
.env.example             # modèle de configuration (sans token)
```

## Limites

- **État en mémoire** : seuil, abonnés et alertes déjà envoyées sont perdus au redémarrage
  (python-telegram-bot propose `PicklePersistence` pour les conserver).
- Un seul seuil pour tous les capteurs ; pas de seuil bas ni d'alerte de retour à la normale.
- Sans `ALLOWED_CHAT_IDS`, **n'importe qui** trouvant le bot peut s'abonner et changer le seuil.
- Pas de commande de désabonnement ; un chat qui bloque le bot est retiré automatiquement.
- Le CSV est relu entièrement à chaque passage : adapté à quelques milliers de lignes, pas à un historique très long.
- Mode *polling* (simple à lancer partout) ; un déploiement en production utiliserait plutôt un webhook.
