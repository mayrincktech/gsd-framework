# Provisioning

O script `provision/provision_app.py` automatiza o setup completo de um novo app: template → GitHub → Neon → Vercel. **Um comando, ~2 minutos, zero intervenção manual.**

## Pré-requisitos

| Ferramenta | Versão | Como instalar |
|---|---|---|
| Python | 3.11+ | `apt install python3` |
| psycopg2-binary | qualquer | `pip install psycopg2-binary` (venv recomendado) |
| Node.js | 22+ | nvm |
| gh CLI | 2.95+ | [cli.github.com](https://cli.github.com/) |
| Vercel CLI | 54+ | `npm i -g vercel` |
| Neon | Free tier | [neon.tech](https://neon.tech) |

## Credenciais Necessárias

```bash
# ~/.hermes/.env ou variáveis de ambiente
GITHUB_TOKEN=ghp_...                    # GitHub PAT com repo scope
NEON_CONNECTION_STRING=postgresql://... # Neon connection string (pooler hostname)

# Vercel token em arquivo separado
echo "vcp_..." > /tmp/.vercel_tok       # Vercel token (vercel.com > Settings > Tokens)
```

## Uso

```bash
python3 provision/provision_app.py \
  --name "Task Manager" \
  --slug "task-manager" \
  --description "Sistema de gerenciamento de tarefas"
```

### Parâmetros

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `--name` | Sim | Nome de exibição (ex: "Task Manager") |
| `--slug` | Sim | Slug URL-safe (ex: "task-manager") |
| `--description` | Sim | Descrição de uma linha |
| `--template-dir` | Não | Path do template (default: `../web-app-template`) |

## Fluxo Executado (7 passos)

```
Step 1: COPY TEMPLATE
  └─ cp -r template → /workspace/{slug} (sem .git, node_modules, .next)

Step 2: PERSONALIZE
  └─ "App Name" → nome real em todos os arquivos
  └─ package.json: name + description atualizados

Step 3: GITHUB REPO
  └─ git init + commit (email deve bater com conta Vercel)
  └─ gh repo create --private + push
  └─ Idempotente: reusa repo se já existe

Step 4: NEON DATABASE ← ANTES do deploy
  └─ CREATE SCHEMA {slug_underscored}
  └─ CREATE TABLE users, accounts, sessions, verification_tokens (em public)
  └─ DATABASE_URL sem ?schema= (Neon HTTP driver não suporta)

Step 5: VERCEL ENV VARS ← ANTES do deploy
  └─ vercel link (cria projeto se não existe)
  └─ Set DATABASE_URL via Vercel API
  └─ Set AUTH_SECRET gerado automaticamente (secrets.token_urlsafe)
  └─ Idempotente: deleta e recria se já existe

Step 6: VERCEL DEPLOY
  └─ vercel deploy --prod (env vars já configuradas)
  └─ Disable SSO/Vercel Authentication (acesso público)
  └─ Captura URL de produção

Step 7: OUTPUT
  └─ JSON com todas as URLs e credenciais
  └─ Append em data/provisioned_apps.json
```

### Por que DB e env vars ANTES do deploy?

Na primeira versão, o deploy acontecia antes do DB e env vars. Isso causava:
1. First deploy com HTTP 500 (sem DATABASE_URL)
2. Necessidade de redeploy manual após configurar env vars
3. App quebrado por vários minutos até intervenção

A ordem correta é: preparar tudo (DB + env vars) → deploy → app funciona na primeira tentativa.

## Output

```json
{
  "app_name": "Task Manager",
  "slug": "task-manager",
  "github_url": "https://github.com/mayrincktech/task-manager",
  "vercel_url": "https://task-manager-xxx.vercel.app",
  "database_schema": "task_manager",
  "database_url": "postgresql://...?sslmode=require",
  "auth_secret": "auto-generated-secret",
  "status": "provisioned"
}
```

Também appenda em `data/provisioned_apps.json` para registro.

## Configuração

### GitHub

O script usa o usuário `mayrincktech` por padrão. Para mudar:

```python
# No topo do script
GITHUB_ORG = "sua-org"
GITHUB_EMAIL = "seu@email.com"  # DEVE bater com email da conta Vercel
GITHUB_NAME = "Seu Nome"
```

**Importante:** O `GITHUB_EMAIL` deve ser o mesmo email associado à conta Vercel. Se não bater, o Vercel bloqueia o deploy com erro "commit author does not have contributing access".

### Vercel

O script detecta automaticamente o team/org do Vercel via `vercel link`. O token deve ter permissão de criar projects e setar env vars.

### Neon

Cada app recebe:
- Um **schema** isolado (para organização futura)
- Tabelas de auth em **public** (o driver HTTP `@neondatabase/serverless` não suporta `?schema=` na connection string)
- A mesma instância Neon (free tier)

## Arquitetura do Template

### Lazy Init (Auth + DB)

O template usa lazy initialization para NextAuth e Drizzle — as conexões só são criadas na primeira request, não em build time. Isso permite que `next build` passe sem `DATABASE_URL` definida.

```typescript
// src/lib/db/index.ts — getDb() em vez de db exportado
export function getDb() {
  if (_db) return _db;
  _db = drizzle(neon(process.env.DATABASE_URL), { schema });
  return _db;
}

// src/lib/auth.ts — initAuth() em vez de NextAuth() no top-level
function initAuth() {
  if (_auth) return _auth;
  _auth = NextAuth({ adapter: DrizzleAdapter(getDb()), ... });
  return _auth;
}
```

### Neon HTTP Driver

O template usa `@neondatabase/serverless` (driver HTTP) para conexão com Neon. Isso significa:
- **Não suporta `?schema=`** na URL — tabelas devem estar em `public`
- **Não suporta conexões persistentes** — cada query é uma request HTTP
- **Funciona em edge functions** — sem socket TCP necessário

Para migrations locais (drizzle-kit), o template inclui `pg` (driver TCP) como dependência.

## Troubleshooting

### Deploy BLOCKED: "commit author does not have contributing access"

**Causa:** O email do git commit não bate com a conta Vercel.

**Fix:** O script já seta `GITHUB_EMAIL` corretamente. Se persistir, verifique:
```bash
git config user.email  # deve ser o email da conta Vercel
```

### Deploy BLOCKED: "Deployment not found"

**Causa:** Deploy CLI incompleto (timeout ou upload interrompido).

**Fix:** Delete deploys BLOCKED via Vercel API e refaça:
```python
import urllib.request, json
# GET /v6/deployments?projectId=X&limit=10
# DELETE /v13/deployments/{uid}
```

### HTTP 500 no app após deploy

**Causa:** `DATABASE_URL` não configurada ou incorreta.

**Fix:** O script seta env vars antes do deploy. Se persistir, verifique:
1. URL tem `?sslmode=require` (não `?schema=`)
2. Hostname é o pooler (`-pooler.c-...`) para driver HTTP
3. Tabelas estão em `public` (não em schema dedicado)

### Signup falha: "Failed to create account"

**Causa:** Tabelas de auth não existem no DB.

**Fix:** O script cria as tabelas no Step 4. Se persistir, crie manualmente:
```sql
CREATE TABLE IF NOT EXISTS users (
  id text NOT NULL PRIMARY KEY,
  name text, email text NOT NULL UNIQUE,
  email_verified timestamptz, image text, password text
);
-- + accounts, sessions, verification_tokens (ver AUTH_TABLES_SQL no script)
```

### `source: not found`

O script usa `. ~/.nvm/nvm.sh` (compatível com sh e bash). Se ainda falhar:
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

### `gh auth failed`

```bash
echo "$GITHUB_TOKEN" | gh auth login --with-token
gh auth setup-git
```

### Neon schema creation failed

- Verifique `NEON_CONNECTION_STRING`
- Teste conexão: `psql "$NEON_CONNECTION_STRING" -c "SELECT 1"`
- Se usar venv: `pip install psycopg2-binary`

### drizzle-kit push falha com Neon

O driver HTTP do Neon não suporta `drizzle-kit push`. Use:
```bash
# Instalar pg (já incluído no template)
npm install pg @types/pg

# Ou criar tabelas via psycopg2 (o que o provision script faz)
```
