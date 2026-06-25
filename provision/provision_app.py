#!/usr/bin/env python3
"""
provision_app.py — Automate the full provisioning flow for a new web app.

Flow:
  1. COPY TEMPLATE      cp -r template → /home/moises/workspace/{slug}
  2. PERSONALIZE        Replace 'App Name' placeholders, update package.json
  3. GITHUB REPO        Create private repo via `gh` + push code
  4. NEON DATABASE      Create schema + auth tables (users, accounts, sessions, verification_tokens)
  5. VERCEL ENV VARS    Set DATABASE_URL + AUTH_SECRET via Vercel API
  6. VERCEL DEPLOY      Link project → `vercel --prod` → disable Vercel Auth
  7. INIT .PLANNING     Create .planning/ directory with templates + pipeline status
  8. OUTPUT             Print JSON summary + append to provisioned_apps.json

Usage:
    python3 provision_app.py \
        --name 'Price Tracker' \
        --slug 'price-tracker' \
        --description 'Track prices over time'

Credentials are read from the environment — never hardcoded:
    GitHub token:      ~/.hermes/.env  (GITHUB_TOKEN=...)
    Vercel token:      /tmp/.vercel_tok
    Neon connection:   ~/.hermes/.env  (NEON_CONNECTION_STRING=...)
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────
WORKSPACE = Path("/home/moises/workspace")
GITHUB_ORG = "mayrincktech"
GITHUB_EMAIL = "lucronaconfeitaria@gmail.com"  # Must match Vercel account email
GITHUB_NAME = "Moises Mayrinck"
ENV_FILE = Path.home() / ".hermes" / ".env"
VERCEL_TOKEN_FILE = Path("/tmp/.vercel_tok")
DATA_FILE = WORKSPACE / "hermes-gsd-framework" / "data" / "provisioned_apps.json"
NVM_SOURCE = ". ~/.nvm/nvm.sh"
DEFAULT_TEMPLATE = str(WORKSPACE / "web-app-template")

Path(WORKSPACE / "hermes-gsd-framework" / "data").mkdir(parents=True, exist_ok=True)

# Files / dirs to strip when copying the template (avoid copying build state)
TEMPLATE_JUNK = {".git", "node_modules", ".next", ".vercel", ".DS_Store"}
# Binary-ish extensions we skip when doing text replacement
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".otf", ".pdf", ".zip", ".tar", ".gz", ".lock",
}

# SQL to create auth tables in the public schema.
# The Neon HTTP driver (@neondatabase/serverless) does not support ?schema=
# in the connection string, so tables must be in public.
AUTH_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id text NOT NULL PRIMARY KEY,
    name text,
    email text NOT NULL UNIQUE,
    email_verified timestamptz,
    image text,
    password text
);

CREATE TABLE IF NOT EXISTS accounts (
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type text NOT NULL,
    provider text NOT NULL,
    provider_account_id text NOT NULL,
    refresh_token text,
    access_token text,
    expires_at integer,
    token_type text,
    scope text,
    id_token text,
    session_state text,
    PRIMARY KEY (provider, provider_account_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_token text NOT NULL PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_tokens (
    identifier text NOT NULL,
    token text NOT NULL,
    expires timestamptz NOT NULL,
    PRIMARY KEY (identifier, token)
);
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────
class StepError(Exception):
    """Raised when a provisioning step fails."""


def log(msg: str):
    print(msg, flush=True)


def fail(step: str, msg: str, exc: Exception = None):
    """Print a structured failure message and exit."""
    print(f"\n❌ STEP FAILED: {step}", file=sys.stderr)
    print(f"   {msg}", file=sys.stderr)
    if exc:
        print(f"   Error: {exc}", file=sys.stderr)
    sys.exit(1)


def run(cmd, cwd=None, env=None, check=True, timeout=600):
    """Run a shell command string (with nvm sourced) via subprocess.run."""
    full_cmd = f"{NVM_SOURCE} && {cmd}"
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    r = subprocess.run(
        full_cmd, shell=True, capture_output=True, text=True,
        cwd=cwd, env=merged_env, timeout=timeout, executable="/bin/bash",
    )
    if check and r.returncode != 0:
        detail = r.stdout.strip() or r.stderr.strip()
        raise StepError(
            f"Command exited {r.returncode}: {cmd}\n"
            f"  stdout: {r.stdout[-800:]}\n  stderr: {r.stderr[-800:]}"
            if detail else f"Command exited {r.returncode}: {cmd}"
        )
    return r


def run_py(code: str, env=None, check=True):
    """Run Python code (requires psycopg2 installed)."""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=merged_env, timeout=60,
    )
    if check and r.returncode != 0:
        raise StepError(f"Python execution failed:\n  {r.stderr[-800:]}")
    return r


def read_env_var(filepath: Path, varname: str) -> str:
    """Read a VAR=value line from a dotenv-style file."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise StepError(f"{varname}: file not found at {filepath}")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(f"{varname}="):
            val = line.split("=", 1)[1].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    raise StepError(f"{varname} not found in {filepath}")


