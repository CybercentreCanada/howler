# Créer des utilisateurs dans Howler

Howler ne dispose pas actuellement d'une interface graphique pour la création d'utilisateurs. La manière généralement
suggérée de créer des utilisateurs est de connecter Howler à un fournisseur OAuth 2.0 (azure, google, etc.) et de créer
un utilisateur basé sur le jeton d'authentification JWT renvoyé. Ceci est déjà géré dans Howler, et nécessite
juste la mise en place d'un fournisseur OAuth externe (voir
[ici](/howler-docs/installation/configuration/#oauthprovider) pour les informations de configuration).

Si vous souhaitez créer un utilisateur directement, sans passer par la création d'OAuth, vous pouvez utiliser le script
suivant, sur la même machine que celle sur laquelle Howler est hébergé :

```python
from howler.common.logging import get_logger
from howler.odm.models.user import User
from howler.security.utils import get_password_hash
from howler.common.loader import datastore

logger = get_logger(__file__)


def create_user(name: str, email: str, username: str):
    """Créer un utilisateur de base avec un nom d'utilisateur, un email et un mot de passe"""

    ds = datastore()

    user_data = User(
        {
            "name": name,
            "email": email,
            "password": get_password_hash(username),
            "uname": f"{username}",
        }
    )
    ds.user.save(username, user_data)
    logger.info(f"{username}:{username}")

    ds.user.commit()


if __name__ == "__main__":
    name = input("Entrer le nom:\n> ")
    username = input("\nEntrer le nom d'utilisateur:\n> ")
    email = input("\nEntrer l'email:\n> ")

    print(
        f"Un nouvel utilisateur sera créé.\n\tNom: {name}\n\tNom d'utilisateur: {username}\n\tEmail: {email}"
    )

    create_user(name, email, username)
```

Un ticket pour la création d'un utilisateur graphique a été créé et est actuellement en cours de développement.
