<!-- docs/ingestion/authentication.fr.md -->

# Authentification de Howler

L'API de Howler prend en charge un certain nombre d'approches d'authentification lors de l'accès à l'API. Ce document présente les
différentes approches et explique comment utiliser chacune d'entre elles.

## Types d'authentification

Il existe quatre méthodes d'authentification que l'on peut utiliser pour se connecter à l'API howler:

1. Nom d'utilisateur et mot de passe
2. Nom d'utilisateur et clé API
3. Nom d'utilisateur et clé d'application (après connexion)
4. Jeton d'accès OAuth

Nous allons maintenant présenter les cas d'utilisation de chaque type d'authentification.

### Authentification par nom d'utilisateur/mot de passe

L'authentification par nom d'utilisateur et mot de passe est la méthode d'authentification la plus simple et la moins sûre. Il est peu probable qu'elle soit activée
dans un environnement de production, elle permet aux utilisateurs de se connecter facilement à l'API Howler et d'effectuer des modifications en tant qu'utilisateur donné,
sans avoir à se soucier de créer des clés API ou d'utiliser un fournisseur OAuth comme Keycloak ou Azure. Les utilisateurs peuvent se connecter
en utilisant l'authentification par nom d'utilisateur et mot de passe de l'une des deux manières suivantes :

#### Appel direct au point de terminaison requis (mot de passe)

C'est de loin la méthode la plus simple. Il suffit d'ajouter un en-tête d'autorisation de base à la requête HTTP que vous souhaitez effectuer, et tout est pris en charge.
que vous voulez faire, et tout est pris en charge:

```bash
echo -n "user:user" | base64 -w0
# -> dXNlcjp1c2Vy
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic dXNlcjp1c2Vy
```

#### Échange contre un jeton d'application (mot de passe)

Il s'agit d'une approche un peu plus complexe, mais qui présente l'avantage de ne pas exposer le nom d'utilisateur et le mot de passe à chaque demande.
à chaque requête. Vous pouvez utiliser le point de terminaison `v1/auth/login` pour échanger votre nom d'utilisateur et votre mot de passe contre un jeton d'application. Le jeton
fonctionne de la même manière qu'un jeton d'accès OAuth - vous le fournissez à chaque requête ultérieure, et il vous authentifie jusqu'à ce que le jeton expire.
jusqu'à ce que le jeton expire.

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "user": "user",
  "password": "user"
}
```

Le résultat sera quelque chose comme:

```json
{
  "api_error_message": "",
  "api_response": {
    "app_token": "user:5791a142067745c3af51d6596da7da8f86357a9fa92ad78d1ce118ea7d89d34e",
    "provider": null,
    "refresh_token": null
  },
  "api_server_version": "0.0.0.dev0",
  "api_status_code": 200
}
```

Utilisation de ce jeton dans un autre appel d'API:

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer user:5791a142067745c3af51d6596da7da8f86357a9fa92ad78d1ce118ea7d89d34e
```

### Authentification par nom d'utilisateur/clé API

L'authentification par nom d'utilisateur et clé API fonctionne en grande partie de la même manière que l'authentification par nom d'utilisateur/mot de passe du point de vue du client.
Du côté du serveur, cependant, les clés API présentent plusieurs avantages essentiels. Tout d'abord, elles peuvent être facilement révoquées par l'utilisateur.
Deuxièmement, leurs privilèges peuvent être limités, n'autorisant qu'un sous-ensemble de permissions.

Il existe deux méthodes d'authentification, reflétant le nom d'utilisateur et le mot de passe:

#### Appel direct au point de terminaison requis (clé API)

Il suffit d'ajouter un en-tête d'autorisation de base contenant le nom d'utilisateur et la clé API à la requête HTTP que vous souhaitez effectuer, et
tout est pris en charge:

```bash
# note the format is <username>:<apikeyname>:<secret>
echo -n "user:devkey:user" | base64 -w0
# -> dXNlcjpkZXZrZXk6dXNlcg==
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic dXNlcjpkZXZrZXk6dXNlcg==
```

#### Échange contre un jeton d'application (clé API)

Vous pouvez également utiliser le point de terminaison `v1/auth/login` pour échanger votre nom d'utilisateur et votre clé API contre un jeton d'application. Le jeton
fonctionne de la même manière qu'un jeton d'accès OAuth - vous le fournissez à chaque demande ultérieure, et il vous authentifie jusqu'à ce que le jeton expire.

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "user": "user",
  "apikey": "devkey:user"
}
```

Le résultat sera quelque chose comme:

```json
{
  "api_error_message": "",
  "api_response": {
    "app_token": "user:f220eb76ff8404abfece8c0c2f3368c7d89618c776bedcd3a506843dc4a952e4",
    "provider": null,
    "refresh_token": null
  },
  "api_server_version": "0.0.0.dev0",
  "api_status_code": 200
}
```

Utilisation de ce jeton dans un autre appel d'API:

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer user:f220eb76ff8404abfece8c0c2f3368c7d89618c776bedcd3a506843dc4a952e4
```

