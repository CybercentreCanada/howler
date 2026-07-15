# Ingénieurs en détection

Vous venez d'écrire une analyse qui détecte une activité suspecte et vous aimeriez que votre centre d'opérations de sécurité (SOC) en bénéficie. Dans Howler, un événement intéressant est appelé un hit. Le terme alerte est réservé aux hits qui nécessitent un triage.

Pour créer un nouveau hit, produisez un objet JSON dans lequel vous avez normalisé les données de l'événement selon Elastic Common Schema (ECS). Nous procédons ainsi pour que les analystes de triage disposent d'un schéma unique à apprendre quelle que soit la source des alertes, ce qui leur facilitera grandement la tâche.

## Champs spécifiques à Howler

Ensuite, vous devez remplir certains champs spécifiques à Howler :

### Champs requis

| Champ | Description | Notes |
|-------|-------------|-------|
| `howler.analytic` | Le produit qui effectue la détection. Certains produits analytiques exécuteront plusieurs détections distinctes. | Doit contenir uniquement des lettres et des espaces pour les meilleures pratiques |

### Champs générés automatiquement

Ces champs sont automatiquement remplis par Howler s'ils ne sont pas fournis :

| Champ | Description | Comportement par défaut |
|-------|-------------|-------------------------|
| `howler.id` | Un identifiant unique pour le hit | UUID généré automatiquement |
| `howler.hash` | Un hash utilisé pour dédupliquer les hits | Auto-généré à partir de l'analytique, de la détection et des données brutes si non fourni |
| `event.created` | Horodatage de création de l'événement | Défini à l'heure actuelle si non fourni |

### Champs recommandés

Bien que non strictement requis, ces champs sont fortement recommandés pour un triage efficace :

| Champ | Description | Défaut | Notes |
|-------|-------------|--------|-------|
| `howler.detection` | Un identifiant court et unique pour la détection spécifique | Aucun | Doit contenir uniquement des lettres et des espaces pour les meilleures pratiques |
| `howler.outline.threat` | L'identifiant qui représente le mieux l'attaquant | Aucun | Peut être une IP, une adresse électronique, etc. |
| `howler.outline.target` | L'identifiant qui représente le mieux la victime | Aucun | Une IP, un domaine, une adresse électronique, etc. |
| `howler.outline.indicators` | Une liste libre d'indicateurs de compromission (IoC) | Liste vide | Généralement des IPs, des domaines et des hashes |
| `howler.outline.summary` | Un résumé expliquant l'activité détectée | Aucun | Décrivez l'événement en supposant que la détection est correcte |
| `howler.data` | Une liste de données d'événement brut avant normalisation | Liste vide | Facilite les enquêtes en dehors de Howler |
| `howler.escalation` | Le niveau d'escalade du hit | `hit` | Valeurs valides : `miss`, `hit`, `alert`, `evidence` |
| `howler.status` | Le statut actuel du hit | `open` | Valeurs valides : `open`, `in-progress`, `on-hold`, `resolved` |
| `howler.scrutiny` | Niveau de scrutiny appliqué au hit | `unseen` | Valeurs valides : `unseen`, `surveyed`, `scanned`, `inspected`, `investigated` |

### Niveaux d'escalade

Howler utilise des niveaux d'escalade (`howler.escalation`) pour catégoriser les hits :

- `miss` - L'événement est évalué comme n'étant pas lié à la détection (faux-positif).
- `hit` - (par défaut) L'événement peut ne pas être très fiable sans contexte supplémentaire.
- `alert` - L'événement doit être évalué par un analyste de triage.
- `evidence` - L'événement a été évalué comme étant lié à la détection (vrai-positif).

Vous pouvez promouvoir certains hits en alertes immédiates au moment de la création si l'on s'attend à ce que tous les hits méritent d'être triés.

Une fois l'objet JSON complété, utilisez le [client Howler](/howler/developer/client/) pour créer un nouveau hit. Ce hit sera immédiatement disponible pour les analystes de triage à partir de l'interface utilisateur de Howler.

## Exemple : Créer un hit

