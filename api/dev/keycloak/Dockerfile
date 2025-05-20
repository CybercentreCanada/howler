FROM quay.io/keycloak/keycloak:18.0.2

ENV KEYCLOAK_ADMIN="admin"
ENV KEYCLOAK_ADMIN_PASSWORD="admin"
ENV KC_PROXY="edge"
EXPOSE 8080 8080
CMD ["start-dev", "--debug", "--import-realm", "--spi-dblock-jpa-lock-wait-timeout 900", "-Dkeycloak.profile.feature.token_exchange=enabled", "-Dkeycloak.profile.feature.admin_fine_grained_authz=enabled"]

COPY ./keycloak-realm.json /opt/keycloak/data/import/keycloak-realm.json
