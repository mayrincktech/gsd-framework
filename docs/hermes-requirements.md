# Hermes GSD Framework — Hermes Requirements

O Hermes GSD Framework roda sobre o [Hermes Agent](https://hermes-agent.nousresearch.com) e depende de customizações específicas. Este documento lista todos os pré-requisitos e patches necessários.

---

## Hermes Agent (Base)

O Hermes é o orquestrador que executa o pipeline GSD. Ele fornece:

- **delegate_task** — delegação de tasks para subagentes (Code AI, QA AI)
- **Kanban board** — observabilidade nativa do pipeline
- **terminal** — execução de comandos (git, npm, vercel CLI)
- **file tools** — leitura/escrita de specs, planning files, código
- **web tools** — research, validação de mercado
- **cron jobs** — automação de tarefas recorrentes
- **memory** — persistência de preferências e contexto entre sessões

---

## Patches Obrigatórios

O `hermes update` sobrescreve o core. Estas customizações DEVEM ser reaplicadas após cada update.

### Runner Automático

Todos os patches abaixo são reaplicados automaticamente via:

```bash
python3 ~/.hermes/scripts/post_update_patches.py
```

Recomendado: configurar como cron job após `hermes update`.

---

### 1. Delegation Per-Task Model Override

**O que faz:**
- Permite que cada `delegate_task` use modelo/provider diferente na mesma sessão
- Faz `_load_config()` ler do disco em cada chamada (mudanças de config têm efeito imediato)
- **Sem este patch:** todos os subagentes usam o mesmo modelo do parent — inviabiliza o principio de QA com modelo diferente

**Por que o GSD precisa:**
O GSD delega código para DeepSeek e QA para Kimi (modelo diferente). Sem o patch, não é possível trocar modelo entre delegações.

**Uso:**

```python
# Method 1: Global config switch (sequential calls)
hermes config set delegation.model "deepseek-v4-flash"
delegate_task(goal="write API")

hermes config set delegation.model "kimi-k2.7-code"
delegate_task(goal="review code")

# Method 2: Per-task override (batch calls)
delegate_task(tasks=[
  {"goal": "write API", "model": "deepseek-v4-flash", "provider": "custom:opencode-go"},
  {"goal": "review code", "model": "kimi-k2.7-code", "provider": "custom:opencode-go"}
])
```

**Skill de referência:** `devops/hermes-delegation-patch`
**Script:** `~/.hermes/skills/devops/hermes-delegation-patch/scripts/apply_delegation_patch.py`

---

### 2. Neon RAG Memory Plugin (psycopg2)

**O que faz:**
- Restaura o plugin de memória RAG baseado em Neon Postgres + pgvector
- Usa psycopg2 em vez de httpx para conexão com Neon
- **Sem este patch:** memória semântica (`supabase_recall`) não funciona após update

**Por que o GSD precisa:**
Research Agent e contexto de projeto dependem de memória semântica para recall de decisões anteriores, padrões identificados, e contexto de mercado.

**Skill de referência:** `devops/hermes-neon-rag-patch`
**Script:** `~/.hermes/skills/devops/hermes-neon-rag-patch/scripts/apply_neon_rag_patch.py`

---

### 3. Gemini Image Fallback

**O que faz:**
- Adiciona Gemini 2.5 Flash Image como fallback quando FAL.ai falha
- **Sem este patch:** geração de imagens pode falhar silenciosamente

**Por que o GSD precisa:**
Geração de wireframes visuais, protótipos de UI, e assets de design podem usar geração de imagem durante o UX Design Gate.

**Skill de referência:** `devops/hermes-gemini-image-fallback`
**Script:** `~/.hermes/skills/devops/hermes-gemini-image-fallback/scripts/apply_gemini_fallback.py`

---

## Provider Configuration

O GSD usa o provider `custom:opencode-go` para delegação de código e QA.

### OpenCode Go

Endpoint: `https://opencode.ai/zen/go/v1`
API Key env var: `OPENCODE_API_KEY`

#### Modelos disponíveis para GSD

| Model ID | Role | Quando usar |
|---|---|---|
| `deepseek-v4-flash` | code_executor | Default para todas as tasks de código. Rápido, barato, alta qualidade. |
| `deepseek-v4-pro` | code_executor | Tasks pesadas/complexas quando flash não é suficiente. |
| `kimi-k2.7-code` | qa_verifier | QA review. Modelo diferente de DeepSeek — pega o que DeepSeek missed. |

#### ⚠️ Pitfalls de Model IDs

- **`kimi-k2.7` (sem `-code`) → HTTP 401.** O ID correto é `kimi-k2.7-code`.
- **Case-sensitive e exato.** Sem prefixes como `-latest`.
- **Verificar modelos disponíveis:**
  ```bash
  curl -s https://opencode.ai/zen/go/v1/models \
    -H "Authorization: Bearer $OPENCODE_API_KEY" \
    | python3 -m json.tool | grep '"id"'
  ```

#### Config global no config.yaml

```yaml
delegation:
  model: deepseek-v4-flash
  provider: custom:opencode-go
```

---

## Variáveis de Ambiente

```bash
# .env (~/.hermes/.env)
GITHUB_TOKEN=ghp_...               # GitHub API para repos, PRs
NEON_CONNECTION_STRING=postgresql://...  # Neon Postgres
OPENCODE_API_KEY=ocg_...           # OpenCode Go provider (DeepSeek, Kimi)

# Vercel (separate file)
VERCEL_TOKEN=...                   # /tmp/.vercel_tok
```

---

## Skills do Hermes Utilizadas

| Skill | Uso no GSD |
|---|---|
| `workflow/gsd-methodology` | A metodologia completa (este framework) |
| `workflow/research-agent` | Research Gate — validação de demanda |
| `software-development/writing-plans` | Decomposição de tasks no PLAN |
| `devops/hermes-delegation-patch` | Multi-model delegation |
| `devops/nextjs-vercel-neon-deploy` | Provisioning detalhado + pitfalls |
| `autonomous-ai-agents/kanban-codex-lane` | Kanban lifecycle patterns |

---

## Setup Checklist

```bash
# 1. Instalar Hermes Agent
#    https://hermes-agent.nousresearch.com/docs

# 2. Aplicar patches obrigatórios
python3 ~/.hermes/scripts/post_update_patches.py

# 3. Verificar delegation patch
grep "Per-task model/provider override" ~/.hermes/hermes-agent/tools/delegate_tool.py

# 4. Configurar provider
hermes config set delegation.provider "custom:opencode-go"
hermes config set delegation.model "deepseek-v4-flash"

# 5. Carregar skill GSD
#    skill_view(name="gsd-methodology")

# 6. Configurar credenciais
export GITHUB_TOKEN=ghp_...
export NEON_CONNECTION_STRING=postgresql://...
echo "$OPENCODE_API_KEY"  # deve estar no .env
echo "vercel_token" > /tmp/.vercel_tok

# 7. Testar delegation com modelo diferente
delegate_task(goal="echo hello", model="kimi-k2.7-code")
```
