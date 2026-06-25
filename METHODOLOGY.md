# GSD Methodology v8

**Get Shit Done** — um sistema production-ready para desenvolvimento autônomo com IA.

## Role System (Model-Agnostic)

O framework define papéis por **capabilities**, não por modelo. Modelos são trocáveis sem mudar o framework.

```yaml
# roles.yaml — configuração de roles
orchestrator:
  name: "Orchestrator + UX Designer"
  responsibilities: [research, architecture, ux_design, ux_review, planning, deploy]
  capabilities:
    visual_reasoning: true        # pode avaliar UX
    wireframe_generation: true     # pode criar wireframes
    ux_evaluation: true            # pode aplicar UX Score
    code_generation: false         # NÃO codifica
  current_implementation: "GLM-5.2"

code_executor:
  name: "Code AI"
  responsibilities: [write_code, write_tests, fix_code]
  capabilities:
    code_generation: true
    test_generation: true
    architecture_decisions: false  # não decide arquitetura
    ux_decisions: false            # não decide UX
  requirements:
    fast_inference: true           # precisa ser rápido
    supports_delegation: true      # precisa funcionar via delegate_task
  current_implementation: "DeepSeek V4 Flash/Pro via OpenCode Go"

qa_verifier:
  name: "QA AI"
  responsibilities: [code_review, security_check, contract_check]
  capabilities:
    code_review: true
    security_analysis: true
    type_safety_check: true
  requirements:
    different_model_family: true   # OBRIGATÓRIO: modelo diferente do executor
  current_implementation: "Kimi K2.7 Code via OpenCode Go"
```

**Para trocar um modelo:** basta que o novo atenda as `capabilities` e `requirements` do role. O framework não muda.

## Arquitetura

```
Orchestrator AI (role: orchestrator)
  │  — research, architecture, UX design, planning, deploy
  │
  ├── RESEARCH     → valida demanda antes de engenharia
  ├── ARCHITECTURE → trava stack antes de codar
  ├── UX DESIGN    → trava wireframes + design system antes de UI
  ├── PLANNING     → decomposição em tasks atômicas
  ├── CODING       → delegate to Code AI (role: code_executor)
  ├── UX REVIEW    → score objetivo (min 42/60)
  ├── TESTING      → build, lint, typecheck, tests
  ├── QA           → delegate to QA AI (role: qa_verifier — modelo DIFERENTE)
  └── DEPLOY       → produção
```

---

## Princípios Core

1. **Orchestrator pensa, Code AI executa, QA AI revisa** — nunca misturar roles
2. **Modelos diferentes para implementar e revisar** — mesmo modelo se auto-revisando é um padrão de falha conhecido
3. **Orchestrator não codifica** — escreve specs, não implementação
4. **Spec-driven** — RESEARCH → ARCHITECTURE → UX DESIGN → PLAN → EXECUTE → UX REVIEW → TEST → VERIFY → DEPLOY
5. **Estado persistente em arquivos** — `.planning/` directory
6. **Outcome over output** — resultado importa mais que volume
7. **Tasks atômicas e testáveis** — máx 5 arquivos, 500 linhas por task
8. **Research valida demanda** — antes de qualquer engenharia
9. **Arquitetura trava antes do código** — zero architecture drift mid-project
10. **Wireframes antes de código UI** — NUNCA começar React/Next.js sem wireframe aprovado
11. **Design System obrigatório** — todo projeto tem DESIGN-SYSTEM.md antes de tasks de UI
12. **Testes não são opcionais** — QA review não substitui rodar testes
13. **Mobile-first SEMPRE** — desenvolvimento começa por mobile (375px). Desktop é adaptação.

---

## Pipeline Completo

