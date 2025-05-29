<!-- docs/ingestion/authentication.md -->

# Howler Authentication

Howler's API supports a number of authentication approaches when accessing the API. This document will outline the
different approaches, and explain how to use each of them.

## Types of Authentication

There are four methods of authentication one can use to connect to the howler API:

1. Username and Password
2. Username and API Key
3. Username and app token (after login)
4. OAuth Access Token

We will outline the use case for each authentication type next.

### Username/Password Authentication

Username and password authentication is the simplest and least secure method of authentication. Unlikely to be enabled
in a production environment, it allows users to easily connect to the Howler API and make changes as the given user,
without having to worry about creating API keys or using an OAuth provider like Keycloak or Azure. Users can connect
using username and password authentication in one of two ways:

#### Direct Call to the Requisite Endpoint (Password)

This is far and away the simplest method. Simply add a basic Authorization header to the HTTP request you want to
make, and everything is taken care of:

```bash
echo -n "user:user" | base64 -w0
# -> dXNlcjp1c2Vy
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic dXNlcjp1c2Vy
```

#### Exchanging for an App Token (Password)

This is a slightly more complex approach, but carries the benefit of not exposing the username and password on every
request. You can leverage the `v1/auth/login` endpoint to exchange your username and password for an app token. The
token works similarly to an OAuth access token - you provide it with each subsequent request, and it authenticates you
until the token expires.

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "user": "user",
  "password": "user"
}
```

Will return something like:

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

Using this token in another API call:

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer user:5791a142067745c3af51d6596da7da8f86357a9fa92ad78d1ce118ea7d89d34e
```

### Username/API Key Authentication

The username and API Key authentication works largely the same as username/password from the perspective of the client.
On the server side, however, API keys have several key advantages. Firstly, they can easily be revoked by the user.
Secondly, their privileges can be limited, allowing only a subset of permissions.

There are two methods of authentication, mirroring the username and password:

#### Direct Call to the Requisite Endpoint (API Key)

Simply add a basic Authorization header containing the username and API key to the HTTP request you want to make, and
everything is taken care of:

```bash
# note the format is <username>:<apikeyname>:<secret>
echo -n "user:devkey:user" | base64 -w0
# -> dXNlcjpkZXZrZXk6dXNlcg==
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic dXNlcjpkZXZrZXk6dXNlcg==
```

#### Exchanging for an App Token (API Key)

You can also leverage the `v1/auth/login` endpoint to exchange your username and API key for an app token. The
token works similarly to an OAuth access token - you provide it with each subsequent request, and it authenticates you
until the token expires.

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "user": "user",
  "apikey": "devkey:user"
}
```

Will return something like:

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

Using this token in another API call:

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer user:f220eb76ff8404abfece8c0c2f3368c7d89618c776bedcd3a506843dc4a952e4
```

Note that when logging in using an api key, the permissions of the api key continue to apply. So if you try and access
an endpoint that requires the "write" permission with an API key that only has read permission, this will cause a 403
Forbidden error.

### Access Token Authentication

In addition to the authentication methods provided internally by Howler, you can also authenticate with an external
OAuth provider like Azure or Keycloak. To do this, you must obtain an access token from one of these providers. In
order to get an access token, there are generally two flows - On-Behalf-Of, or the user login flow (see [here](https://www.rfc-editor.org/rfc/rfc6749#section-4.1) for a rundown
of that). In the case of Howler, the `v1/auth/login` endpoint is used for step D & E in the linked user login flow, and
it returns the following:

```json
{
  "api_response": {
    "app_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0",
    "provider": "keycloak",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWZyZXNoIn0"
  }
}
```

In this case, the `app_token` is the JSON Web Token the application uses as an access token. Similarly, the
`refresh_token` is another JWT that is used to refresh the access token if needed. Finally, the `provider` field
outlines which provider this access token corresponds to.

Once you have that access token, you can simply pass it along in the Authorization header:

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0
```

Howler will automatically detect this is a JWT, and treat it as such. If the token is valid, the user will be
authenticated.

In order to refresh an expired access token, you can use the following API call:

```http
POST $CURRENT_URL/api/v1/auth/login/
Content-Type: application/json

{
  "oauth_provider": "keycloak",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWZyZXNoIn0"
}
```

And you'll get something like this back:

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

The final important bit of the authentication flow is the impersonation functionality. In order for a service account
or other user to impersonate you (i.e. to create alerts on your behalf), Howler allows users to provide a second API key
in order to authenticate as another user.

Before you use another user's API key to authenticate as them, it's important that the API key you're using has been
marked as valid for impersonation - check with the user that provided it. If it has, you can use it by, formating your
request as follows:

```bash
# Your credentials
echo -n "admin:devkey:admin" | base64 -w0
# -> YWRtaW46ZGV2a2V5OmFkbWlu

# Their credentials
echo -n "user:impersonate_admin:user" | base64 -w0
# -> dXNlcjppbXBlcnNvbmF0ZV9hZG1pbjp1c2Vy
```

```alert
Any form of authentication can be used by the impersonator, but validated API keys are the only permitted
authentication method for the person you're impersonating.
```

```http
GET $CURRENT_URL/api/v1/user/whoami
Authorization: Basic YWRtaW46ZGV2a2V5OmFkbWlu
X-Impersonating: Basic dXNlcjppbXBlcnNvbmF0ZV9hZG1pbjp1c2Vy
```

If set up correctly, the result will look like:

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

Note that the server returned this as if you were `user`, NOT `admin`. It is clearly marked in the logs, however, that you are making the request:

```log
22/12/05 14:15:02 INFO howler.api.security | Authenticating user for path /api/v1/user/whoami/
22/12/05 14:15:03 WARNING howler.api.security | admin is impersonating user
22/12/05 14:15:03 INFO howler.api.security | Logged in as user from 127.0.0.1
22/12/05 14:15:03 INFO howler.api | GET /api/v1/user/whoami/ - 200
```
