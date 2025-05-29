# Base image
FROM node:latest

# Creating howler-ui user (and using gid and uid 1001, since gid and uid 1000 are used by the node:node user in the base node image)
RUN groupadd -g 1001 howler-ui && useradd -u 1001 -g howler-ui -s /bin/sh howler-ui

# Set working directory
WORKDIR /howler-ui

# Copying the webpacked project into the working directory
COPY  --chown=howler-ui:howler-ui ./build /howler-ui/build

RUN npm install serve -g

USER root
RUN apt update && apt install vim htop procps -y

# Run container rootless
USER howler-ui:howler-ui

# start app
CMD ["serve", "-s", "build"]
