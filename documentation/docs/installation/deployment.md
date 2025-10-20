# Deploying Howler

Internally at the Cyber Centre, we use a helm chart to deploy howler to a kubernetes cluster. An open source version of this chart is available on [GitHub](https://github.com/CybercentreCanada/howler/tree/main/howler-helm). This article consists of a general discussion of dependencies. For an example of this helm chart in use, see [Installing Howler on a New Ubuntu VM](/howler-docs/installation/deployment_minikube).

## Dependencies

Howler has dependencies on a number of other applications for its functionality:

1. Elasticsearch 8 ([Configuration](/howler-docs/installation/configuration/#datastore))
1. Two redis instances ([Configuration](/howler-docs/installation/configuration/#redis))
    1. A persistent instance
    1. A non-persistent instance
1. A minio server (Setup under [FileStore](/howler-docs/installation/configuration/#filestore) as a host, see the [default configuration](/howler-docs/installation/default_configuration) for an example)
1. (Optional) An OAuth provider Google, Microsoft, Keycloak, etc.

So whatever platform you wish to run Howler one, it's important it has access to these dependencies. Internally, these
dependencies reside inside the same namespace as the main Howler pods.

## Building the Image

Currently, although the docker image for Howler is open source, there are no public images available. Therefore, manual
building is necessary:

<!-- LINK TO THE DEVELOPERS GUIDE SETUP SOMEWHERE BEFORE THIS. Some users are gonna go straight to the installation section and may not have read the Developer's Guide -->
```shell
cd ~/repos/howler-api/docker
./build_container.sh
```

This will create a new image with the tags `cccs/howler-api:latest` and `cccs/howler-api:$version`, where `$version`
is the version specified in howler's `setup.py`.

## Configuring OAuth

In order to get OAuth authentication working, you need to configure the provider in Howler's `config.yml`. Below is a
snippet explaining a sample configuration for connecting to a Keycloak server. Howler uses
[JSON Web Tokens](https://jwt.io/) for authentication in the case of OAuth.

```yaml
auth:
    # Other auth configuration here
    oauth:
        enabled: true
        providers:
            # Naming the provider
            keycloak:

                # The audience that should be accepted in the JWT
                # https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.3
                audience: howler

                # Should user data be synchronized on login with Howler?
                auto_sync: true

                # Where to connect to in order to fetch a token
                access_token_url: https://example.com/realms/keycloak-realm/protocol/openid-connect/token

                # The base URL of the OAuth provider, used for validation
                api_base_url: https://example.com/realms/keycloak-realm/protocol/openid-connect/

                # The client id and secret of the application in the OAuth provider
                # https://www.oauth.com/oauth2-servers/client-registration/client-id-secret/
                client_id: howler
                client_secret: super_secret_key

                # The scope denoting what data Howler will have access to on successful authentication
                # https://oauth.net/2/scope/
                scope: "openid offline_access"

                # Where to fetch the keys necessary to validate the JWT returned from the server.
                # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets
                jwks_uri: https://example.com/realms/keycloak-realm/protocol/openid-connect/certs

                # What groups the user must be a member of in order to have access to howler?
                required_groups:
                - howler_user

                # What do the groups the user is a member of map to in terms of roles in Howler?
                role_map:
                    user: howler_user
                    admin: howler_admin
                    automation_basic: howler_admin
                    automation_advanced: howler_admin
```
