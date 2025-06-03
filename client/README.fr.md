# Bibliothèque client de Howler

La bibliothèque client Howler facilite l'émission de requêtes à Howler.

## Exécution des tests

1. Préparez l'interface howler-api :
    1. Démarrer les dépendances
    1. `howler-api > python howler/app.py`
    1. `howler-api > python howler/odm/random_data.py`
2. Exécutez les tests d'intégration Java :
    1. `howler-client > mvn verify`
3. Exécuter les tests d'intégration python :
    1. `howler-client/python > python -m venv env`
    1. `howler-client/python > . env/bin/activate`
    1. `howler-client/python > pip install -r requirements.txt`
    1. `howler-client/python > pip install -r test/requirements.txt`
    1. `howler-client/python > pip install -e .`
    1. `howler-client/python > pytest -s -v test`
