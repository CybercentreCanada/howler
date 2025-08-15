# Base image
FROM node:alpine

# Creating howler-ui user (and using gid and uid 1001, since gid and uid 1000 are used by the node:node user in the base node image)
RUN addgroup -g 1001 howler-ui && adduser -u 1001 -G howler-ui -s /bin/sh -D howler-ui

# Set working directory
WORKDIR /howler-ui

# Copying the webpacked project into the working directory
COPY  --chown=howler-ui:howler-ui ./build /howler-ui/build

RUN npm install serve -g

USER root
RUN apk update && apk add --no-cache vim htop procps

# Run container rootless
USER howler-ui:howler-ui

# start app
CMD ["serve", "-s", "build"]