```
RESEARCH GATE (Orchestrator + Research Agent)
    ↓ (BUILD?)
BUSINESS VALIDATION (Orchestrator — viabilidade comercial)
    ↓ (viable?)
[CONTENT STRATEGY] (opcional — projetos com conteúdo)
    ↓
ARCHITECTURE GATE (Orchestrator — ARCHITECTURE.md)
    ↓ (locked)
UX DESIGN GATE (Orchestrator — DESIGN-SYSTEM.md + WIREFRAMES.md)
    ↓ (wireframes aprovados)
PLAN (Orchestrator — decomposição em waves)
    ↓
EXECUTE (Code AI — delegate_task)
    ↓
UX REVIEW (Orchestrator — UX Score ≥ 42/60) [apenas tasks com UI]
    ↓ (aprovado?)
TEST (Code AI — build, lint, typecheck, tests)
    ↓ (all pass?)
VERIFY (QA AI — code review, security, contracts) [modelo DIFERENTE]
    ↓ (0 critical/high?)
FIX (Code AI, se necessário)
    ↓
DEPLOY (Orchestrator)
    ↓
DONE (Definition of Done checklist)
```

---

## Roles & Responsabilidades

### Orchestrator AI (role: orchestrator)

- Define arquitetura (ARCHITECTURE.md)
- Define UX design (DESIGN-SYSTEM.md, WIREFRAMES.md)
- Executa Research Agent (validação de ideia)
- Quebra tasks em unidades atômicas
- Delega código para Code AI
- Delega QA para QA AI (modelo DIFERENTE)
- Executa UX Review (UX Score)
- Verifica testes
- Faz deploy

### Code AI (role: code_executor)

- Escreve código via delegation
- Segue instruções exatamente
- Segue DESIGN-SYSTEM.md e wireframes
- NÃO toma decisões arquiteturais ou de UX
- Retorna output estruturado

### QA AI (role: qa_verifier)

- Revisa TODOS os arquivos modificados
- Modelo diferente do executor — pega o que Code AI perde
- Roda build checks, security checks, type safety, contract compliance
- Retorna report categorizado: CRITICAL / HIGH / MEDIUM / LOW

---

## Regras de Delegação

| Task | Role que executa |
|---|---|
| Code tasks | code_executor |
| Test tasks | code_executor |
| QA tasks | qa_verifier (modelo DIFERENTE) |
| UX Design/Review | orchestrator (sem delegação) |
| Research/Planning | orchestrator (sem delegação) |

**Não delegar quando:**
- Debugging
- Fixes pequenos (1 arquivo)
- Mudanças simples de config

---

## Estrutura de Planning Files

```
.planning/
├── PROJECT.md
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── DESIGN-SYSTEM.md
├── WIREFRAMES.md
├── ROADMAP.md
├── STATE.md
├── config.json
└── phases/
    └── NN-phase-name/
        ├── NN-CONTEXT.md
        ├── NN-RESEARCH.md
        ├── NN-PLAN.md
        ├── NN-SUMMARY.md
        ├── NN-UX-REVIEW.md
        ├── NN-TEST-RESULTS.md
        └── NN-VERIFICATION.md
```

### STATE.md (obrigatório)

```markdown
## Current Phase
## Completed Tasks
## Pending Tasks
## Decisions Made
## Blockers
## Metrics (tasks completed, failures, rework count, UX avg score)
```

---

## Design Philosophy (GLOBAL)

### Inspiração

- **Apple HIG** — minimalista, premium, muito espaço em branco
- **Linear** — clean, escuro elegante, tipografia forte, micro-interações
- **Notion** — flexível, clean, foco no conteúdo
- **Stripe** — profissional, confiança visual, animações sutis

### Características obrigatórias

- Mobile-first (375px base — TODO código UI começa por mobile)
- Minimalista
- Premium
- Muito espaço em branco
- Poucas cores (máx 3 cores principais)
- Tipografia forte
- Hierarquia visual clara
- Espaçamento consistente
- Desktop é adaptação de mobile, nunca o inverso

### Proibido

- Bootstrap visual (look padrão)
- Material Design padrão (look Google)
- Cards genéricos sem tratamento
- Tabelas sem tratamento visual
- Telas com mais de 3 cores principais
- Interfaces genéricas
- Cards excessivos
- Muitas bordas
- Formulários longos sem quebra visual

---

## UX Persona

Ativar antes de qualquer tela ser implementada:

