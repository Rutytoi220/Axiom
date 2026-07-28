# AXIOM Release Guide

This document outlines the standard procedure for publishing a new version of AXIOM (v5.3.0+).

## 1. Preparation
1. Ensure all tests pass: `pytest tests/`.
2. Verify all subsystems (AxiomFS, HUD, Sandbox) are operational.
3. Update the version number in `pyproject.toml` (e.g., to `5.3.0`).
4. Update `CHANGELOG.md` with the new version and release date.

## 2. Security Audit
Perform a final check of the sandbox isolation:
```bash
python3 -m axiom.security.verifier --audit-all
```

## 3. Git Tagging
Create an annotated git tag for the release:

```bash
git tag -a v5.3.0 -m "AXIOM v5.3.0: Sovereign Kernel Release"
git push origin v5.3.0
```

*Note: Pushing the tag will trigger the GitHub Actions release workflow, which builds the `.rpm`, `.deb`, `.AppImage`, and `.exe` artifacts.*

## 4. GitHub Release
1. Navigate to the GitHub repository "Releases" page.
2. Click "Draft a new release".
3. Select the `v5.3.0` tag you just pushed.
4. Set the Release title to `AXIOM v5.3.0: Sovereign Kernel Release`.
5. Copy the changes from `CHANGELOG.md` into the release description.
6. Verify that the CI-built artifacts are automatically attached to the release.
7. Publish the release.

## 5. OTA Broadcast
Once the release is public, the Kernel will automatically detect it via the `axiom.security.release_verifier`. To force a broadcast to all active nodes in the Swarm:

```bash
axiom-kernel broadcast-update --version 5.3.0
```
