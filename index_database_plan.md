Don't use any of those tools as your primary solution. For a **multi-agent swarm doing real coding work**, you need two completely different things that none of those tools fully address together. Here's the complete picture:

## The Two Distinct Problems

**Problem 1 — Codebase Structure Index** (what agents query to find code)
**Problem 2 — Agent Working Memory** (what agents remember across turns and handoffs)

These require different storage backends, different query patterns, and different update strategies. Conflating them is why off-the-shelf solutions fall short.

***

## For Codebase Index: Build Your Own on CocoIndex + Tree-sitter

**Don't use mem0, A-mem, Memori, or MemOS for this** — they're designed for conversational memory, not code structure.  CocoIndex with Tree-sitter is the right foundation — incremental processing (only reindexes changed files), Rust core for performance, and it chunks code by AST syntax nodes rather than arbitrary line breaks.  The key advantage is that when a builder agent edits `src/auth.py`, only that file's chunks are re-embedded — not the whole repo. [opencode](https://opencode.ai/docs/cli/)

Your custom layer on top should add **three indexes** that generic tools never build:

```python
# src/memory/codebase_index.py
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import json

@dataclass
class SymbolRecord:
    """One entry per function/class/method in the codebase."""
    fqn: str           # fully qualified name: src.auth.UserService.login
    kind: str          # function | class | method | variable | import
    file: str          # relative path
    line_start: int
    line_end: int
    signature: str     # def login(self, user: str, pw: str) -> bool
    docstring: str
    embedding: list[float] = field(default_factory=list)

@dataclass
class DependencyEdge:
    """Directed import/call edge between symbols."""
    caller_fqn: str
    callee_fqn: str
    edge_type: str     # imports | calls | inherits | instantiates

@dataclass
class WorktreeSnapshot:
    """Per-agent worktree state — what each agent has changed."""
    agent_name: str
    branch: str
    modified_files: list[str]
    added_symbols: list[str]
    removed_symbols: list[str]
    timestamp: float


class CodebaseIndex:
    """
    Three-layer codebase index built for multi-agent swarm use.

    Layer 1 — Symbol table (SQLite):
        Fast exact lookup by FQN, file, or kind.
        "What is the signature of UserService.login?"
        "What files does this module export?"

    Layer 2 — Semantic vector index (Postgres + pgvector via CocoIndex):
        Semantic similarity search across code chunks.
        "Find code similar to this auth pattern"
        "What functions handle JWT token validation?"

    Layer 3 — Dependency graph (SQLite adjacency list):
        Multi-hop structural queries.
        "What calls UserService.login?"
        "What would break if I change this interface?"
        "Show the import chain from main to this function"

    All three update incrementally on file change — no full re-index.
    WorktreeSnapshot tracks per-agent divergence from main.
    """

    def __init__(self, db_path: str = ".polyglot/index.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS symbols (
                    fqn         TEXT PRIMARY KEY,
                    kind        TEXT NOT NULL,
                    file        TEXT NOT NULL,
                    line_start  INTEGER,
                    line_end    INTEGER,
                    signature   TEXT,
                    docstring   TEXT,
                    updated_at  REAL
                );

                CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);
                CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);

                CREATE TABLE IF NOT EXISTS dependencies (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    caller_fqn  TEXT NOT NULL,
                    callee_fqn  TEXT NOT NULL,
                    edge_type   TEXT NOT NULL,
                    UNIQUE(caller_fqn, callee_fqn, edge_type)
                );

                CREATE INDEX IF NOT EXISTS idx_dep_caller ON dependencies(caller_fqn);
                CREATE INDEX IF NOT EXISTS idx_dep_callee ON dependencies(callee_fqn);

                CREATE TABLE IF NOT EXISTS worktree_snapshots (
                    agent_name      TEXT NOT NULL,
                    branch          TEXT NOT NULL,
                    modified_files  TEXT,   -- JSON array
                    added_symbols   TEXT,   -- JSON array
                    removed_symbols TEXT,   -- JSON array
                    timestamp       REAL,
                    PRIMARY KEY (agent_name, branch)
                );

                CREATE TABLE IF NOT EXISTS agent_memory (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    agent_name  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,   -- JSON
                    expires_at  REAL,            -- NULL = permanent
                    created_at  REAL,
                    UNIQUE(session_id, agent_name, key)
                );

                CREATE INDEX IF NOT EXISTS idx_mem_agent ON agent_memory(agent_name);
                CREATE INDEX IF NOT EXISTS idx_mem_session ON agent_memory(session_id);
            """)

    # ── Symbol table ───────────────────────────────────────────────────────────

    def upsert_symbol(self, rec: SymbolRecord) -> None:
        import time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO symbols
                    (fqn, kind, file, line_start, line_end, signature, docstring, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(fqn) DO UPDATE SET
                    kind=excluded.kind, file=excluded.file,
                    line_start=excluded.line_start, line_end=excluded.line_end,
                    signature=excluded.signature, docstring=excluded.docstring,
                    updated_at=excluded.updated_at
            """, (rec.fqn, rec.kind, rec.file, rec.line_start, rec.line_end,
                  rec.signature, rec.docstring, time.time()))

    def get_symbol(self, fqn: str) -> SymbolRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT fqn,kind,file,line_start,line_end,signature,docstring "
                "FROM symbols WHERE fqn=?", (fqn,)
            ).fetchone()
        if not row:
            return None
        return SymbolRecord(*row)

    def symbols_in_file(self, file: str) -> list[SymbolRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT fqn,kind,file,line_start,line_end,signature,docstring "
                "FROM symbols WHERE file=? ORDER BY line_start", (file,)
            ).fetchall()
        return [SymbolRecord(*r) for r in rows]

    def remove_file_symbols(self, file: str) -> None:
        """Call when a file is deleted or fully rewritten."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM symbols WHERE file=?", (file,))

    # ── Dependency graph ───────────────────────────────────────────────────────

    def add_edge(self, caller: str, callee: str, edge_type: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO dependencies (caller_fqn, callee_fqn, edge_type)
                VALUES (?,?,?)
            """, (caller, callee, edge_type))

    def callers_of(self, fqn: str, edge_type: str | None = None) -> list[str]:
        """Who calls/imports/inherits this symbol?"""
        with sqlite3.connect(self.db_path) as conn:
            if edge_type:
                rows = conn.execute(
                    "SELECT caller_fqn FROM dependencies "
                    "WHERE callee_fqn=? AND edge_type=?", (fqn, edge_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT caller_fqn FROM dependencies WHERE callee_fqn=?", (fqn,)
                ).fetchall()
        return [r[0] for r in rows]

    def callees_of(self, fqn: str) -> list[str]:
        """What does this symbol call/import/inherit?"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT callee_fqn, edge_type FROM dependencies WHERE caller_fqn=?", (fqn,)
            ).fetchall()
        return [(r[0], r [opencode](https://opencode.ai/docs/cli/)) for r in rows]

    def impact_radius(self, fqn: str, depth: int = 3) -> set[str]:
        """
        BFS: find all symbols that transitively depend on this one.
        Used by reviewer/supervisor to assess change blast radius.
        """
        visited = set()
        frontier = {fqn}
        for _ in range(depth):
            next_frontier = set()
            for node in frontier:
                for caller in self.callers_of(node):
                    if caller not in visited:
                        next_frontier.add(caller)
                        visited.add(caller)
            frontier = next_frontier
        return visited

    # ── Worktree snapshots ─────────────────────────────────────────────────────

    def update_worktree_snapshot(self, snap: WorktreeSnapshot) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO worktree_snapshots
                    (agent_name, branch, modified_files, added_symbols,
                     removed_symbols, timestamp)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(agent_name, branch) DO UPDATE SET
                    modified_files=excluded.modified_files,
                    added_symbols=excluded.added_symbols,
                    removed_symbols=excluded.removed_symbols,
                    timestamp=excluded.timestamp
            """, (snap.agent_name, snap.branch,
                  json.dumps(snap.modified_files),
                  json.dumps(snap.added_symbols),
                  json.dumps(snap.removed_symbols),
                  snap.timestamp))

    def active_worktrees(self) -> list[WorktreeSnapshot]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT agent_name,branch,modified_files,added_symbols,"
                "removed_symbols,timestamp FROM worktree_snapshots"
            ).fetchall()
        return [
            WorktreeSnapshot(
                agent_name=r[0], branch=r [opencode](https://opencode.ai/docs/cli/),
                modified_files=json.loads(r[2] or "[]"),
                added_symbols=json.loads(r[3] or "[]"),
                removed_symbols=json.loads(r[4] or "[]"),
                timestamp=r[5],
            )
            for r in rows
        ]

    def conflict_check(self, agent_a: str, agent_b: str) -> list[str]:
        """Return files modified by both agents — potential merge conflicts."""
        snaps = {s.agent_name: s for s in self.active_worktrees()}
        a = set(snaps.get(agent_a, WorktreeSnapshot(agent_a,"",[], [], [], 0)).modified_files)
        b = set(snaps.get(agent_b, WorktreeSnapshot(agent_b,"",[], [], [], 0)).modified_files)
        return list(a & b)

    # ── Agent working memory ───────────────────────────────────────────────────

    def mem_set(self, session_id: str, agent_name: str, role: str,
                key: str, value: any, ttl_seconds: float | None = None) -> None:
        """Store a key-value memory entry for an agent."""
        import time
        expires_at = (time.time() + ttl_seconds) if ttl_seconds else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO agent_memory
                    (session_id, agent_name, role, key, value, expires_at, created_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(session_id, agent_name, key) DO UPDATE SET
                    value=excluded.value, expires_at=excluded.expires_at,
                    created_at=excluded.created_at
            """, (session_id, agent_name, role, key,
                  json.dumps(value), expires_at, time.time()))

    def mem_get(self, session_id: str, agent_name: str, key: str) -> any:
        import time
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT value, expires_at FROM agent_memory
                WHERE session_id=? AND agent_name=? AND key=?
            """, (session_id, agent_name, key)).fetchone()
        if not row:
            return None
        value, expires_at = row
        if expires_at and time.time() > expires_at:
            return None   # expired
        return json.loads(value)

    def mem_get_all(self, session_id: str, agent_name: str) -> dict:
        """Get all non-expired memory for an agent in a session."""
        import time
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT key, value, expires_at FROM agent_memory
                WHERE session_id=? AND agent_name=?
            """, (session_id, agent_name)).fetchall()
        now = time.time()
        return {
            r[0]: json.loads(r [opencode](https://opencode.ai/docs/cli/))
            for r in rows
            if not r[2] or now <= r[2]
        }

    def mem_handoff(self, session_id: str,
                    from_agent: str, to_agent: str, to_role: str) -> None:
        """
        Copy handoff-scoped memory from one agent to the next.
        Only copies keys prefixed with 'handoff:' — ephemeral keys stay behind.
        """
        import time
        all_mem = self.mem_get_all(session_id, from_agent)
        for key, value in all_mem.items():
            if key.startswith("handoff:"):
                self.mem_set(session_id, to_agent, to_role, key, value)
```

