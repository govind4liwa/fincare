# ============================================================
# FinCare frontend (Next.js) — dev image for docker-compose.
# Production build/runner stages will be added when we containerize for deploy.
# ============================================================
FROM node:22-alpine AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# --- Dependencies ---
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# --- Dev (used by docker-compose `frontend` service) ---
FROM base AS dev
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
