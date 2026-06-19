FROM node:20-alpine

WORKDIR /app

# Only package.json is committed (no lockfile), so use npm install, not npm ci.
COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

ENV APP_PORT=8000
EXPOSE 8000

CMD ["node", "server.js"]
