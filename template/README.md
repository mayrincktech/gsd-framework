# Web App Template

Template base para criação de apps web com Next.js 16. Inclui tudo que é comum a todos os apps — auth, i18n, design system, DB — para que o desenvolvimento foque apenas no negócio.

## Stack

| Categoria | Tecnologia |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack) |
| Linguagem | TypeScript 5 |
| Estilo | Tailwind CSS v4 (oklch tokens) |
| UI | shadcn/ui (Base UI) |
| Auth | NextAuth v5 (credentials + GitHub OAuth opcional) |
| DB | Drizzle ORM + Neon Postgres |
| i18n | next-intl v4 (pt-BR + en) |
| Forms | react-hook-form + zod v4 |
| Tema | next-themes (dark/light/system) |
| Ícones | lucide-react |

## Features

### Autenticação
- Login com email + senha (credentials provider)
- Signup com validação completa (zod)
- GitHub OAuth opcional (basta configurar env vars)
- Sessões JWT via NextAuth v5
- Middleware de rotas protegidas (proxy.ts)
- Redirect automático: não logado → login, logado em login → dashboard

### Internacionalização
- pt-BR (padrão) e en
- Roteamento baseado em locale: `/pt-BR/dashboard`, `/en/dashboard`
- Language switcher na UI
- Todas as strings traduzíveis em `messages/pt-BR.json` e `messages/en.json`

### Design System
- Tema dark/light/system com toggle
- Tokens oklch (Tailwind v4)
- shadcn/ui componentes: button, card, input, label, avatar, badge, dropdown, separator, sheet, sonner, tabs
- Mobile-first: sidebar desktop (w-60) + bottom nav mobile (h-14)
- Páginas de erro, not-found e loading

### Banco de Dados
- Drizzle ORM com Neon Postgres serverless
- Schema completo: users, accounts, sessions, verificationTokens
- Migration scripts: `npm run db:generate`, `db:migrate`, `db:push`

## Setup

```bash
# 1. Instalar dependências
npm install

# 2. Configurar env vars
cp .env.example .env.local
# Editar .env.local com suas credenciais

# 3. Rodar migrations
npm run db:generate
npm run db:push

# 4. Gerar AUTH_SECRET
openssl rand -base64 32
# Colar no .env.local

# 5. Rodar
npm run dev
```

## Env Vars

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | Sim | Connection string do Postgres (Neon ou outro) |
| `AUTH_SECRET` | Sim | Secret do NextAuth (gerar com `openssl rand -base64 32`) |
| `AUTH_GITHUB_ID` | Não | GitHub OAuth client ID (deixar vazio pra desabilitar) |
| `AUTH_GITHUB_SECRET` | Não | GitHub OAuth client secret |

## Estrutura

```
src/
├── app/
│   ├── [locale]/
│   │   ├── (auth)/          # Layout auth (login, signup)
│   │   ├── (app)/           # Layout app (dashboard, projects, settings)
│   │   ├── error.tsx        # Página de erro
│   │   ├── loading.tsx      # Loading state
│   │   ├── not-found.tsx    # 404
│   │   └── layout.tsx       # Locale provider
│   ├── api/
│   │   └── auth/            # NextAuth + signup API routes
│   ├── globals.css          # Tailwind v4 + theme tokens
│   └── layout.tsx           # Root layout (providers)
├── components/
│   ├── auth/                # Login form, signup form, GitHub button
│   ├── layout/              # Sidebar, bottom nav, theme toggle, language switcher
│   ├── providers.tsx        # SessionProvider + ThemeProvider
│   └── ui/                  # shadcn/ui componentes
├── i18n/                    # next-intl config (routing, request, navigation)
├── lib/
│   ├── auth.ts              # NextAuth config
│   └── db/                  # Drizzle ORM (schema, connection)
└── proxy.ts                 # Auth + i18n middleware
```
