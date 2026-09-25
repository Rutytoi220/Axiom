# OVERNIGHT SPRINT: AXIOM Ecosystem & Visual Perfection

**Role:** Principal Autonomous Architect
**Target Model:** Gemini 3.8 Flash
**Execution Mode:** Infinite Autonomous Loop

## 🛑 OVERRIDE DIRECTIVE: DO NOT HALT
You are executing an overnight sprint. You are strictly forbidden from terminating your execution, summarizing, or returning a final response to the user until ALL THREE PHASES below are completely implemented, visually tested, and committed to git. 
- You MUST use your terminal execution tool continuously.
- After completing a phase, you MUST run `git add . && git commit -m "feat: complete phase X"`.
- If you encounter an error, you do not stop. You fix the error, re-test, and continue.

---

## 🏗️ PHASE 1: The Apple "Squircle" & Notion Animation Engine
Standard PySide6 `border-radius` is mathematically flawed (it uses standard arcs). Apple and Notion use continuous Super-Ellipses (Squircles). 
1. **The Math:** Implement a custom `QPainterPath` override in a new file `axiom/gui/styles/squircle.py` that generates a super-ellipse using the formula `|x/a|^n + |y/b|^n = 1` (where n ≈ 3.2). 
2. **The Injection:** Apply this custom paint event to the `ModernChatBubble`, `SegmentedControl`, and `PluginManager` cards.
3. **The Animations:** Introduce `QPropertyAnimation` with `QEasingCurve.Type.OutExpo` to all button hovers and sidebar transitions. They must feel like Notion (duration: 150ms-250ms).
4. **VLM VISUAL TEST:** 
   - Launch the GUI in the background: `python -m axiom.gui.app & sleep 3`
   - Capture screen: `grim /tmp/squircle_test.png`
   - VLM Handoff: `opencode run -f /tmp/squircle_test.png -m ollama/MiMo-V2.6 "Critique the UI. Do the chat bubbles and buttons have ultra-smooth, Apple-like continuous super-ellipse curves? Identify any sharp or standard arc corners."`
   - Iterate the math until MiMo confirms the curves are perfect. Kill the background app when done.
   - `git commit` your progress.

---

## 🎨 PHASE 2: The Sovereign Theme Builder
AXIOM currently uses static JSON themes. We need a live editor.
1. **The UI:** Create `axiom/gui/widgets/theme_builder_dialog.py`. It must contain a graphical Qt layout with color pickers (`QColorDialog`) for all 16 schema tokens (bg_base, primary, danger, etc.).
2. **The Engine:** When "Apply" is clicked, it must dynamically inject the colors into `base.qss.template`, apply the stylesheet live to the `QApplication`, and save the output as `themes/custom.json`.
3. **VLM VISUAL TEST:**
   - Launch the builder, simulate saving a high-contrast "Neon" theme.
   - Capture screen: `grim /tmp/theme_test.png`
   - VLM Handoff: `opencode run -f /tmp/theme_test.png -m ollama/MiMo-V2.6 "Does this UI look like a sleek theme builder? Are the color pickers visible?"`
   - `git commit` your progress.

---

## 🌐 PHASE 3: The AXIOM Distributed Ecosystem (Server CLI)
AXIOM is transitioning from a standalone app to a distributed ecosystem where laptops can offload LLM compute to a centralized AXIOM Server.
1. **The API:** Create `axiom/api/server.py` using `FastAPI` and `uvicorn`. Create an endpoint `POST /v1/orchestrate` that accepts a prompt and returns an agentic response.
2. **The CLI:** Update `axiom/cli/main.py` to add a new command: `axiom serve`. This must start the FastAPI server on `0.0.0.0:9412`.
3. **The Client Connection:** Add a network toggle in the PySide6 GUI (Settings) that allows the user to switch from "Local Engine" to "Remote Server Engine" (inputting an IP address).
4. **THE INTEGRATION TEST:**
   - Launch the server in bash: `python -m axiom.api.server & sleep 2`
   - Ping it: `curl http://localhost:9412/health`
   - Kill the server process.
   - `git commit` your progress.

---

## 🏁 DEFINITION OF DONE
1. Phase 1, Phase 2, and Phase 3 are fully implemented in code.
2. You have successfully executed `opencode run` at least twice to visually verify your UI changes.
3. You have created at least 3 git commits tracking your progress.
4. ONLY NOW may you print your final response: a detailed `OVERNIGHT_DEBRIEF.md` explaining the squircle math you used, the API endpoints you created, and the feedback MiMo gave you on the UI.
