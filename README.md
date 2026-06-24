# GSD Framework

**Metodologia + ferramentas para desenvolvimento de apps com IA — do conceito ao deploy em minutos.**

O GSD (Get Shit Done) é um framework que combina:
- **Metodologia estruturada** — pipeline de 11 estágios com gates de qualidade
- **Template reutilizável** — Next.js + auth + i18n + DB + shadcn/ui pronto pra clonar
- **Provisionamento automático** — GitHub + Vercel + Neon com um comando, zero intervenção manual

## O que está incluído

| Componente | Descrição |
|---|---|
| `METHODOLOGY.md` | Pipeline GSD v7 completo com todos os gates |
| `docs/` | Guias detalhados de pipeline, design system, roles e provisionamento |
| `template/` | Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui + auth + i18n + DB |
| `provision/` | Script Python que automatiza setup de GitHub + Neon + Vercel |

## Pré-requisitos

- **Python 3.11+** com `psycopg2-binary` (`pip install psycopg2-binary`)
- **Node.js 22+** (recomendado via [nvm](https://github.com/nvm-sh/nvm))
- **[gh CLI](https://cli.github.com/)** autenticado
- **[Vercel CLI](https://vercel.com/docs/cli)** instalado (`npm i -g vercel`)
- **Conta [Neon](https://neon.tech)** (free tier)

## Quickstart

```bash
# 1. Clone o framework
git clone https://github.com/mayrincktech/gsd-framework.git
cd gsd-framework

# 2. Configure credenciais
export GITHUB_TOKEN=seu_token_aqui
export NEON_CONNECTION_STRING=postgresql://...
echo "seu_vercel_token" > /tmp/.vercel_tok

# 3. Crie um novo app
python3 provision/provision_app.py \
  --name "Meu App" \
  --slug "meu-app" \
  --description "Descrição do app"
```

O script executa 7 passos automatizados em ~2 minutos:

```
1. Copy template    → /workspace/{slug}
2. Personalize      → "App Name" substituído em todos os arquivos
3. GitHub repo      → repo privado criado + push (email correto para Vercel)
4. Neon database    → schema + auth tables criadas (users, accounts, sessions, verification_tokens)
5. Vercel env vars  → DATABASE_URL + AUTH_SECRET configurados antes do deploy
6. Vercel deploy    → production deploy com tudo configurado
7. Output           → JSON com URLs + append em provisioned_apps.json
```

Resultado:
```json
{
  "app_name": "Meu App",
  "slug": "meu-app",
  "github_url": "https://github.com/mayrincktech/meu-app",
  "vercel_url": "https://meu-app-xxx.vercel.app",
  "database_schema": "meu_app",
  "database_url": "postgresql://...?sslmode=require",
  "auth_secret": "auto-generated",
  "status": "provisioned"
}
```

## Pipeline GSD

```
RESEARCH GATE
    ↓
BUSINESS VALIDATION
    ↓
ARCHITECTURE GATE
    ↓
UX DESIGN GATE
    ↓
PLAN → EXECUTE → UX REVIEW → TEST → VERIFY → DEPLOY → DONE
```

Cada gate é um checkpoint de qualidade. Nada passa sem aprovação.

## Template Features

### Autenticação (NextAuth v5)
- Login com email/senha (bcrypt)
- Signup com validação
- GitHub OAuth (opcional, auto-desativado se env vars vazias)
- Middleware de proteção de rotas
- Lazy init — build passa sem DATABASE_URL

### Internacionalização (next-intl)
- PT-BR e EN prontos
- Switcher de idioma na UI
- Rotas com `[locale]` prefix
- Middleware de detecção automática

### Banco de Dados (Neon + Drizzle)
- Neon Postgres (free tier, serverless HTTP driver)
- Drizzle ORM com schema de auth completo
- Migrations via drizzle-kit (com `pg` driver TCP)
- Tabelas em `public` (compatível com driver HTTP)

### UI/UX
- **Next.js 16** com App Router
- **TypeScript** strict mode
- **Tailwind CSS v4** com tema dark/light/system
- **shadcn/ui** (Base UI) — 12+ componentes prontos
- **Mobile-first** — sidebar desktop + bottom nav mobile
- **Lucide icons**
- **Sonner** — toast notifications

### Design
- Toggle de tema (dark/light/system)
- Layout responsivo 375px → desktop
- Empty states em todas as páginas
- Páginas de erro e 404 customizadas

## Arquitetura: Lazy Init

O template usa lazy initialization para que `next build` passe sem variáveis de ambiente:

```typescript
// DB — conexão criada na primeira request, não em build time
export function getDb() { ... }

// Auth — instância NextAuth criada na primeira request
function initAuth() { ... }
export const handlers = {
  GET: (req) => initAuth().handlers.GET(req),
  POST: (req) => initAuth().handlers.POST(req),
};
```

Isso significa que o provision script pode fazer deploy antes de configurar env vars, e o app não quebra em build time. As env vars são setadas via Vercel API antes do deploy.

## Configuração

### GitHub

O script usa o usuário `mayrincktech` por padrão. Para mudar:
```python
GITHUB_ORG = "sua-org"
GITHUB_EMAIL = "seu@email.com"  # DEVE bater com email da conta Vercel
```

### Vercel

O script detecta automaticamente o team/org. O token precisa de permissão para:
- Criar projects
- Setar environment variables
- Desabilitar SSO protection

### Neon

Cada app recebe um schema isolado + tabelas de auth em `public`. A connection string usa o hostname pooler (compatível com o driver HTTP `@neondatabase/serverless`).

Veja `docs/provision.md` para detalhes completos e troubleshooting.

## Licença

MIT — use freely, comercialmente ou não.
