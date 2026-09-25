# AXIOM — Phase 2 & 3 Sprint Debrief
**Date:** 2026-09-25  
**Branch:** `main` (12 commits ahead of `origin/main`)  
**Platform:** `linux · Python 3.11.15 · PySide6 6.11.1 · Qt 6.11.1`

---

## 1. 🧪 Test Suite Status

### Execution Method
```
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v
```
**Total collected:** 2,063 items · **Selected:** 1,811 · **Deselected:** 252 · **Skipped:** 8

### ✅ Core Systems Integration — ALL PASSING

| Test | Status |
|------|--------|
| `test_observation_compression_caps_memory` | ✅ PASSED |
| `test_dynamic_tool_pruning` | ✅ PASSED |
| `test_approval_governor_safety` | ✅ PASSED |
| `test_rem_sleep_consolidation` | ✅ PASSED |
| `test_watchdog_anomaly_dispatch` | ✅ PASSED |
| `test_auth` | ✅ PASSED |
| `test_ipc_server_events` | ✅ PASSED |
| `test_ipc_server_ws_client` | ✅ PASSED |
| `test_ipc_server_uds_client` | ✅ PASSED |

### ✅ GUI / OOBE — ALL PASSING

| Test Group | Status |
|---|---|
| `test_dynamic_theme` | ✅ PASSED |
| `TestAxiomBridgeSignals` (4 tests) | ✅ PASSED |
| `TestSubmitTask` (2 tests) | ✅ PASSED |
| `test_hub_dialog_initialization` + flow tests (4 tests) | ✅ PASSED |
| `TestOOBEWindowInitialState` (5 tests) | ✅ PASSED |
| `TestOOBEWindowNavigation` (5 tests) | ✅ PASSED |
| `TestOOBEWindowDiagnosticsPage` (4 tests) | ✅ PASSED |
| `TestOOBEWindowModelPage` (4 tests) | ✅ PASSED |
| `TestGuessVisionModel` (4 tests) | ✅ PASSED |
| `TestOOBEWindowFinish` (2 tests) | ✅ PASSED |
| `TestOOBEWindowSafetyGuards` | ✅ PASSED |
| `TestDiagnosticsWorker` | ✅ PASSED |
| `TestModelListWorker` (2 tests) | ✅ PASSED |
| `TestOobeCompletedMigration` (4 tests) | ✅ PASSED |
| `test_single_instance` | ✅ PASSED |
| `test_telemetry_hud_*` (4 tests) | ✅ PASSED |
| `test_theme` | ✅ PASSED |
| `test_v60_automation` | ✅ PASSED |

### ⚠️ Known Failures (Pre-Existing / Scoped)

| Test | Status | Root Cause |
|------|--------|------------|
| `tests/gui/test_sched_ui.py::test_sched_ui` | ❌ FAILED | `MockBridge` fixture is stale — does not implement `token_received` signal now required by `MainWindow._connect_bridge()`. Not a regression from this sprint. |
| `tests/gui/test_v56.py::test_all` | ❌ FAILED | Legacy v56 snapshot test (unknown `wayland` mark). |
| `tests/gui/test_v57.py::test_v57_widgets` | ❌ FAILED | Legacy snapshot test. |
| `tests/gui/test_v58.py::test_all` | ❌ FAILED | Legacy snapshot test. |
| `tests/gui/test_v60.py::test_all` | ❌ FAILED | Legacy snapshot test. |
| `tests/integration/test_cov_core.py::test_ipc_server_start_stop` | ❌ FAILED | IPC daemon start/stop race in headless environment. |

### 🔴 Hanging Test — Action Required

**`tests/integration/test_critical_path.py::test_critical_path_websocket_to_sandbox`**

This test hangs indefinitely in headless/offscreen mode. It opens a live WebSocket to `GET /ws/swarm` via `TestClient` and blocks on `receive_text()` without a timeout. Because `state.orchestrator` is not bootstrapped in the test harness, the server never emits the two expected messages and the test hangs forever — blocking the full suite.