```
Você é um Product Designer Senior.
Seu objetivo NÃO é apenas fazer a tela funcionar.

Objetivos:
- Visual premium
- Experiência semelhante a apps líderes de mercado
- Hierarquia visual clara
- Espaçamento consistente
- Mobile-first
- Acessibilidade
- Conversão e retenção

Referências:
- Stripe, Linear, Notion, Airbnb, Apple, Arc Browser

Evite:
- Interfaces genéricas
- Cards excessivos
- Muitas bordas
- Muitas cores
- Tabelas feias
- Formulários longos
```

---

## Design System Template (obrigatório por projeto)

Todo projeto deve ter DESIGN-SYSTEM.md antes de qualquer task de UI.

```markdown
# Design System — [Project Name]

## Border Radius
- 16px (cards, containers)
- 8px (inputs, buttons)
- 999px (pills, badges)

## Spacing Scale (8px base)
- 8px, 16px, 24px, 32px, 48px, 64px

## Typography
- Heading XL: 32px / 700 / -0.02em
- Heading L: 24px / 700 / -0.01em
- Heading M: 20px / 600
- Body: 16px / 400 / 1.5
- Caption: 14px / 400 / 1.4
- Label: 12px / 500 / uppercase

## Sombras (máx 3 níveis)
- sm: 0 1px 2px rgba(0,0,0,0.05)
- md: 0 4px 6px rgba(0,0,0,0.07)
- lg: 0 10px 15px rgba(0,0,0,0.1)

## Cores (máx 3 principais)
- Primária: [definir]
- Secundária: [definir]
- Neutras: gray-50 → gray-900
- Sucesso: green-500
- Erro: red-500
- Aviso: amber-500

## Componentes Base
- Button: [variantes, tamanhos]
- Input: [estados, tamanhos]
- Card: [variantes]
- Table: [estilo, hover, zebra?]

## Referências Visuais (3 obrigatórias)
1. [app de referência] — [o que pegar emprestado]
2. [app de referência] — [o que pegar emprestado]
3. [app de referência] — [o que pegar emprestado]
```

---

## UX Score (UX REVIEW GATE)

A revisão de UX é objetiva com pontuação.

### Critérios

| Critério | Nota | Descrição |
|---|---|---|
| Hierarquia Visual | 0-10 | Elementos importantes se destacam? Ordem de leitura clara? |
| Legibilidade | 0-10 | Contraste, tamanho de fonte, espaçamento entre linhas |
| Espaçamento | 0-10 | Segue escala de spacing? Espaçamento generoso e consistente? |
| Mobile Experience | 0-10 | Funciona em 375px? Touch targets ≥44px? Sem scroll horizontal? |
| Acessibilidade | 0-10 | ARIA labels, contraste WCAG AA, navegação por teclado? |
| Premium Feel | 0-10 | Parece profissional? Espaço em branco adequado? Micro-interações? |

### Aprovação

- **Total ≥ 42/60** → APROVADO → prossegue para TEST
- **Total < 42/60** → REPROVADO → volta para EXECUTE com feedback específico

---

## Wireframe Format

Todo wireframe DEVE começar pela versão mobile (375px). Desktop é opcional e vem depois.

```
Tela: Dashboard (Mobile-first — 375px)
Referências: Linear (layout), Stripe (cards), Notion (tipografia)

┌───────────────────────┐
│ ☰  App Name    👤      │
├───────────────────────┤
│                        │
│  ┌────────────────┐    │
│  │ KPI: Projetos  │    │
│  │      12        │    │
│  └────────────────┘    │
│                        │
│  ┌────────────────┐    │
│  │ Pipeline       │    │
│  │ ●→●→○→○→○     │    │
│  └────────────────┘    │
│                        │
│  ┌────────────────┐    │
│  │ Tasks          │    │
│  │ • Task A       │    │
│  │ • Task B       │    │
│  └────────────────┘    │
│                        │
└───────────────────────┘

Desktop (≥768px) — adaptação:
┌─────────────────────────────────────┐
│ Header                               │
│ ├ Logo    ├ Busca    ├ Perfil        │
├─────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐│
│  │ KPI  │ │ KPI  │ │ KPI  │ │ KPI ││
│  └──────┘ └──────┘ └──────┘ └─────┘│
└─────────────────────────────────────┘
```