Notez que lorsque vous vous connectez à l'aide d'une clé d'api, les autorisations de la clé d'api continuent de s'appliquer. Ainsi, si vous essayez d'accéder à
à un point d'accès qui requiert l'autorisation "write" avec une clé API qui n'a que l'autorisation "read", cela provoquera une erreur 403
Forbidden (Interdit).

### Authentification par jeton d'accès

En plus des méthodes d'authentification fournies en interne par Howler, vous pouvez également vous authentifier avec un fournisseur OAuth externe comme Azure ou Keycloak.
Pour ce faire, vous devez obtenir un jeton d'accès auprès de l'un de ces fournisseurs.
Pour obtenir un jeton d'accès, il y a généralement deux flux - On-Behalf-Of, ou le flux de connexion de l'utilisateur (voir [ici](https://www.rfc-editor.org/rfc/rfc6749#section-4.1) pour un récapitulatif
de cela). Dans le cas de Howler, le point de terminaison `v1/auth/login` est utilisé pour les étapes D & E du flux de connexion de l'utilisateur, et
il renvoie ce qui suit:

```json
{
  "api_response": {
    "app_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0",
    "provider": "keycloak",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWZyZXNoIn0"
  }
}
```

Dans ce cas, le `app_token` est le Web Token JSON que l'application utilise comme jeton d'accès. De la même manière, le
`refresh_token` est un autre JWT qui est utilisé pour rafraîchir le jeton d'accès si nécessaire. Enfin, le champ `provider` (fournisseur)
indique à quel fournisseur correspond ce jeton d'accès.

Une fois que vous avez ce jeton d'accès, vous pouvez simplement le transmettre dans l'en-tête Authorization :

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0
```

Howler détectera automatiquement qu'il s'agit d'un JWT et le traitera comme tel. Si le jeton est valide, l'utilisateur sera
authentifié.

Afin de rafraîchir un jeton d'accès expiré, vous pouvez utiliser l'appel API suivant:

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "oauth_provider": "keycloak",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWZyZXNoIn0"
}
```

Et vous obtiendrez quelque chose comme ceci en retour:

```json
{
  "api_response": {
    "app_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMiJ9",
    "provider": "keycloak",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWZyZXNodG9rZW4yIn0"
  }
}
```

## Impersonation

Le dernier élément important du flux d'authentification est la fonctionnalité d'usurpation d'identité. Pour qu'un compte de service
ou un autre utilisateur puisse se faire passer pour vous (c'est-à-dire créer des alertes en votre nom), Howler permet aux utilisateurs de fournir une deuxième clé API
afin de s'authentifier en tant qu'autre utilisateur.

Avant d'utiliser la clé API d'un autre utilisateur pour vous authentifier en tant que lui, il est important que la clé API que vous utilisez ait été
marquée comme valide pour l'usurpation d'identité - vérifiez auprès de l'utilisateur qui l'a fournie. Si c'est le cas, vous pouvez l'utiliser en formulant votre requête
comme suit:

```bash
# Your credentials
echo -n "admin:devkey:admin" | base64 -w0
# -> YWRtaW46ZGV2a2V5OmFkbWlu

# Their credentials
echo -n "user:impersonate_admin:user" | base64 -w0
# -> dXNlcjppbXBlcnNvbmF0ZV9hZG1pbjp1c2Vy
```

```alert
Toute forme d'authentification peut être utilisée par l'usurpateur, mais les clés API validées sont la seule méthode d'authentification autorisée pour la personne dont vous usurpez l'identité.
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic YWRtaW46ZGV2a2V5OmFkbWlu
X-Impersonating: Basic dXNlcjppbXBlcnNvbmF0ZV9hZG1pbjp1c2Vy
```

Si la configuration est correcte, le résultat sera le suivant:

```json
{
  "api_error_message": "",
  "api_response": {
    "avatar": null,
    "classification": "TLP:W",
    "email": "user@howler.cyber.gc.ca",
    "groups": ["USERS"],
    "is_active": true,
    "is_admin": false,
    "name": "User",
    "roles": ["user"],
    "username": "user"
  },
  "api_server_version": "0.0.0.dev0",
  "api_status_code": 200
}
```

Notez que le serveur a renvoyé cette requête comme si vous étiez `user`, PAS `admin`. Il est cependant clairement indiqué dans les logs que c'est vous qui faites la requête:

```log
22/12/05 14:15:02 INFO howler.api.security | Authenticating user for path /api/v1/user/whoami/
22/12/05 14:15:03 WARNING howler.api.security | admin is impersonating user
22/12/05 14:15:03 INFO howler.api.security | Logged in as user from 127.0.0.1
22/12/05 14:15:03 INFO howler.api | GET /api/v1/user/whoami/ - 200
```
