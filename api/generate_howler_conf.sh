#!/bin/bash

mkdir -p /etc/howler/conf

HOWLER_CLASSIFICATION_PATH="/etc/howler/conf/classification.yml"
HOWLER_CONF_PATH="/etc/howler/conf/config.yml"
KEYCLOAK_CONF=""
AZURE_CONF=""

function create_classification() {
  echo "Creating $HOWLER_CLASSIFICATION_PATH"
  cp build_scripts/classification.yml $HOWLER_CLASSIFICATION_PATH
}

function create_config() {
  if [ -n "$KEYCLOAK_CLIENT_SECRET" ]; then
    KEYCLOAK_CONF+="
      keycloak:
          audience: howler
          auto_sync: true
          access_token_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/token
          api_base_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/
          authorize_url: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/auth
          client_id: howler
          client_secret: $KEYCLOAK_CLIENT_SECRET
          scope: \"openid offline_access\"
          jwks_uri: http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/certs
          required_groups:
          - howler_user
          role_map:
            user: howler_user
            admin: howler_admin
            automation_basic: howler_admin
            automation_advanced: howler_admin"
  fi

  if [ -n "$AZURE_CLIENT_ID" ] && [ -n "$AZURE_CLIENT_SECRET" ]; then
    AZURE_CONF+="
      azure:
          audience: $AZURE_CLIENT_ID
          auto_sync: true
          access_token_url: https://login.microsoftonline.com/da9cbe40-ec1e-4997-afb3-17d87574571a/oauth2/v2.0/token
          api_base_url: https://login.microsoftonline.com/da9cbe40-ec1e-4997-afb3-17d87574571a/
          authorize_url: https://login.microsoftonline.com/da9cbe40-ec1e-4997-afb3-17d87574571a/oauth2/v2.0/authorize
          client_id: $AZURE_CLIENT_ID
          client_secret: $AZURE_CLIENT_SECRET
          scope: \"$AZURE_CLIENT_ID/.default openid email profile\"
          jwks_uri: https://login.microsoftonline.com/da9cbe40-ec1e-4997-afb3-17d87574571a/discovery/v2.0/keys
          user_get: openid/userinfo
          picture_url: https://graph.microsoft.com/v1.0/me/photo/\$value
          iss: https://login.microsoftonline.com/da9cbe40-ec1e-4997-afb3-17d87574571a/v2.0
          uid_regex: \"(.+)\\\\.(.+)@\"
          required_groups:
          - df1d1d1d-e663-4ee2-92ef-8ddc0ee4f4f3
          role_map:
            user: df1d1d1d-e663-4ee2-92ef-8ddc0ee4f4f3
            admin: a68d51b6-68d9-4ca8-b26d-b4dbf1b3c56c
            automation_basic: a68d51b6-68d9-4ca8-b26d-b4dbf1b3c56c
            automation_advanced: a68d51b6-68d9-4ca8-b26d-b4dbf1b3c56c"
  fi

  if [ -z "$KEYCLOAK_CONF" ] && [ -z "$AZURE_CONF" ]; then
    echo "Error: KEYCLOAK_CLIENT_SECRET and/or (AZURE_CLIENT_ID and AZURE_CLIENT_SECRET) environment variable must be set!"
    exit 1
  fi

  HOWLER_CONF_DATA="auth:
  internal:
    enabled: true
  oauth:
    enabled: true
    providers:$KEYCLOAK_CONF$AZURE_CONF

datastore:
  ilm:
    enabled: false
    indexes: {}

logging:
  log_level: INFO
  log_as_json: false

system:
  type: development

ui:
  audit: true
  debug: false
  enforce_quota: false
  validate_session_useragent: false
  discover_url: https://discover.dev.analysis.cyber.gc.ca/eureka/apps
  static_folder: /etc/howler/static

core:
  spellbook:
    enabled: true
    url: https://spellbook.dev.analysis.cyber.gc.ca/api
    scope: 883e7856-e3a6-480f-b958-5289d5d8a7ad/default
  notebook:
    enabled: false
  alfred:
    enabled: true
  borealis:
    enabled: true
    url: https://enrichment.dev.analysis.cyber.gc.ca
    scope: df750cd2-e7b8-4a21-a5f8-c9c1ef99071b/user_impersonation
  vault_url: https://vault.dev.analysis.cyber.gc.ca
"

  echo "Creating $HOWLER_CONF_PATH"
  cat <<<$HOWLER_CONF_DATA >$HOWLER_CONF_PATH
}

write=true
if [[ -f "$HOWLER_CLASSIFICATION_PATH" ]]; then
  while [ true ]; do
    read -n 1 -p "$HOWLER_CLASSIFICATION_PATH already exists. Overwrite? (y/N) " res
    if [ -z "$res" ]; then
      res="n"
    else
      echo
    fi

    case "$res" in
    [yY])
      break
      ;;
    [nN])
      write=false
      break
      ;;
    *)
      echo "Enter a valid response.\n"
      ;;
    esac
  done
fi

if [ "$write" = true ]; then
  create_classification
fi

write=true
if [[ -f "$HOWLER_CONF_PATH" ]]; then
  while [ true ]; do
    read -n 1 -p "$HOWLER_CONF_PATH already exists. Overwrite? (y/N) " res
    if [ -z "$res" ]; then
      res="n"
    else
      echo
    fi

    case "$res" in
    [yY])
      break
      ;;
    [nN])
      write=false
      break
      ;;
    *)
      echo "Enter a valid response.\n"
      ;;
    esac
  done
fi

if [ "$write" = true ]; then
  create_config
fi

echo "Creating lookups..."
mkdir -p /etc/howler/lookups
python howler/external/generate_mitre.py /etc/howler/lookups
echo "Completed configuration!"
