# Creating Users in Howler

Howler does not currently have a graphical interface for creating users. The generally suggested manner of creating
users is by connecting Howler to an OAuth 2.0 provider (azure, google, etc.) and creating a user based on the returned
JWT authentication token. This is already handled in howler, and just requires setting up an external OAuth provider
(see [here](/howler-docs/installation/configuration/#oauthprovider) for configuration information).

If you'd like to create a user directly, without the use of OAuth creation, you can currently use the following script,
on the same machine Howler is hosted on:

```python
from howler.common.logging import get_logger
from howler.odm.models.user import User
from howler.security.utils import get_password_hash
from howler.common.loader import datastore

logger = get_logger(__file__)


def create_user(name: str, email: str, username: str):
    """Create a basic user with username, email and password"""

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
    name = input("Enter Name:\n> ")
    username = input("\nEnter Username:\n> ")
    email = input("\nEnter Email:\n> ")

    print(
        f"New user will be created.\n\tName: {name}\n\tUsername: {username}\n\tEmail: {email}"
    )

    create_user(name, email, username)
```

A ticket for graphical user creation has been created.
