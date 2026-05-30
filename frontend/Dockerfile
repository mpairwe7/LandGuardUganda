# syntax=docker/dockerfile:1.7
FROM oven/bun:1.3 AS deps
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile || bun install

FROM oven/bun:1.3 AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* env vars are baked into the client bundle at build
# time. The browser uses this URL to talk to the backend directly
# (Crane Cloud pods have no outbound egress, so the in-pod proxy
# fallback can't reach the backend). Override with --build-arg when
# the backend URL changes.
ARG NEXT_PUBLIC_BACKEND_URL=https://landguard-backend-d1e66f33.renu-01.cranecloud.io
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}
RUN bun run build

FROM oven/bun:1.3 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# bun:1.3's Debian base ships `groupadd`/`useradd` (passwd) but not the
# `adduser`/`addgroup` wrappers that bun:1.1 had, so use the former.
RUN groupadd --system --gid 10001 landguard && \
    useradd --system --uid 10001 --gid 10001 landguard

COPY --from=builder /app/public ./public
COPY --from=builder --chown=landguard:landguard /app/.next/standalone ./
COPY --from=builder --chown=landguard:landguard /app/.next/static ./.next/static

USER landguard
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O- http://localhost:3000/api/health || exit 1

CMD ["bun", "server.js"]
