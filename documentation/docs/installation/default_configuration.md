
# Default Configuration

??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality
    will always be documented and available on release.

Below is the default configuration for Howler when unit tests are run. You can use it as a starting point for your
installation. For more information, see [Configuration](/howler/installation/configuration).

```yaml
auth:
  allow_apikeys: true
  allow_extended_apikeys: true
  internal:
    enabled: true
    failure_ttl: 60
    max_failures: 5
    password_requirements:
      lower: false
      min_length: 12
      number: false
      special: false
      upper: false
  max_apikey_duration_amount: 180
  max_apikey_duration_unit: days
  oauth:
    enabled: true
    gravatar_enabled: true
    providers:
      keycloak:
        access_token_params: null
        access_token_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/token
        api_base_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/
        audience: howler
        authorize_params: null
        authorize_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/auth
        auto_create: true
        auto_properties: []
        auto_sync: true
        client_id: howler
        client_secret: 09RhSF7tp0ShDdDMCszqI4zk8HMroTTZ
        groups_key: null
        groups_url: null
        iss: null
        jwks_uri: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/certs
        picture_url: null
        request_token_params: null
        request_token_url: null
        required_groups:
        - howler_user
        role_map:
          admin: howler_admin
          user: howler_user
        scope: openid offline_access
        uid_format: null
        uid_randomize: false
        uid_randomize_delimiter: '-'
        uid_randomize_digits: 0
        uid_regex: null
        user_get: null
    strict_apikeys: true
core:
  clue:
    enabled: false
    status_checks: []
    url: http://enrichment-rest.enrichment.svc.cluster.local:5000
  metrics:
    apm_server:
      server_url: null
      token: null
  notebook:
    enabled: false
    scope: null
    url: http://nbgallery.nbgallery.svc.cluster.local:3000
  plugins: []
  redis:
    nonpersistent:
      host: 127.0.0.1
      port: 6379
    persistent:
      host: 127.0.0.1
      port: 6380
datastore:
  hosts:
  - apikey_id: null
    apikey_secret: null
    host: localhost:9200
    name: elastic
    password: devpass
    scheme: http
    username: elastic
  type: elasticsearch
logging:
  export_interval: 5
  log_as_json: false
  log_directory: /var/log/howler/
  log_level: INFO
  log_to_console: true
  log_to_file: false
  log_to_syslog: false
  syslog_host: localhost
  syslog_port: 514
mapping:
  azure.upn: email_address
  destination.address: domain
  destination.domain: domain
  destination.ip: ip
  destination.nat.ip: ip
  destination.nat.port: port
  destination.port: port
  destination.user.email: email_address
  dns.answers.name: domain
  dns.question.registered_domain: domain
  dns.question.subdomain: domain
  dns.question.top_level_domain: domain
  dns.resolved_ip: ip
  email.attachments.file.hash.md5: md5
  email.attachments.file.hash.sha256: sha256
  email.bcc.address: email_address
  email.cc.address: email_address
  email.from.address: email_address
  email.parent.bcc.address: email_address
  email.parent.cc.address: email_address
  email.parent.destination: ip
  email.parent.from.address: email_address
  email.parent.source: ip
  email.parent.to.address: email_address
  email.reply_to.address: email_address
  email.sender.address: email_address
  email.to.address: email_address
  event.url: url
  file.hash.md5: md5
  file.hash.sha256: sha256
  host.domain: domain
  host.ip: ip
  howler.outline.indicators: email_address
  process.parent.parent.user.email: email_address
  process.parent.user.email: email_address
  process.user.email: email_address
  related.ip: ip
  server.address: domain
  server.domain: domain
  server.ip: ip
  source.address: domain
  source.domain: domain
  source.ip: ip
  source.nat.ip: ip
  source.nat.port: port
  source.port: port
  source.user.email: email_address
  threat.indicator.email.address: email_address
  threat.indicator.ip: ip
  tls.client.ja3: sha256
  tls.server.ja3s: sha256
  url.domain: domain
  url.port: port
  url.registered_domain: domain
  url.subdomain: domain
  url.top_level_domain: domain
system:
  retention:
    crontab: 0 0 * * *
    enabled: true
    limit_amount: 350
    limit_unit: days
  type: development
  view_cleanup:
    crontab: 0 0 * * *
    enabled: true
ui:
  audit: false
  debug: true
  discover_url: null
  enforce_quota: true
  secret_key: This is the default flask secret key... you should change this!
  static_folder: /etc/howler/static
  validate_session_ip: true
  validate_session_useragent: false
  websocket_url: null
```
