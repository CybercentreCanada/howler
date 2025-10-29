# Génération de données aléatoires

Pour avoir une idée de ce à quoi ressemble Howler avec des données, et pour tester votre code, vous pouvez utiliser le
script d'aide `api/howler/odm/random_data.py`. Ce script contient des méthodes pour générer des données de test
réalistes pour tous les modèles utilisés dans Howler.

## Utilisation de base

```shell
cd ~/repos/howler/api

# Exécuter sans arguments - tous les index sont effacés et remplis avec des données de test
python howler/odm/random_data.py

# Remplir tous les index sans effacer les données existantes
python howler/odm/random_data.py all --no-wipe

# Remplir uniquement des index spécifiques
python howler/odm/random_data.py users hits analytics

# Remplir des index spécifiques sans effacer
python howler/odm/random_data.py users hits --no-wipe
```

## Index disponibles

Les index suivants peuvent être remplis avec des données de test :

- **users** - Comptes utilisateurs avec divers niveaux de permission et clés API
- **templates** - Modèles d'affichage de hits pour différentes analytiques et détections
- **overviews** - Modèles de vue d'ensemble basés sur Markdown avec support Handlebars
- **views** - Requêtes de recherche et filtres sauvegardés
- **hits** - Données d'alertes/détections incluant des bundles
- **analytics** - Définitions d'analytiques avec règles et paramètres de triage
- **actions** - Configurations d'actions automatisées
- **dossiers** - Dossiers d'enquête

## Données de test générées

### Utilisateurs

Le script crée plusieurs utilisateurs prédéfinis pour tester différents scénarios :

| Nom d'utilisateur | Mot de passe | Type | Description |
|-------------------|--------------|------|-------------|
| `admin` | `admin` (ou `$DEV_ADMIN_PASS`) | admin, user, automation_basic, automation_advanced | Accès admin complet avec plusieurs clés API |
| `user` | `user` (ou `$DEV_USER_PASS`) | user | Utilisateur standard avec clés d'impersonnalisation |
| `shawn-h` | `shawn-h` | admin, user | Utilisateur admin pour les tests |
| `goose` | `goose` | admin, user | Utilisateur admin pour les tests |
| `huey` | `huey` | user | Utilisateur standard pour les tests |

<!-- markdownlint-disable -->
??? tip "Mots de passe personnalisés"
    Vous pouvez personnaliser les mots de passe admin et utilisateur en définissant des variables d'environnement :

    ```shell
    export DEV_ADMIN_PASS="mon_mot_de_passe_securise"
    export DEV_USER_PASS="mon_mot_de_passe_utilisateur"
    python howler/odm/random_data.py users
    ```
<!-- markdownlint-enable -->

### Hits

Par défaut, le script génère **200 hits aléatoires** avec des données réalistes incluant :

- Différents types de détection et analytiques
- Différents niveaux de statut (ouvert, en cours, résolu)
- Assignations aléatoires aux utilisateurs
- Données d'évaluation (escalades et niveaux de scrutiny)
- Catégories d'événements et métadonnées

Le script crée également des **bundles** - groupes de hits liés ensemble.

### Analytiques

Le script génère des analytiques dans plusieurs catégories :

- **Analytiques existantes à partir des hits** - Les analytiques sont automatiquement créées à partir des hits générés
- **Analytiques aléatoires** (10 par défaut) - Définitions d'analytiques entièrement aléatoires
- **Analytiques basées sur des règles** - Analytiques avec règles Lucene, EQL et Sigma

Chaque analytique inclut :

- Détections
- Commentaires (au niveau de l'analytique et de la détection)
- Notebooks (si activé dans la configuration)
- Paramètres de triage avec évaluations valides
- Contributeurs et propriétaires

<!-- markdownlint-disable -->
??? info "Règles Sigma"
    Pour de meilleures données de test utilisant les règles Sigma, exécutez d'abord le générateur de règles Sigma :

    ```shell
    python howler/external/generate_sigma_rules.py
    ```
<!-- markdownlint-enable -->

### Modèles

Les modèles sont générés pour différentes analytiques et détections, incluant :

- **Modèles globaux** - Disponibles pour tous les utilisateurs
- **Modèles personnels** - Modèles spécifiques à l'utilisateur

Chaque modèle définit quels champs de hit doivent être affichés et dans quel ordre.

### Vues d'ensemble

Les modèles de vue d'ensemble utilisent la syntaxe Handlebars pour créer des vues dynamiques basées sur Markdown des
hits. Les vues d'ensemble générées incluent des exemples de :

- Rendu conditionnel basé sur le statut du hit
- Récupération de données externes via des appels API
- Affichage d'avatars utilisateur
- Badges de statut et formatage

### Actions

Des actions automatisées aléatoires sont générées avec diverses opérations telles que :

- Ajustements de priorisation
- Transitions de statut
- Mises à jour de champs
- Opérations en masse

Chaque action inclut une requête pour correspondre aux hits et une série d'opérations à effectuer.

### Vues

Des vues sauvegardées sont créées incluant :

- **Vues globales** - Requêtes partagées pour des cas d'utilisation courants
- **Vues personnelles** - Recherches sauvegardées spécifiques à l'utilisateur
- **Vues en lecture seule** - Filtres préconfigurés (par exemple, "Assigné à moi")

## Variables d'environnement

Le script respecte plusieurs variables d'environnement :

- `DEV_ADMIN_PASS` - Mot de passe pour l'utilisateur admin (défaut : `admin`)
- `DEV_USER_PASS` - Mot de passe pour le compte utilisateur (défaut : `user`)
- `HWL_PLUGIN_DIRECTORY` - Emplacement des plugins Howler (défaut : `/etc/howler/plugins`)
- `ELASTIC_HIT_SHARDS` - Nombre de shards pour l'index des hits (défini à 1 pendant la configuration)
- `ELASTIC_HIT_REPLICAS` - Nombre de réplicas pour l'index des hits (défini à 1 pendant la configuration)
- `ELASTIC_USER_REPLICAS` - Nombre de réplicas pour l'index utilisateur (défini à 1 pendant la configuration)
- `ELASTIC_USER_AVATAR_REPLICAS` - Nombre de réplicas pour l'index des avatars utilisateur (défini à 1 pendant la configuration)

## Intégration de plugins

Le générateur de données aléatoires prend en charge les plugins via la fonction `run_modifications`. Si vous avez des
plugins personnalisés qui étendent les modèles de données de Howler, ils seront automatiquement invoqués pendant la
génération de données pour remplir les champs spécifiques aux plugins.

## Cas d'utilisation

### Configuration de l'environnement de développement

Remplir rapidement une instance Howler fraîche avec des données de test réalistes :

```shell
python howler/odm/random_data.py all
```

### Tester des fonctionnalités spécifiques

Remplir uniquement les données nécessaires pour votre fonctionnalité :

```shell
# Tester les permissions utilisateur
python howler/odm/random_data.py users --no-wipe

# Tester le traitement des hits
python howler/odm/random_data.py hits analytics --no-wipe

# Tester les actions
python howler/odm/random_data.py hits actions --no-wipe
```

### Intégration continue

Utilisez le flag `--no-wipe` pour ajouter des données de test sans détruire les données existantes pendant les
exécutions de tests.
