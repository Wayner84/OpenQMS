# Dev stage: Vite dev server with HMR, used by docker-compose.yml (see docs/Docker.md).
FROM node:20-slim AS dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]

# Build stage: production static assets (not required by Milestone 0, documented for
# later use per docs/Docker.md and docs/Deployment.md).
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage: static files served by a minimal web server.
FROM nginx:1.27-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
