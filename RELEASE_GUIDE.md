# AXIOM Release Guide

This document outlines the standard procedure for publishing a new version of AXIOM.

## 1. Preparation
Ensure all tests pass and your working tree is clean.
Update the version number in `pyproject.toml` (e.g., to `1.0.0`).
Update `CHANGELOG.md` with the new version and release date.

## 2. Git Tagging
Create an annotated git tag for the release:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

*Note: Pushing the tag will trigger the GitHub Actions release workflow.*

## 3. GitHub Release
1. Navigate to the GitHub repository "Releases" page.
2. Click "Draft a new release".
3. Select the `v1.0.0` tag you just pushed.
4. Set the Release title to `v1.0.0`.
5. Copy the changes from `CHANGELOG.md` into the release description.
6. Publish the release.

## 4. PyPI Publishing (Manual Fallback)
If the GitHub Actions workflow fails, you can publish manually from your local machine.

First, ensure you have the latest build tools:
```bash
pip install --upgrade build twine
```

Build the distribution (wheel and source distribution):
```bash
python -m build
```

Upload to PyPI (you will be prompted for your PyPI API token):
```bash
twine upload dist/*
```
