# Hermes GSD Framework

**Metodologia spec-driven para desenvolvimento de apps com IA — roda sobre o [Hermes Agent](https://hermes-agent.nousresearch.com).**

O GSD (Get Shit Done) é um framework que orquestra múltiplos agentes de IA com papéis especializados, gates de qualidade obrigatórios e pipeline estruturado. Não é só "pedir pro IA escrever código" — é um sistema production-ready com arquitetura travada, UX design gate e QA com modelo diferente do executor.

> ⚠️ **Este framework depende do Hermes Agent e de patches específicos.** Veja [`docs/hermes-requirements.md`](docs/hermes-requirements.md) para setup completo.

---

## Como funciona

Roles definidos por **capabilities**, não por modelo. Trocar um modelo não muda o framework.

```yaml
# Ver roles.yaml para configuração completa
orchestrator:    # research, architecture, UX design, planning, deploy
  code_generation: false
  current: "GLM-5.2"

code_executor:   # writes code, writes tests
  requirements: [fast_inference]
  current: "DeepSeek V4 Flash/Pro"

qa_verifier:     # reviews code, security, contracts
  requirements: [different_model_family: true]  # MANDATORY
  current: "Kimi K2.7 Code"
```

```
GLM-5.2 (Orchestrator + UX Designer)
  │
  ├── RESEARCH      → valida demanda antes de engenharia
  ├── ARCHITECTURE  → trava stack antes de codar
  ├── UX DESIGN     → trava wireframes + design system antes de UI
  ├── PLAN          → decomposição em tasks atômicas (máx 5 arquivos, 500 linhas)
  ├── EXECUTE       → DeepSeek V4 Flash/Pro codifica via delegate_task
  ├── UX REVIEW     → score objetivo (min 42/60 para aprovar)
  ├── TEST          → build, lint, typecheck, unit tests
  ├── VERIFY        → Kimi K2.7 revisa código (modelo DIFERENTE do executor)
  └── DEPLOY        → Vercel automático via Git
```

### Observabilidade: Kanban Board nativo

O pipeline é visualizado em tempo real no **Kanban board do Hermes**. Sem app separado, sem JSON pra sincronizar, sem polling.

- Cada task vira um card (To Do → In Progress → Review → Done)
- Cards bloqueados mostram o motivo (UX score < 42, build failed, QA critical)
- Zero infraestrutura de monitoramento

---

## Principais features

### UX Design Gate
Nenhuma tela é implementada sem wireframe aprovado. Antes de qualquer código UI:
- **DESIGN-SYSTEM.md** obrigatório (cores, tipografia, spacing, componentes, referências)
- **WIREFRAMES.md** com wireframe ASCII mobile-first (375px)
- Aprovação explícita antes de prosseguir

### UX Score (Review Gate)
Após EXECUTE, toda UI é avaliada em 6 critérios objetivos (0-10 cada):

| Critério | Descrição |
|---|---|
| Hierarquia Visual | Elementos importantes se destacam |
| Legibilidade | Contraste, tamanho de fonte, line-height |
| Espaçamento | Segue escala de spacing, consistência |
| Mobile Experience | Funciona em 375px, touch targets ≥44px |
| Acessibilidade | ARIA labels, contraste WCAG AA, teclado |
| Premium Feel | Profissional, espaço em branco, micro-interações |

**Mínimo 42/60 para aprovar.** Abaixo disso, volta para o executor com feedback específico.

### Multi-Model Delegation
IA diferente para papéis diferentes. Mesmo modelo se avaliando é um padrão de falha conhecido. Roles são definidos por capabilities em [`roles.yaml`](roles.yaml) — trocar de modelo não muda o framework.

| Role | O que faz | Modelo atual |
|---|---|---|
| orchestrator | Raciocínio, design, arquitetura, UX | GLM-5.2 |
| code_executor | Escreve código, rápido | DeepSeek V4 Flash/Pro |
| qa_verifier | Revisa código (modelo diferente) | Kimi K2.7 Code |

### Provisioning Automático
Um comando provisiona tudo:
- GitHub repo (privado ou público)
- Neon Postgres database (schema isolado)
- Vercel deploy (SSL, auto-deploy via Git)
- `.planning/` structure inicializado
- ~2 minutos do zero ao app rodando

---

## Hermes Integration

O GSD roda sobre o Hermes Agent. Os 3 patches abaixo são **obrigatórios** e se reaplicam automaticamente após `hermes update`.

| Patch | O que faz | Por que o GSD precisa |
|---|---|---|
| **Delegation Per-Task** | Permite trocar modelo entre delegações | Code AI (DeepSeek) e QA AI (Kimi) na mesma sessão |
| **Neon RAG Plugin** | Memória semântica via Neon + pgvector | Research Agent e recall de contexto |
| **Gemini Image Fallback** | Fallback quando FAL.ai falha | Geração de wireframes visuais e assets |

**Provider:** `custom:opencode-go` (endpoint OpenCode Go com DeepSeek e Kimi)

Setup completo em [`docs/hermes-requirements.md`](docs/hermes-requirements.md).

---

## Stack técnica

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 16 + React + TypeScript |
| UI | Tailwind v4 + shadcn/ui |
| Backend | API Routes (Next.js) |
| Database | Neon Postgres (serverless) |
| Auth | NextAuth / Supabase Auth |
| Deploy | Vercel (Git push → live) |
| Orchestrator | Hermes Agent |

---

## Estrutura do repo

```
hermes-gsd-framework/
├── METHODOLOGY.md              # Pipeline completo v8 com todos os gates
├── roles.yaml                  # Role definitions (capabilities, not model names)
├── CHANGELOG.md                # Histórico de versões
├── docs/
│   ├── pipeline.md             # Detalhamento de cada fase
│   ├── design-system.md        # Como criar DESIGN-SYSTEM.md
│   ├── roles.md                # Responsabilidades de cada agente
│   ├── getting-started.md      # Setup passo a passo
│   ├── provision.md            # Troubleshooting do provisioning
│   ├── hermes-requirements.md  # Patches e config do Hermes (OBRIGATÓRIO)
│   └── planning-structure.md   # Estrutura do .planning/
├── schemas/
│   └── task-format.md          # Formato de tasks atômicas
├── templates/
│   └── planning/               # Templates de STATE, ROADMAP, task
├── provision/
│   └── provision_app.py        # Script de provisioning automatizado
└── template/                   # Next.js app template (auth + i18n + DB + UI)
```

---

## Pré-requisitos

- **[Hermes Agent](https://hermes-agent.nousresearch.com)** com patches aplicados (ver [`docs/hermes-requirements.md`](docs/hermes-requirements.md))
- **Python 3.11+** com `psycopg2-binary` (`pip install psycopg2-binary`)
- **Node.js 22+** (recomendado via [nvm](https://github.com/nvm-sh/nvm))
- **[gh CLI](https://cli.github.com/)** autenticado
- **[Vercel CLI](https://vercel.com/docs/cli)** instalado (`npm i -g vercel`)
- **Conta [Neon](https://neon.tech)** (free tier)
- **Provider OpenCode Go** (`OPENCODE_API_KEY`) para DeepSeek e Kimi

---

## Quickstart

```bash
# 1. Clone o framework
git clone https://github.com/mayrincktech/hermes-gsd-framework.git
cd hermes-gsd-framework

# 2. Configure credenciais
export GITHUB_TOKEN=seu_github_token
export NEON_CONNECTION_STRING=postgresql://user:pass@host/db
echo "seu_vercel_token" > /tmp/.vercel_tok

# 3. Provisione um novo app
python3 provision/provision_app.py \
  --name "Meu App" \
  --slug "meu-app" \
  --description "Descrição do app"
```

O script executa automaticamente em ~2 minutos:
1. Cria repo no GitHub
2. Clona o template Next.js (auth + i18n + DB + shadcn/ui)
3. Cria schema no Neon Postgres
4. Configura environment variables
5. Faz deploy no Vercel
6. Inicializa `.planning/` com templates
7. App rodando em produção com SSL

---

## Modos de operação

### Fast Mode
Para tarefas simples. Tempo alvo: **5-10 min**.

```
Idea → Light Spec → Architecture → Dev → QA → Deploy
```

Landing pages, CRUDs simples, MVPs, ferramentas internas.

### Enterprise Mode (Full)
Para produtos comerciais. Tempo alvo: **20-45 min**.

```
RESEARCH → ARCHITECTURE → UX DESIGN → PLAN → EXECUTE → UX REVIEW → TEST → VERIFY → DEPLOY
```

SaaS, multi-tenant, produtos complexos.

---

## Design Philosophy

### Inspiração
- **Apple HIG** — minimalista, premium, espaço em branco
- **Linear** — clean, escuro elegante, tipografia forte
- **Stripe** — profissional, confiança visual, animações sutis

### Obrigatório
- Mobile-first (375px base — todo código UI começa por mobile)
- Minimalista, premium, poucas cores (máx 3 principais)
- Tipografia forte, hierarquia visual clara
- Espaçamento consistente e generoso

### Proibido
- Bootstrap/Material Design look padrão
- Cards genéricos sem tratamento
- Interfaces genéricas que parecem template

---

## Credenciais

### GitHub
```bash
export GITHUB_TOKEN=ghp_seu_token
git config --global user.email "seu@email.com"  # DEVE bater com email da conta Vercel
```

### Vercel
Token com permissão para criar projects, setar env vars e desabilitar SSO protection.

### Neon
Cada app recebe schema isolado + tabelas de auth. Connection string usa hostname pooler (compatível com `@neondatabase/serverless`).

Veja [`docs/provision.md`](docs/provision.md) para detalhes e troubleshooting.

---

## Execution Metrics

O sucesso do framework é medido por dados, não por README bonito.

| Métrica | Meta |
|---|---|
| Tempo: Idea → Deploy | Fast <10min, Enterprise <45min |
| Rework rate | <30% |
| UX Score médio | ≥48/60 |
| QA Critical/High ao deployar | 0 |
| Builds sem erro (1a tentativa) | >90% |

**Sem projetos reais completados, o framework é só teoria.** Cada app provisionado registra métricas em STATE.md.

---

## Licença

MIT — use livremente, comercialmente ou não.