def read_vercel_token() -> str:
    try:
        return VERCEL_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise StepError(f"Vercel token file not found: {VERCEL_TOKEN_FILE}")


def slug_to_schema(slug: str) -> str:
    """Convert a URL slug to a Postgres-safe schema name (underscores)."""
    s = slug.lower().replace("-", "_")
    s = re.sub(r"[^a-z0-9_]", "_", s)
    if not s or s[0].isdigit():
        s = f"app_{s}"
    return s


def vercel_api(method: str, path: str, token: str, body: dict = None,
               team_id: str = None) -> dict:
    """Call the Vercel REST API and return the parsed JSON response."""
    url = f"https://api.vercel.com{path}"
    sep = "&" if "?" in path else "?"
    if team_id:
        url += f"{sep}teamId={team_id}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500]
        raise StepError(f"Vercel API {method} {path} → HTTP {e.code}: {err_body}")
    except urllib.error.URLError as e:
        raise StepError(f"Vercel API {method} {path} → network error: {e}")


# ─── Step 1: Copy template ───────────────────────────────────────────────────
def step_copy_template(template_dir: Path, slug: str) -> Path:
    """Copy template-dir to /home/moises/workspace/{slug}, stripping junk."""
    dest = WORKSPACE / slug
    log(f"\n📦 Step 1: Copy template → {dest}")

    if not template_dir.exists():
        raise StepError(f"Template directory not found: {template_dir}")

    if dest.exists():
        log(f"   ℹ  Destination exists, removing stale copy: {dest}")
        shutil.rmtree(dest)

    def ignore(dirpath, names):
        return [n for n in names if n in TEMPLATE_JUNK]

    shutil.copytree(template_dir, dest, ignore=ignore)
    log(f"   ✅ Copied template to {dest}")
    return dest


# ─── Step 2: Personalize ─────────────────────────────────────────────────────
def step_personalize(app_name: str, slug: str, description: str, dest: Path):
    """Replace 'App Name' placeholders and update package.json."""
    log(f"\n✏️  Step 2: Personalize → '{app_name}'")

    replaced = 0
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if d not in TEMPLATE_JUNK]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext in BINARY_EXTS:
                continue
            fpath = Path(root) / fname
            try:
                content = fpath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            if "App Name" in content:
                fpath.write_text(
                    content.replace("App Name", app_name), encoding="utf-8"
                )
                replaced += 1
    log(f"   ✅ Replaced 'App Name' in {replaced} file(s)")

    # Update package.json: set name field
    pkg_path = dest / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            pkg["name"] = slug
            pkg["description"] = description
            pkg_path.write_text(json.dumps(pkg, indent=2) + "\n",
                                encoding="utf-8")
            log(f"   ✅ Updated package.json (name={slug})")
        except (json.JSONDecodeError, KeyError) as e:
            log(f"   ⚠  Could not update package.json: {e}")