***

## Why Not the Tools You Listed

| Tool | Problem |
|---|---|
| **mem0 / A-mem / Memori** | Conversational memory only — no code structure awareness, no symbol tables |
| **MemOS / MemMachine** | Research prototypes, not production-grade, no Tree-sitter integration |
| **CodexGraph** | Graph DB approach is correct but requires Neo4j + heavy setup — SQLite adjacency list gives you 90% of the value |
| **code-index-mcp / codeindex** | Read-only search tools — no agent working memory, no worktree tracking |
| **CocoIndex** | ✅ Use this for the semantic vector layer only — it doesn't do symbol tables or agent memory |
| **LangChain conversational memory** | Completely wrong category — chat history buffers, not codebase indexes |

## The Right Stack

```
┌─────────────────────────────────────────────┐
│           CodebaseIndex (yours)             │
├──────────────┬──────────────┬───────────────┤
│ Symbol Table │  Dep Graph   │ Agent Memory  │
│   SQLite     │   SQLite     │   SQLite      │
├──────────────┴──────────────┴───────────────┤
│     CocoIndex + Tree-sitter + pgvector      │
│        (semantic chunk search only)         │
└─────────────────────────────────────────────┘
```

Build your own `CodebaseIndex` as above — it's ~400 lines and gives you symbol lookup, impact radius, conflict detection, and agent handoff memory in one local SQLite file with zero external dependencies except CocoIndex for the semantic layer.
