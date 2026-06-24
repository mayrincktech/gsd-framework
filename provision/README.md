# Provision Script

Automatiza o setup completo de um novo app web em ~2 minutos, zero intervenção manual:

1. **Copia o template** Next.js + shadcn/ui
2. **Personaliza** nome do app em todos os arquivos
3. **Cria repo** no GitHub e faz push (email correto para Vercel)
4. **Cria schema + tabelas** no Neon Postgres (auth tables em public)
5. **Seta env vars** no Vercel (DATABASE_URL + AUTH_SECRET)
6. **Faz deploy** no Vercel (produção, com tudo configurado)
7. **Salva output** JSON + append em provisioned_apps.json

## Uso

```bash
python3 provision_app.py \
  --name "Meu App" \
  --slug "meu-app" \
  --description "Uma descrição"
```

## Pré-requisitos

- Python 3.11+ com psycopg2-binary
- Node.js 22+ (nvm)
- gh CLI autenticado
- Vercel CLI instalado
- Conta Neon com connection string

## Credenciais

```bash
export GITHUB_TOKEN=ghp_...ort NEON_CONNECTION_STRING=postgresql://...
echo "vcp_..." > /tmp/.vercel_tok
```

Veja `docs/provision.md` para arquitetura completa, configuração e troubleshooting.