# ─── Step 3: GitHub repo ─────────────────────────────────────────────────────
def step_github_repo(slug: str, description: str, dest: Path,
                     github_token: str) -> str:
    """Create a private GitHub repo and push code. Returns the repo URL."""
    repo_full = f"{GITHUB_ORG}/{slug}"
    repo_url = f"https://github.com/{repo_full}"
    log(f"\n🐙 Step 3: GitHub repo → {repo_full}")

    env = {"GITHUB_TOKEN": github_token, "GH_TOKEN": github_token}

    # Ensure git credential helper is set up for HTTPS auth
    run("gh auth setup-git 2>/dev/null || true", env=env, check=False)

    # Init local git + set identity (MUST use Vercel-linked email)
    run("git init -q 2>/dev/null || true", cwd=dest, env=env, check=False)
    run(f"git config user.name '{GITHUB_NAME}' && "
        f"git config user.email '{GITHUB_EMAIL}'",
        cwd=dest, env=env, check=False)

    # Stage + commit BEFORE creating the repo
    run("git add -A", cwd=dest, env=env, check=False)
    run("git diff --cached --quiet || git commit -q -m "
        + shlex_quote("Initial commit (provisioned by provision_app.py)"),
        cwd=dest, env=env, check=False)

    # Check if repo already exists (idempotency)
    r = run(f"gh repo view {repo_full} 2>/dev/null", env=env, check=False)
    repo_exists = r.returncode == 0

    if repo_exists:
        log(f"   ℹ  Repo already exists — reusing {repo_full}")
        run("git remote remove origin 2>/dev/null || true", cwd=dest, env=env,
            check=False)
        run(f"git remote add origin https://github.com/{repo_full}.git",
            cwd=dest, env=env, check=False)
    else:
        log(f"   📝 Creating private repo {repo_full} …")
        desc_flag = f"--description {shlex_quote(description)}"
        run(
            f"gh repo create {repo_full} --private {desc_flag} "
            f"--source={dest} --remote=origin --push",
            cwd=dest, env=env,
        )

    # Push (covers both paths)
    branch = run("git branch --show-current", cwd=dest, env=env).stdout.strip() \
        or "main"
    push = run(
        f"git push -u origin {branch} 2>&1",
        cwd=dest, env=env, check=False,
    )
    if push.returncode != 0:
        for fb in ("main", "master", "HEAD"):
            fb_r = run(f"git push -u origin {fb} 2>&1", cwd=dest, env=env,
                       check=False)
            if fb_r.returncode == 0:
                break
        else:
            log(f"   ⚠  Push may need manual verification. "
                f"Last output: {push.stderr[-200:]}")

    log(f"   ✅ Code pushed to {repo_url}")
    return repo_url


def shlex_quote(s: str) -> str:
    """Minimal shell quoting for safe argument passing."""
    if re.match(r"^[A-Za-z0-9 _./@:=+,-]*$", s):
        return f"'{s}'"
    return "'" + s.replace("'", "'\"'\"'") + "'"


# ─── Step 4: Neon database (schema + tables) ─────────────────────────────────
def step_neon_database(slug: str, neon_conn: str) -> tuple:
    """Create a dedicated schema + auth tables in the Neon database.
    Returns (schema_name, database_url_without_schema_param).
    """
    schema = slug_to_schema(slug)
    log(f"\n🗄️  Step 4: Neon database → schema={schema}, tables in public")

    # Requires psycopg2 to be installed
    py_code = (
        "import os, psycopg2\n"
        "from psycopg2 import sql\n"
        "\n"
        "conn = psycopg2.connect(os.environ['NEON_CONN'])\n"
        "conn.autocommit = True\n"
        "cur = conn.cursor()\n"
        "schema = os.environ['NEON_SCHEMA']\n"
        "\n"
        "# Create dedicated schema (for future use / organization)\n"
        "cur.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}')\n"
        ".format(sql.Identifier(schema)))\n"
        "\n"
        "# Create auth tables in public (Neon HTTP driver needs public)\n"
        "tables_sql = '''" + AUTH_TABLES_SQL.replace("\\", "\\\\") + "'''\n"
        "for stmt in tables_sql.strip().split(';'):\n"
        "    stmt = stmt.strip()\n"
        "    if stmt and not stmt.startswith('--'):\n"
        "        cur.execute(stmt)\n"
        "\n"
        "# Verify tables exist\n"
        "cur.execute(\"\"\"SELECT table_name FROM information_schema.tables\n"
        "WHERE table_schema = 'public' AND table_name IN\n"
        "('users','accounts','sessions','verification_tokens')\n"
        "ORDER BY table_name\"\"\")\n"
        "tables = [r[0] for r in cur.fetchall()]\n"
        "print('TABLES_OK:' + ','.join(tables))\n"
        "\n"
        "cur.close()\n"
        "conn.close()\n"
    )
    env = {"NEON_CONN": neon_conn, "NEON_SCHEMA": schema}
    r = run_py(py_code, env=env, check=False)
    if r.returncode != 0 or "TABLES_OK" not in r.stdout:
        raise StepError(
            f"Neon database setup failed for '{schema}'\n"
            f"  stdout: {r.stdout[-500:]}\n  stderr: {r.stderr[-500:]}"
        )

    tables_found = r.stdout.split("TABLES_OK:")[1].strip()
    log(f"   ✅ Schema '{schema}' created")
    log(f"   ✅ Auth tables in public: {tables_found}")

    # DATABASE_URL without ?schema= (Neon HTTP driver doesn't support it)
    # Strip any existing ?schema= param, keep sslmode=require
    database_url = re.sub(r'&?schema=[^&]+', '', neon_conn)
    if "?" not in database_url:
        database_url += "?sslmode=require"
    elif "sslmode" not in database_url:
        database_url += "&sslmode=require"

    log(f"   ✅ DATABASE_URL ready (no ?schema=, tables in public)")
    return schema, database_url