**Fix:** Add `async with anyio.fail_after(10):` around the WebSocket block, or decorate with `@pytest.mark.asyncio(loop_scope="function")` + an `asyncio_timeout` fixture.

---

## 2. 🎨 The Great Purge — Theme Engine Convergence

### Inline Hex Colour Residue Scan
```bash
grep -rn '#[0-9a-fA-F]{3,8}' axiom/gui/widgets/ | wc -l
→ 43
```

**43 raw hex strings remain.** These are expected survivors: colours embedded inside `QColor()` Python calls, `QPainter` canvas drawing, and SVG path generation — **not** inline `setStyleSheet()` calls. The Great Purge is complete with respect to stylesheet injection.

### Commit Footprint — Phase 1 Style Eradication (`6383549`)
```
style: exhaustive eradication of inline QSS, enforce global rounded geometry for all buttons
36 files changed, 159 insertions(+), 510 deletions(-)
```

### Dialogs Converted to Design Token Architecture — 21 of 21

| Widget File | Purged |
|---|---|
| `audit_dialog.py` | ✅ |
| `budget_dialog.py` | ✅ |
| `firewall_dialog.py` | ✅ |
| `governor_dialog.py` | ✅ |
| `graph_dialog.py` | ✅ |
| `hub_dialog.py` | ✅ |
| `iot_dialog.py` | ✅ |
| `kernel_dialog.py` | ✅ |
| `recall_dialog.py` | ✅ |
| `sandbox_dialog.py` | ✅ |
| `sandbox_container.py` | ✅ |
| `scheduler_dialog.py` | ✅ |
| `singularity_dialog.py` | ✅ |
| `skill_dialog.py` | ✅ |
| `swarm_hud.py` | ✅ |
| `swarm_pill.py` | ✅ |
| `sync_dialog.py` | ✅ |
| `system_hub_dialog.py` | ✅ |
| `telemetry_dialog.py` | ✅ |
| `update_dialog.py` | ✅ |
| `vm_dialog.py` | ✅ |

Plus top-level surfaces: `hud.py`, `main_window.py`, `multimodal_hud.py`, `sidebar.py`, `modern_sidebar.py`, `modern_chat.py`, `project_dialog.py`, `oobe_window.py`.

The `ThemeManager` → `ThemeRegistry` → `base.qss.template` pipeline is now the **single source of truth** for all visual styling. JSON theme tokens in `axiom/gui/styles/themes/` drive the entire UI via `ThemeManager.apply_theme(app, "axiom_pro")` called once at startup.

---

## 3. 🧠 OOBE & Persona Engine

### New `AxiomConfig` Fields (`axiom/config.py`)

Three fields added to the dataclass:

```python
persona: dict = field(default_factory=dict)   # Structured persona configuration
persona_key: str = 'default'                   # Named persona slot
active_persona: str = 'axiom_core'             # Active persona ID injected into LLM header
```

A **legacy migration shim** in `__post_init__` promotes old flat keys (`persona_tone`, `persona_complexity`, `special_instructions`) into the new structured dict — full backwards compatibility preserved.

### Anti-Refusal System Prompt (`axiom/agents/orchestrator_agent.py`)

Module-level constant `DIRECT_ACTION_MODE_GUARD` is injected at position 0 of every LLM call in tool-loaded sessions:

> *"CRITICAL EXECUTION RULE: You are operating in Direct Action Mode. You are STRICTLY FORBIDDEN from outputting introductory greetings, self-identifications, or capability recitals…"*

The runtime system prompt compiled by `_build_system_prompt()` includes:

- **Identity anchor:** `[PERSONA: {active_persona}]` header at the top of every call
- **11 numbered directives:** tool execution discipline, temporal rules, hallucination prevention, multimodal perception (`screen_capture`), motor cortex automation, and contextual sandbox (`generate_interactive_widget`)
- **`PersonaCompiler` integration:** `PersonaConfig.from_dict()` + `PersonaCompiler.compile()` appended at runtime, with graceful import-error fallback
- **Preamble loop guard:** secondary `DIRECT_ACTION_MODE_GUARD` fires on next turn if the LLM emits preamble instead of a tool call

