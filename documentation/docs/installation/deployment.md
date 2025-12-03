# Deploying Howler

Internally at the Cyber Centre, we use a helm chart to deploy howler to a kubernetes cluster. An open source version
of this chart is available on [GitHub](https://github.com/CybercentreCanada/howler/tree/main/howler-helm). This
article consists of a general discussion of dependencies. For an example of this helm chart in use, see
[Installing Howler on a New Ubuntu VM](/howler/installation/deployment_minikube).

## Prerequisites

Before deploying Howler, ensure you have the following tools:

- **`kubectl`**: Kubernetes command-line tool ([installation guide](https://kubernetes.io/docs/tasks/tools/))
  - You may also want to install **`k9s`** for an easier time administering the cluster. ([installation guide](https://k9scli.io/topics/install/))
- **`helm`**: Helm 3.x or later ([installation guide](https://helm.sh/docs/intro/install/))
- **Access to a Kubernetes cluster**: With sufficient permissions to create namespaces, deployments, and services

And the following permissions on the cluster:

- **Cluster admin permissions** or appropriate RBAC roles to:
  - Create and manage namespaces
  - Deploy applications via Helm charts
  - Create secrets and config maps
  - Configure ingress resources (if using ingress)

### Architecture Overview

For a comprehensive understanding of how Howler's components interact, see the
[System Architecture](/howler/overview/architecture/) documentation. This will help you understand the
relationships between Howler's services and its dependencies.

## Dependencies

Howler has dependencies on a number of other applications for its functionality:

1. Elasticsearch 8 ([Configuration](/howler/installation/configuration/#datastore))
1. Two redis instances ([Configuration](/howler/installation/configuration/#redis))
    1. A persistent instance
    1. A non-persistent instance
1. (Optional) An OAuth provider Google, Microsoft, Keycloak, etc.

### Dependency Hosting Options

Howler is flexible in how you provide these dependencies. You have several options:

#### Co-located Dependencies (Recommended for Development/Testing)

The Howler Helm chart includes optional dependencies (Redis and MinIO) that can be deployed in the same Kubernetes
namespace as Howler. This approach is convenient for development, testing, or smaller deployments.

```yaml
# In values.yaml - using included dependencies
redis-persistent:
  enabled: true

redis-nonpersistent:
  enabled: true
```

#### External Managed Services (Recommended for Production)

For production deployments, you can use externally managed services as long as they are accessible over the network
from your Howler pods. This includes:

- Managed Elasticsearch/OpenSearch services (e.g., AWS OpenSearch, Elastic Cloud)
- Managed Redis services (e.g., AWS ElastiCache, Azure Cache for Redis)

To use external services, configure the connection details in your `values.yaml`:

```yaml
# Example: Using external services
howlerRest:
  datastore:
    hosts:
      - host: my-elasticsearch.example.com
        port: 9200
        scheme: https
        username: elastic
        password: secret

  redis:
    persistent:
      host: my-redis-persistent.example.com
      port: 6379
    nonpersistent:
      host: my-redis-cache.example.com
      port: 6379
```

<!-- markdownlint-disable -->
??? warning "Network Access Requirements"
    Ensure that:

    - Your Howler pods can reach external services (check firewall rules, security groups, network policies)
    - TLS/SSL certificates are properly configured if using encrypted connections
    - Authentication credentials are stored securely (consider using Kubernetes Secrets)
    - Network latency between Howler and dependencies is acceptable for your use case
<!-- markdownlint-enable -->

## Docker Images

Howler provides official Docker images for both the API and UI components, available on Docker Hub:

- **API Image**: [cccs/howler-api](https://hub.docker.com/r/cccs/howler-api)
- **UI Image**: [cccs/howler-ui](https://hub.docker.com/r/cccs/howler-ui)

These images are regularly updated with new releases. You can pull specific versions using tags:

```shell
# Pull latest versions
docker pull cccs/howler-api:latest
docker pull cccs/howler-ui:latest

# Pull a specific version (e.g., 2.5.0)
docker pull cccs/howler-api:2.5.0
docker pull cccs/howler-ui:2.5.0
```

When using the Howler Helm chart, you can specify which images to use in your `values.yaml`:

```yaml
howlerRest:
  image:
    repository: cccs/howler-api
    tag: latest
    pullPolicy: IfNotPresent

howlerUi:
  image:
    repository: cccs/howler-ui
    tag: latest
    pullPolicy: IfNotPresent
```

<!-- markdownlint-disable -->
??? tip "Building Images from Source"
    If you need to build custom images or want to contribute to Howler development, see the
    [Developer Getting Started Guide](/howler/developer/getting_started/) for instructions on setting up your
    development environment and building images locally.

    The guide covers:

    - Installing required dependencies (Node.js, Python, Docker)
    - Building the API and UI images from source
    - Running Howler in development mode
<!-- markdownlint-enable -->

## Configuring OAuth Authentication

OAuth provides single sign-on (SSO) capabilities, allowing users to authenticate with Howler using their existing
organizational credentials. This section shows how to configure an OAuth provider for Howler.

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