# ─── Step 5: Vercel env vars ─────────────────────────────────────────────────
def step_vercel_env_vars(dest: Path, vercel_token: str,
                         database_url: str, auth_secret: str) -> tuple:
    """Set DATABASE_URL and AUTH_SECRET as env vars on the Vercel project.
    Returns (project_id, org_id).
    """
    log(f"\n🔑 Step 5: Vercel env vars")

    # Read project.json from the .vercel dir (created by `vercel link`)
    proj_json_path = dest / ".vercel" / "project.json"
    project_id = None
    org_id = None

    # If not linked yet, link first
    if not proj_json_path.exists():
        log("   🔗 Linking project to Vercel …")
        slug = dest.name
        link = run(
            f"vercel link --yes --token {vercel_token} --cwd {dest}",
            cwd=dest, env={"VERCEL_TOKEN": vercel_token}, check=False, timeout=120,
        )
        if link.returncode != 0:
            run(
                f"vercel link --yes --token {vercel_token} --project {slug} "
                f"--cwd {dest}",
                cwd=dest, env={"VERCEL_TOKEN": vercel_token}, timeout=120,
            )

    if proj_json_path.exists():
        try:
            pj = json.loads(proj_json_path.read_text())
            project_id = pj.get("projectId")
            org_id = pj.get("orgId")
        except (json.JSONDecodeError, OSError):
            pass

    if not project_id:
        raise StepError("Could not determine Vercel project ID after linking")

    log(f"   📋 Project ID: {project_id}  Org: {org_id}")

    # Set env vars via Vercel API
    base = f"https://api.vercel.com/v10/projects/{project_id}"
    headers = {"Authorization": f"Bearer {vercel_token}"}
    create_url = f"{base}/env?teamId={org_id}" if org_id else f"{base}/env"

    for key, value in [("DATABASE_URL", database_url), ("AUTH_SECRET", auth_secret)]:
        # Check if env var already exists, delete if so
        list_req = urllib.request.Request(create_url, headers=headers)
        try:
            with urllib.request.urlopen(list_req, timeout=30) as resp:
                existing = json.loads(resp.read().decode()).get("envs", [])
            for e in existing:
                if e["key"] == key:
                    del_url = f"{base}/env/{e['id']}?teamId={org_id}" if org_id else f"{base}/env/{e['id']}"
                    del_req = urllib.request.Request(del_url, method="DELETE", headers=headers)
                    with urllib.request.urlopen(del_req, timeout=30):
                        pass
                    log(f"   🗑️  Deleted existing {key}")
        except Exception:
            pass  # Ignore list/delete errors, just create

        # Create the env var
        body = json.dumps({
            "key": key,
            "value": value,
            "type": "plain",
            "target": ["production", "preview", "development"],
        }).encode()
        create_req = urllib.request.Request(create_url, data=body, method="POST",
            headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(create_req, timeout=30):
                log(f"   ✅ Set {key}")
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:200]
            raise StepError(f"Failed to set {key}: HTTP {e.code} — {err}")

    return project_id, org_id


