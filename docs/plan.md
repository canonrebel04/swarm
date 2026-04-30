# Swarm Repo Setup Fix — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fix all setup/import problems so `pip install -r requirements.txt` works and the app runs.

**Architecture:** Generate a requirements.txt from the existing pyproject.toml + poetry.lock, create missing __init__.py files in 10 package directories, and update README to reflect the correct install method.

**Tech Stack:** Python 3.12+, Poetry (build system), pip

---

## Root Cause Summary

| # | Problem | Impact |
|---|---------|--------|
| 1 | No `requirements.txt` — project uses Poetry but README says `pip install -r requirements.txt` | Can't install deps |
| 2 | Missing `__init__.py` in 10 package directories | ImportErrors on any cross-package import |
| 3 | README entry point wrong — says `python src/api/server.py` instead of `swarm serve` | Confusion on how to run |

---

### Task 1: Generate requirements.txt from poetry.lock

**Objective:** Create a valid requirements.txt so `pip install -r requirements.txt` works.

**Files:**
- Create: `requirements.txt`

**Step 1: Export from poetry.lock**

Run:
```bash
cd /tmp/swarm
pip install poetry  # temporary
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

Or manually extract from pyproject.toml:
```
textual>=0.48.0
typer>=0.9.0
aiosqlite>=0.19.0
pydantic>=2.0.0
aiohttp>=3.9.0
fastapi>=0.100.0
uvicorn>=0.23.0
paramiko>=4.0.0
spacetimedb-sdk>=0.7.0
docker>=7.1.0
pyyaml>=6.0.3
```

**Step 2: Verify install works**

```bash
cd /tmp/swarm
pip install -r requirements.txt
```

Expected: all packages install without errors.

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "fix: add requirements.txt for pip install support"
```

---

### Task 2: Create missing __init__.py files

**Objective:** Fix ImportErrors by adding __init__.py to all Python package directories that lack one.

**Files (all CREATE):**
- `src/utils/__init__.py`
- `src/skills/__init__.py`
- `src/skills/definitions/__init__.py`
- `src/cli/__init__.py`
- `src/cli/commands/__init__.py`
- `src/api/__init__.py`
- `src/agents/__init__.py`
- `src/agents/definitions/__init__.py`
- `src/roles/contracts/__init__.py`
- `src/tui/screens/__init__.py`

**Step 1: Create all files**

```bash
for dir in \
  src/utils src/skills src/skills/definitions \
  src/cli src/cli/commands \
  src/api \
  src/agents src/agents/definitions \
  src/roles/contracts \
  src/tui/screens; do
  touch /tmp/swarm/$dir/__init__.py
done
```

**Step 2: Verify imports work**

```bash
cd /tmp/swarm
python -c "from src.cli.app import app; print('CLI app import OK')"
python -c "from src.api.server import app; print('API server import OK')"
python -c "from src.tui.app import SwarmApp; print('TUI import OK')"
```

Expected: All three print "OK" without ImportErrors.

**Step 3: Commit**

```bash
git add src/*/__init__.py src/*/*/__init__.py
git commit -m "fix: add missing __init__.py files for package imports"
```

---

### Task 3: Update README with correct install and run instructions

**Objective:** Fix README so newcomers don't hit the same wall.

**Files:**
- Modify: `README.md`

**Step 1: Replace install section**

Old (lines 14-25):
```markdown
## Quick Start

1. Clone the repository...
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
```

New:
```markdown
## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/canonrebel04/swarm.git
   cd swarm
   ```

2. Create a virtual environment and install:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Or with Poetry:
   ```bash
   poetry install
   ```

3. Set environment variables:
   ```bash
   export SWARM_API_KEY=your-secret-key
   ```

4. Verify installation:
   ```bash
   swarm --help
   ```

5. Start the TUI:
   ```bash
   swarm tui
   ```
   Or start the API server:
   ```bash
   swarm serve
   ```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: fix install instructions — use pip or poetry, correct entry points"
```

---

### Task 4: Verify end-to-end

**Objective:** Confirm everything works end-to-end.

**Step 1: Full install test**

```bash
cd /tmp/swarm
python -m venv .venv-test
source .venv-test/bin/activate
pip install -r requirements.txt
```

**Step 2: Smoke test imports**

```bash
python -c "
from src.cli.app import app
from src.api.server import app as api_app
from src.tui.app import SwarmApp
from src.orchestrator.coordinator import coordinator
from src.messaging.event_bus import event_bus
from src.runtimes.registry import registry
from src.roles.registry import role_registry
from src.safety.enforcer import SafetyEnforcer
print('ALL IMPORTS OK')
"
```

**Step 3: Verify CLI works**

```bash
swarm --help
```

Expected: Typer help output with commands: init, doctor, logs, roles, runtimes, tui, cleanup, setup, serve.

---

## Verification Checklist

- [ ] `pip install -r requirements.txt` succeeds
- [ ] All 10 missing `__init__.py` files created
- [ ] `python -c "from src.cli.app import app"` succeeds
- [ ] `swarm --help` shows all commands
- [ ] README instructions are accurate
- [ ] Three clean commits
