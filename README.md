# Maehai (ร้านหมูยอแม่ฮาย)

Monorepo: Django API + Next.js shop + Vite admin, with shared UI and a generated API client.

```
apps/api      Django + Django Ninja (domain apps under maehai/)
apps/shop     Customer site (Next.js, SSR, Thai default)
apps/admin    Back office (React + Vite)
packages/ui          Shared design system (tokens from Claude Design)
packages/api-client  Typed client generated from the API's OpenAPI
packages/config      Shared tsconfig / tailwind preset
infra         docker-compose for local development (postgres, redis)
deploy        production: Dockerfiles, Caddy, docker-compose, backups -> see deploy/README.md
```

## Quick start
```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d      # optional; sqlite is the dev default
pnpm install
(cd apps/api && uv sync && uv run python manage.py migrate)
pnpm api            # http://localhost:8000/api/docs
pnpm dev            # shop :3000, admin :5173
pnpm gen:api        # regenerate TS client after changing API
```

## Conventions
- Money is integer **satang**; only the backend calculates prices, VAT, shipping.
- Backend is split by domain (catalog, orders, payments, shipping...), not by technical layer.
- Frontends import only from `@maehai/*` packages, never from each other.

## Production
Everything runs from one `docker compose` file behind Caddy (automatic HTTPS). Setup, updates, backups and LINE
configuration: [deploy/README.md](deploy/README.md).