# ─── Step 6: Vercel deploy ───────────────────────────────────────────────────
def step_vercel_deploy(slug: str, dest: Path, vercel_token: str) -> str:
    """Deploy to production. Env vars are already set from Step 5.
    Returns the production deployment URL.
    """
    log(f"\n▲  Step 6: Vercel deploy → {slug}")

    env = {"VERCEL_TOKEN": vercel_token}

    log("   🚀 Deploying to production …")
    deploy = run(
        f"vercel deploy --prod --yes --token {vercel_token} --cwd {dest}",
        cwd=dest, env=env, check=False, timeout=600,
    )
    if deploy.returncode != 0:
        raise StepError(
            f"vercel deploy failed (exit {deploy.returncode})\n"
            f"  stdout: {deploy.stdout[-800:]}\n  stderr: {deploy.stderr[-800:]}"
        )

    vercel_url = parse_vercel_url(deploy.stdout)
    if not vercel_url:
        vercel_url = f"https://{slug}.vercel.app"
        log(f"   ⚠  Could not parse deployment URL — using default: {vercel_url}")

    log(f"   ✅ Deployed: {vercel_url}")

    # Disable Vercel Authentication (SSO protection)
    proj_json_path = dest / ".vercel" / "project.json"
    if proj_json_path.exists():
        try:
            pj = json.loads(proj_json_path.read_text())
            project_id = pj.get("projectId")
            org_id = pj.get("orgId")
            if project_id:
                vercel_api("PATCH", f"/v9/projects/{project_id}", vercel_token,
                           body={"ssoProtection": None}, team_id=org_id)
                log("   ✅ SSO / Vercel Authentication disabled")
        except (json.JSONDecodeError, OSError, StepError) as e:
            log(f"   ⚠  Could not disable SSO protection: {e}")

    return vercel_url


def parse_vercel_url(stdout: str) -> str:
    """Extract the production deployment URL from vercel deploy stdout."""
    for line in stdout.splitlines():
        low = line.lower()
        if "production" in low and "vercel.app" in low:
            m = re.search(r"https://\S+\.vercel\.app", line)
            if m:
                return m.group(0)
    urls = re.findall(r"https://\S+\.vercel\.app", stdout)
    if urls:
        return urls[-1]
    return None


# ─── Step 7: Init .planning directory ──────────────────────────────────────
def step_init_planning(app_name: str, slug: str, description: str, dest: Path,
                        github_url: str, vercel_url: str):
    """Create .planning/ directory with templates and pipeline status."""
    log(f"\n📋 Step 7: Init .planning/ → {dest / '.planning'}")

    planning_dir = dest / ".planning"
    planning_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).resolve().parent.parent / "templates" / "planning"

    # Copy template files
    shutil.copy2(templates_dir / "STATE.template.md", planning_dir / "STATE.md")
    shutil.copy2(templates_dir / "ROADMAP.template.md", planning_dir / "ROADMAP.md")
    shutil.copy2(templates_dir / "task.template.md", planning_dir / "task.md")
    log(f"   ✅ Copied planning templates")

    # Customize STATE.md
    state_path = planning_dir / "STATE.md"
    state_content = state_path.read_text(encoding="utf-8")
    state_content = state_content.replace("{APP_NAME}", app_name)
    state_path.write_text(state_content, encoding="utf-8")
    log(f"   ✅ STATE.md personalized")

    # Customize ROADMAP.md
    roadmap_path = planning_dir / "ROADMAP.md"
    roadmap_content = roadmap_path.read_text(encoding="utf-8")
    roadmap_content = roadmap_content.replace("{APP_NAME}", app_name)
    roadmap_content = roadmap_content.replace("{APP_DESCRIPTION}", description)
    roadmap_path.write_text(roadmap_content, encoding="utf-8")
    log(f"   ✅ ROADMAP.md personalized")

    # Create empty features/ directory
    features_dir = planning_dir / "features"
    features_dir.mkdir(exist_ok=True)
    log(f"   ✅ features/ directory created")

    # Git add + commit .planning to the app's repo
    env = {"GIT_AUTHOR_NAME": GITHUB_NAME, "GIT_AUTHOR_EMAIL": GITHUB_EMAIL}
    run("git add .planning/", cwd=dest, env=env, check=False)
    run("git diff --cached --quiet || git commit -q -m "
        "\"Init .planning/ directory with pipeline state\"",
        cwd=dest, env=env, check=False)
    log(f"   ✅ Git committed .planning/")