---

## Task Size Rules

- Modify ≤ 5 arquivos
- Alter ≤ 500 linhas total
- Ser ≤ 15 min de execução
- Ter responsabilidade única
- UI tasks devem referenciar wireframe específico de WIREFRAMES.md

---

## Quality Gates (9 total)

1. **Task Size Gate** (≤5 files, ≤500 lines)
2. **Architecture Gate** (stack locked)
3. **UX Design Gate** (wireframes + design system locked)
4. **UX Review Gate** (UX Score ≥ 42/60)
5. **Test Gate** (build + lint + typecheck + tests pass)
6. **Verification Gate** (QA review — 0 critical/high)
7. **Definition of Done Gate** (all checklist items pass)
8. **Build Gate**
9. **Outcome Gate**

---

## Definition of Done

```
[ ] Build passa
[ ] Typecheck passa
[ ] Lint sem erros
[ ] Tests passam
[ ] Sem erros no console
[ ] Sem TODO no código entregue
[ ] UX Review ≥ 42/60 (se task tem UI)
[ ] Documentação atualizada (se aplicável)
[ ] STATE.md atualizado
[ ] QA report: 0 CRITICAL, 0 HIGH
[ ] Deploy validado (se aplicável)
```

---

## Toolchain

| Camada | Serviço | Por quê |
|---|---|---|
| **Source control** | GitHub (`gh` CLI) | Repos privados, PRs, integração com Vercel |
| **Banco de dados** | Neon Postgres | Free tier, branches isolados por projeto |
| **Deploy/hosting** | Vercel | Deploy automático do Git, SSL, sem setup de servidor |
| **Execução** | Qualquer VPS com AI agent | Onde o pipeline roda — não hospeda apps |

---

## Phase Priority

- **P0** → Blocking MVP
- **P1** → Core
- **P2** → Enhancements
- **P3** → Optional

---

## Modos de Operação

### Fast Mode
Para tarefas simples onde o pipeline completo seria disproportional.

**Indicado para:** Landing pages, CRUDs simples, MVPs, ferramentas internas, dashboards básicos.

```
Idea → Light Spec → Architecture → Dev → QA → Deploy
```

- Sem Research Gate, Business Validation, UX Design Gate separados
- UX Reviewinline (Orchestrator avalia rapidamente)
- QA obrigatório (não pula)
- `.planning/` minimal (só STATE.md)

### Enterprise Mode (Full)
Para produtos comerciais, SaaS, sistemas complexos.

```
RESEARCH → BUSINESS → ARCHITECTURE → UX DESIGN → PLAN → EXECUTE → UX REVIEW → TEST → VERIFY → DEPLOY
```

- Todos os gates obrigatórios
- `.planning/` completo com features/, design system, wireframes

### Como escolher

| Critério | Fast | Enterprise |
|---|---|---|
| UI complexa | Não | Sim |
| Multi-tenant | Não | Sim |
| Novo produto | Não | Sim |
| Tempo alvo | 5-10 min | 20-45 min |
| Feature nova em app existente | Depende | Depende |

---

## Telemetry Contract

### Kanban Board — observabilidade nativa

O Hermes Kanban board é a fonte de verdade visual do pipeline. Após cada gate, o Orchestrator atualiza o Kanban:

| Evento | Ação |
|---|---|
| Gate começou | Card → "In Progress" |
| Gate passou | kanban_complete(card, result) |
| Gate falhou | kanban_block(card, reason) → "Blocked" |
| Task completou | Card body atualizado com files_count, lines_count |
| Feature deployada | Todos os cards → "Done" |

STATE.md continua como audit trail em markdown. Sem app separado, sem JSON, sem polling.

### Modelo de delegation

```yaml
# config.yaml
delegation:
  model: deepseek-v4-flash
  provider: custom:opencode-go
```