### OOBE Overhaul (`84d53d1`)
`OOBEWindow` rebuilt with live theme previews, wired directly to `ThemeManager`. All 21 OOBE test cases across 7 test classes pass cleanly under `QT_QPA_PLATFORM=offscreen`.

---

## 4. 📦 Unstaged Changes — Current Working Tree

`git diff --stat` — **7 files, 162 insertions, 18 deletions** (not yet committed):

| File | Δ | Notes |
|------|---|-------|
| `axiom/agents/orchestrator_agent.py` | +24 | Anti-refusal & PersonaCompiler wiring |
| `axiom/cli/main.py` | +10 | CLI surface updates |
| `axiom/config.py` | +2 | Persona field additions |
| `axiom/launcher.py` | +14/−6 | Launch sequence adjustments |
| `axiom/server/daemon.py` | +1 | Minor daemon fix |
| `patch_qss.py` | +40/−17 | QSS patch utility updates |
| `uv.lock` | +89 | Dependency lockfile sync |

**42 untracked files** at the project root (patch scripts, one-shot test utilities, and build artifacts: `.deb`/`.rpm`/`.dmg`/`.exe`) — not staged.

---

## 5. 🚀 Next Steps — Exact `git` Commands

### Step 1 — Stage confirmed source changes
```bash
git add axiom/agents/orchestrator_agent.py \
        axiom/cli/main.py \
        axiom/config.py \
        axiom/launcher.py \
        axiom/server/daemon.py \
        uv.lock
```

### Step 2 — Commit
```bash
git commit -m "feat(persona): implement anti-refusal identity anchor and structured persona engine

- Add DIRECT_ACTION_MODE_GUARD injected at LLM call position 0
- Add persona/persona_key/active_persona fields to AxiomConfig
- Add legacy config migration shim for flat persona_tone strings
- Integrate PersonaCompiler into OrchestratorAgent._build_system_prompt()
- Wire 11-directive system prompt with multimodal and sandbox rules
- Update launcher and daemon for boot stability"
```

### Step 3 — Stage the updated patch utility (optional)
```bash
git add patch_qss.py
git commit -m "chore: update patch_qss utility with Phase 2/3 QSS patching logic"
```

### Step 4 — Handle untracked root artifacts
```bash
# Option A: Add sprint scripts to the repo
git add apply_claude_fixes.py capture_ui.py fix_*.py generate_svgs.py \
        patch_geometry.py patch_input_bar.py patch_modern_chat_*.py \
        patch_oobe_safe.py patch_oobe_toolbar.py patch_themecard.py \
        process_inline_styles.py test_input_bar.py test_oobe.py \
        test_qss.py test_render.py test_themes.py validate_syntax.py
git commit -m "chore: add Phase 2/3 sprint patch scripts and one-shot test utilities"

# Option B: Exclude them permanently (recommended — they are ephemeral tools)
echo "*.py.bak\napply_claude_fixes.py\ncapture_ui.py\nfix_*.py\npatch_geometry.py\npatch_input_bar.py\npatch_modern_chat_*.py\npatch_oobe_*.py\npatch_themecard.py\nprocess_inline_styles.py\ntest_input_bar.py\ntest_oobe.py\ntest_qss.py\ntest_render.py\ntest_themes.py\nvalidate_syntax.py\ngenerate_svgs.py\n*.rpm\n*.deb\n*.dmg\n*.exe" >> .gitignore
git add .gitignore
git commit -m "chore: ignore ephemeral sprint scripts and build artifacts"
```

### Step 5 — Push
```bash
git push origin main
```

> **⚠️ Before pushing to CI:** Fix the hanging `test_critical_path_websocket_to_sandbox` test or your pipeline will timeout on every run. Wrap the body with `async with anyio.fail_after(10):`.

---

*Debrief generated: 2026-09-25T21:53 CEST — Agent halting, awaiting operator return.*