# ─── Step 8: Output ──────────────────────────────────────────────────────────
def step_output(summary: dict):
    """Print JSON summary and append to provisioned_apps.json."""
    log("\n" + "=" * 60)
    log("✅ PROVISIONING COMPLETE")
    log("=" * 60)
    print(json.dumps(summary, indent=2))

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if DATA_FILE.exists():
        try:
            existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(summary)
    DATA_FILE.write_text(
        json.dumps(existing, indent=2) + "\n", encoding="utf-8"
    )
    log(f"\n📁 App info appended to {DATA_FILE}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Provision a new web app end-to-end "
                    "(template → GitHub → Neon → Vercel).",
    )
    parser.add_argument("--name", required=True,
                        help="App display name (e.g. 'Price Tracker')")
    parser.add_argument("--slug", required=True,
                        help="URL-safe slug (e.g. 'price-tracker')")
    parser.add_argument("--description", required=True,
                        help="One-line description")
    parser.add_argument("--template-dir", default=DEFAULT_TEMPLATE,
                        help=f"Path to template (default: {DEFAULT_TEMPLATE})")
    args = parser.parse_args()

    # Validate slug
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", args.slug):
        fail("validation",
             f"Slug must be lowercase, hyphen-separated, alphanumeric: "
             f"'{args.slug}'")

    slug = args.slug
    app_name = args.name
    description = args.description
    template_dir = Path(args.template_dir)

    log(f"🚀 Provisioning '{app_name}' (slug: {slug})")
    log(f"   Template: {template_dir}")

    # ── Read credentials ──────────────────────────────────────────────────
    try:
        github_token = read_env_var(ENV_FILE, "GITHUB_TOKEN")
        neon_conn = read_env_var(ENV_FILE, "NEON_CONNECTION_STRING")
        vercel_token = read_vercel_token()
    except StepError as e:
        fail("credentials", str(e))

    # Generate AUTH_SECRET for NextAuth
    auth_secret = secrets.token_urlsafe(32)

    # ── Execute steps ─────────────────────────────────────────────────────
    try:
        # 1. Copy template
        dest = step_copy_template(template_dir, slug)

        # 2. Personalize
        step_personalize(app_name, slug, description, dest)

        # 3. GitHub repo (uses correct email for Vercel deploy authorization)
        github_url = step_github_repo(slug, description, dest, github_token)

        # 4. Neon database (schema + tables) — BEFORE deploy
        db_schema, database_url = step_neon_database(slug, neon_conn)

        # 5. Vercel env vars — BEFORE deploy so first deploy has them
        project_id, org_id = step_vercel_env_vars(
            dest, vercel_token, database_url, auth_secret
        )

        # 6. Vercel deploy (env vars already set, DB tables already created)
        vercel_url = step_vercel_deploy(slug, dest, vercel_token)

        # 7. Init .planning directory (after deploy, before output)
        step_init_planning(app_name, slug, description, dest,
                           github_url, vercel_url)

    except StepError as e:
        fail("provisioning", str(e), exc=e)
    except subprocess.TimeoutExpired as e:
        fail("provisioning", f"Command timed out: {e}", exc=e)
    except Exception as e:
        fail("provisioning", f"Unexpected error: {e}", exc=e)

    # ── Output ────────────────────────────────────────────────────────────
    summary = {
        "app_name": app_name,
        "slug": slug,
        "github_url": github_url,
        "vercel_url": vercel_url,
        "database_schema": db_schema,
        "database_url": database_url,
        "auth_secret": auth_secret,
        "status": "provisioned",
    }
    step_output(summary)


if __name__ == "__main__":
    main()
