FROM node:22-slim

WORKDIR /app

# The Compose service bind-mounts ./dashboard over /app and keeps node_modules in
# a named volume. Installing here seeds that volume on its first creation; the
# entrypoint re-installs when package-lock.json changes later.
RUN mkdir -p /app/node_modules && chown -R node:node /app
USER node

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

COPY --chown=node:node --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

EXPOSE 5173
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["npm", "run", "dev"]
