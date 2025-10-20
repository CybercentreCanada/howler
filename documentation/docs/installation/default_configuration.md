
# Default Configuration

??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

Below is the default configuration for Howler. You can use it as a starting point for your installation. For more information, see [Configuration](/howler-docs/installation/configuration).

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
  oauth:
    enabled: false
    gravatar_enabled: true
    providers: {}
    strict_apikeys: false
core:
  metrics:
    apm_server:
      server_url: null
      token: null
  redis:
    nonpersistent:
      host: 127.0.0.1
      port: 6379
    persistent:
      host: 127.0.0.1
      port: 6380
datastore:
  hosts:
  - host: localhost:9200
    name: elastic
    password: devpass
    scheme: http
    username: elastic
  ilm:
    days_until_archive: 15
    enabled: false
    indexes: {}
    update_archive: false
  type: elasticsearch
filestore:
  storage:
  - host: localhost:9000?s3_bucket=hwl-storage&use_ssl=False
    name: minio
    password: Ch@ngeTh!sPa33w0rd
    scheme: s3
    username: hwl_storage_key
logging:
  export_interval: 5
  log_as_json: true
  log_directory: /var/log/howler/
  log_level: INFO
  log_to_console: true
  log_to_file: false
  log_to_syslog: false
  syslog_host: localhost
  syslog_port: 514
system:
  retention:
    crontab: 0 0 * * *
    enabled: true
    limit_amount: 350
    limit_unit: days
  type: development
ui:
  audit: true
  banner: null
  banner_level: info
  debug: false
  discover_url: null
  email: null
  enforce_quota: true
  secret_key: This is the default flask secret key... you should change this!
  static_folder: /example_dir/howler-api/howler/odm/models/../../../static
  validate_session_ip: true
  validate_session_useragent: true

```
