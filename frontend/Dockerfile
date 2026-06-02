# ── Stage 1: build React app ───────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

# API endpoint injected at build time; override in CI/CD with --build-arg
ARG REACT_APP_API_ENDPOINT=https://api-leaderboard.anote.ai
ENV REACT_APP_API_ENDPOINT=$REACT_APP_API_ENDPOINT

RUN npm run build

# ── Stage 2: serve with nginx ──────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