Tout d'abord, assurez-vous d'avoir installé le client Howler et un moyen de vous authentifier auprès de Howler (voir [Authentification et connexion](/howler/developer/client/#authentication--connection) pour plus de détails).

```python
from howler_client import get_client
from hashlib import sha256

# Se connecter à Howler
client = get_client("https://votre-instance-howler.com", apikey=(USERNAME, APIKEY))

# Créer un hit
hit = {
    "howler": {
        "analytic": "Détecteur de connexions suspectes",
        "detection": "Pic de connexions échouées",
        "hash": sha256(b"user123-2024-10-22-failed-logins").hexdigest(),
        "escalation": "alert",  # Promouvoir en alerte pour triage
        "outline": {
            "threat": "203.0.113.42",
            "target": "user123@example.com",
            "indicators": ["203.0.113.42"],
            "summary": "Le compte utilisateur a subi 15 tentatives de connexion échouées depuis une seule IP en 5 minutes",
        },
        "data": [{"raw_event": "données_log_originales_ici"}],
    },
    "source": {"ip": "203.0.113.42"},
    "user": {"email": "user123@example.com"},
    "event": {"category": ["authentication"], "outcome": "failure"},
}

response = client.hit.create(hit)
print(f"Hit créé : {response['valid'][0]['id']}")
```

Pour plus d'exemples et une utilisation détaillée, consultez le [Guide de développement client](/howler/developer/client/#creating-hits).

## Page d'analyse

La section Analytics de l'interface utilisateur de Howler fournit une page de support pour les analyses et les
détections individuelles. Elle contient des informations utiles à la fois pour l'auteur d'une analyse ou d'une
détection et pour les analystes de triage qui enquêtent sur les hits.

### Vue d'ensemble

Ici, vous êtes encouragé à fournir de la documentation de votre analytique en Markdown. Celle-ci devrait fournir plus
de détails sur le fonctionnement de l'analyse ou de la détection, sur ce qu'elle recherche et sur la manière de valider
les hits.

Des mesures sont automatiquement générées pour donner un aperçu des performances. Un taux de faux positifs très élevé
peut être le signe que la détection doit être améliorée. En revanche, un taux élevé de vrais positifs peut justifier
que les hits soient automatiquement promus au rang d'alertes.

### Commentaires

Dans cet onglet, les utilisateurs peuvent laisser des commentaires sur une analyse ou une détection. Considérez ceci
comme votre ligne de communication avec l'utilisateur final.

### Commentaires sur les hits

À partir de cet onglet, vous pouvez consulter tous les commentaires laissés sur des hits spécifiques afin de mieux
comprendre ce que les analystes de triage se signalent les uns aux autres.

### Carnets de notes

Si vos analystes de triage ont fréquemment besoin d'enquêter sur des alertes en dehors de Howler, vous pouvez créer un
lien vers un carnet de notes Jupyter. Cela signifie qu'un bouton apparaîtra dans l'interface utilisateur de Howler.
Lorsqu'un utilisateur clique sur le bouton, il est dirigé vers JupyterHub avec le Notebook spécifié ouvert et le hit
spécifique chargé, ce qui permet aux requêtes d'être pré-remplies avec des valeurs pertinentes.

### Paramètres de triage

Configurez quelles options d'évaluation sont valides pour votre analytique. Par exemple, si votre analytique ne détecte
que des activités malveillantes, vous pourriez limiter les évaluations à `compromise`, `attempt` ou `mitigated` - en
excluant des options comme `false-positive` ou `legitimate` qui n'ont pas de sens pour votre logique de détection.

Cela aide à guider les analystes vers des évaluations appropriées et maintient la cohérence dans la façon dont les hits
sont triés.

## Documentation connexe

- **[Guide de développement client](/howler/developer/client/)** - Guide complet sur l'utilisation du client
  Python Howler, y compris l'installation, l'authentification et les opérations avancées sur les hits
- **[Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/index.html)** - Documentation officielle
  Elastic pour la référence des champs ECS et les directives
- **Référence du schéma Hit** - Consultez le schéma complet des hits Howler dans votre instance Howler sous Aide →
  Schéma Hit
- **[Documentation API](https://votre-instance-howler.com/api/doc)** - Documentation API interactive pour votre
  instance Howler (remplacez par votre URL réelle)
