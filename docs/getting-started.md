# Getting Started

## Pré-requisitos

### 1. Python 3.11+
```bash
python3 --version  # deve ser 3.11+
```

### 2. Node.js 22+ (via nvm)
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 22
node --version  # deve ser v22+
```

### 3. GitHub CLI
```bash
# Ubuntu/Debian
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# Autenticar
gh auth login
```

### 4. Vercel CLI
```bash
npm install -g vercel
vercel login
```

### 5. Neon Database
- Criar conta em [neon.tech](https://neon.tech) (free tier)
- Copiar connection string do projeto

## Instalação

```bash
git clone https://github.com/mayrincktech/hermes-gsd-framework.git
cd hermes-gsd-framework
```

## Configurar Credenciais

```bash
# Variáveis de ambiente
export GITHUB_TOKEN=ghp_seu_token_aqui
export VERCEL_TOKEN=vcp_seu_token_aqui
export NEON_CONNECTION_STRING=postgresql://user:pass@host/db?sslmode=require
```

Ou crie um `.env` na raiz:
```bash
cat > .env << 'EOF'
GITHUB_TOKEN=ghp_seu_token_aqui
VERCEL_TOKEN=vcp_seu_token_aqui
NEON_CONNECTION_STRING=postgresql://user:pass@host/db?sslmode=require
EOF
```

## Criar Seu Primeiro App

```bash
python3 provision/provision_app.py \
  --name "Task Manager" \
  --slug "task-manager" \
  --description "Sistema de gerenciamento de tarefas"
```

Output esperado:
```json
{
  "app_name": "Task Manager",
  "slug": "task-manager",
  "github_url": "https://github.com/.../task-manager",
  "vercel_url": "https://task-manager-xxx.vercel.app",
  "database_schema": "task_manager",
  "database_url": "postgresql://...?schema=task_manager",
  "status": "provisioned"
}
```

## Próximos Passos

1. **Clone o novo repo** localmente
2. **Adicione `.env.local`** com a `DATABASE_URL` retornada
3. **Rode `npm run dev`** para desenvolvimento local
4. **Siga a metodologia GSD** — veja `METHODOLOGY.md`
5. **Quando pronto**, push para GitHub → Vercel auto-deploy

## Estrutura do Template

```
template/
├── src/
│   ├── app/
│   │   ├── layout.tsx       # Root layout com sidebar + bottom nav
│   │   ├── page.tsx         # Dashboard/welcome page
│   │   ├── globals.css      # Tailwind v4 + tema dark/light
│   │   ├── projects/        # Página de projetos (placeholder)
│   │   └── settings/        # Página de settings (placeholder)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── sidebar.tsx      # Sidebar desktop (w-60)
│   │   │   └── bottom-nav.tsx   # Bottom nav mobile (h-14)
│   │   └── ui/              # shadcn/ui components (10+)
│   └── lib/
│       └── utils.ts         # cn() helper
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
└── components.json           # shadcn/ui config
```

## Stack do Template

- **Next.js 16** — App Router, Server Components
- **TypeScript** — strict mode
- **Tailwind CSS v4** — com tema dark/light
- **shadcn/ui (Base UI)** — 10+ componentes: card, badge, button, input, label, avatar, dropdown-menu, separator, tabs, sheet, sonner
- **Lucide React** — ícones
- **Mobile-first** — sidebar desktop + bottom nav mobile + Sheet menu
