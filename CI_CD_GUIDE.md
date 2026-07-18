# AXIOM CI/CD Guide & PyPI Trusted Publishing Setup

This document outlines how AXIOM's CI/CD pipeline operates and provides instructions for maintainers on setting up PyPI Trusted Publishing.

## Overview

We have fully automated our testing and release pipeline using GitHub Actions:

1. **Continuous Integration (CI):** On every push and Pull Request to `main`, `.github/workflows/ci.yml` runs our regression test suite across multiple OS platforms (Ubuntu, macOS, Windows) and Python versions (3.10 to 3.13).
2. **Continuous Deployment (CD):** When a semantic version tag (e.g., `v2.0.0`) is pushed to the repository, `.github/workflows/publish.yml` is triggered. This workflow builds the package distributions (`.whl` and `.tar.gz`), publishes them to PyPI using Trusted Publishing (OIDC), and generates a GitHub Release with auto-generated release notes.

## Setting Up PyPI Trusted Publishing

To allow GitHub Actions to securely publish the `local-axiom-agent` package without needing to manage long-lived API tokens, you must configure Trusted Publishing (OpenID Connect) on PyPI.

> **Note:** Only PyPI project owners can configure this setting.

### Prerequisites
1. You must have an account on PyPI (https://pypi.org/).
2. You must have ownership rights over the `local-axiom-agent` project on PyPI (or the rights to register it if it hasn't been published yet).

### Step-by-Step Instructions

1. **Log into PyPI:** Go to [pypi.org](https://pypi.org/) and log in.
2. **Navigate to Publishing Settings:**
   - If the project already exists: Go to **Your Projects** -> click `local-axiom-agent` -> **Manage** -> **Publishing**.
   - If this is a new project: Go to **Your Account** -> **Publishing** -> Add a new pending publisher.
3. **Add a new GitHub Publisher:**
   Fill in the form with the following details exactly:
   - **Owner:** (Your GitHub organization or username where the repository is hosted)
   - **Repository name:** (The name of the AXIOM repository)
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. **Save and Verify:** Click **Add**. PyPI will now trust the GitHub Actions workflow named `publish.yml` running in the `pypi` environment from your repository.

### Releasing a New Version

Once Trusted Publishing is configured, releasing a new version is entirely automated via Git tags:

1. Ensure your local `main` branch is up to date and all tests pass.
2. Update the version number in `pyproject.toml`.
3. Commit the version bump:
   ```bash
   git commit -am "chore: bump version to 2.0.0"
   git push origin main
   ```
4. Create and push a semantic version tag:
   ```bash
   git tag v2.0.0
   git push origin v2.0.0
   ```
5. GitHub Actions will intercept the tag push, build the artifacts, authenticate securely with PyPI via OIDC, and publish the new release!
