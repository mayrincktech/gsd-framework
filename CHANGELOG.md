# Changelog

## v1.1.0 — 2026-06-23

### Fixed — Provision Script (5 bugs críticos)
- **Git email vs Vercel account**: deploy era bloqueado porque o email do commit não batia com a conta Vercel. Adicionado `GITHUB_EMAIL` configurável no script.
- **Env vars não setadas**: DATABASE_URL e AUTH_SECRET não eram configurados no Vercel. Novo Step 5 seta env vars via Vercel API **antes** do deploy.
- **`?schema=` incompatível com Neon HTTP driver**: driver `@neondatabase/serverless` não suporta `?schema=` na URL. Tabelas movidas para `public`, URL sem schema param.
- **Tabelas de auth não criadas**: script só criava schema, não criava tabelas. Novo Step 4 cria users, accounts, sessions, verification_tokens via psycopg2.
- **AUTH_SECRET não gerado**: adicionado `secrets.token_urlsafe(32)` automático.

### Fixed — Template
- **Build quebrava sem DATABASE_URL**: NextAuth e Drizzle instanciavam conexões em build time. Corrigido com lazy initialization (getDb / initAuth).
- **i18n keys faltando**: `Settings.name` e `Settings.email` não existiam nos arquivos de tradução. Adicionados em pt-BR.json e en.json.
- **drizzle-kit push falhava com Neon**: driver HTTP não suporta push. Adicionado `pg` (driver TCP) como dependência.

### Added — Template
- NextAuth v5 com login email/senha + GitHub OAuth opcional
- next-intl com PT-BR e EN
- Drizzle ORM + Neon Postgres com schema de auth completo
- Páginas: dashboard, projects, settings, login, signup
- Componentes de layout: sidebar, bottom nav, theme toggle, language switcher
- Middleware de proteção de rotas (proxy.ts)

### Changed — Provision Script
- Reordenado: DB + env vars **antes** do deploy (antes era depois)
- 7 passos em vez de 6 (adicionado step de env vars)
- AUTH_SECRET incluído no output JSON
- Documentação de troubleshooting expandida com bugs reais encontrados

## v1.0.0 — 2026-06-23

### Added
- GSD Methodology v7 — pipeline completo com 11 estágios e 9 quality gates
- Web app template — Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui
- Provisioning script — automação de GitHub + Vercel + Neon
- Documentação completa (getting-started, pipeline, design-system, roles, provision)
- UX Score system — 6 critérios objetivos, mínimo 42/60
- Design System template obrigatório por projeto
- Wireframe format (ASCII, mobile-first 375px)
- Definition of Done checklist