Per-task override:
```python
delegate_task(tasks=[
  {"goal": "...", "model": "deepseek-v4-flash"},
  {"goal": "...", "model": "kimi-k2.7-code"}
])
```

---

## Feature Lifecycle

### Uma feature por vez

Um app não pode ter duas features simultâneas em `active_feature`. Motivo: conflito de arquivos, deploys, e dependências.

### Fluxo

```
Kanban: To Do
    ↓ (Orchestrator inicia feature)
Kanban: In Progress
    ↓ (pipeline completo: RESEARCH → DEPLOY)
Kanban: Done → deployed_features[]
```

### Cada feature reinicia o pipeline

Cada feature passa por todos os gates do zero. Gates não acumulam entre features. Histórico de features anteriores é preservado em `deployed_features[]` e em `features/{id}/`.

### Versionamento

Cada feature deployada incrementa a versão do app (minor): `1.0.0` → `1.1.0`.

---

## Delegation Enforcement

### Regras obrigatórias

| Role | Config | Como |
|---|---|---|
| Orchestrator | Provider principal | Direto (não delega) |
| Code AI | `delegate_task` com role code_executor | Provider configurável |
| QA AI | `delegate_task` com role qa_verifier | **Modelo DIFERENTE do Code AI** |

### Proibições

- **Orchestrator NÃO codifica** — deve delegar via `delegate_task`
- **Mesmo modelo não revisa próprio código** — DeepSeek escreve, Kimi revisa
- **Sem task list, sem EXECUTE** — tasks devem estar criadas antes da execução

### Quando NÃO delegar

- Debugging (processo interativo)
- Fixes de 1 arquivo
- Mudanças de config
- Escrita de specs/docs (RESEARCH, ARCHITECTURE, UX DESIGN — Orchestrator faz direto)

---

## Task Management

### Formato

Tasks vivem em `.planning/features/{feature-id}/tasks/{NN}-slug.md` com frontmatter YAML.

Ver `schemas/task-format.md` para template completo.

### Regras

- ID: `{FEATURE_ID}-{TASK_ID}` (ex: `02-003`)
- Máx 5 arquivos por task
- Máx 500 linhas por task
- Dependencies devem estar completed antes de iniciar
- Status sincroniza com o Kanban board após cada mudança

---

## Execution Metrics (Acompanhar de perto)

O sucesso do framework é medido por dados reais, não por README bonito.

### Métricas por projeto

| Métrica | Meta | Como medir |
|---|---|---|
| Tempo: Idea → Deploy | Fast: <10min / Enterprise: <45min | Timestamp em STATE.md |
| Rework rate | <30% | Tasks que voltaram para EXECUTE / total |
| UX Score médio | ≥ 48/60 | Média de UX-REVIEW.md |
| QA: Critical/High | 0 ao deployar | VERIFICATION.md |
| Builds sem erro | >90% primeira tentativa | TEST-RESULTS.md |

### Métricas globais do framework

| Métrica | Meta | Como medir |
|---|---|---|
| Projetos completados | >10 para validar | Contagem de apps provisionados |
| Consistência visual entre projetos | Subjetivo, melhorando | Comparar screenshots |
| Retrabalho diminuindo ao longo do tempo | Tendência decrescente | Rework rate por mês |
| UX melhor que Claude/Cursor direto | Validação subjetiva | Comparação lado a lado |

**Sem dados, o framework é só teoria.** Cada projeto deve registrar essas métricas em STATE.md.

---

## Final Rules

- Orchestrator THINKS, Code AI BUILDS and TESTS, QA AI REVIEWS
- **Never use same model for implement and QA**
- **Never start UI code without approved wireframe**
- **Never skip Design System**
- Never mix roles
- Always research before planning new products
- Always lock architecture before coding
- Always wireframe before UI code
- Always UX review before tests (for UI tasks)
- Always test before QA review
- Always verify before deploy
- Always run Definition of Done checklist
- Optimize for execution, not theory

If system becomes slow or complex → reduce task size, not structure.
