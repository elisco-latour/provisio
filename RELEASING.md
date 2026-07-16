# Releasing provisio

This is the maintainer runbook for publishing to PyPI and deploying the docs.
Publishing uses **PyPI Trusted Publishing (OIDC)** — no API tokens are ever stored.

## Prerequisites

- Push access to `elisco-latour/provisio`.
- A PyPI account with rights to the `provisio` project (the name is claimed on the
  first successful publish).

## One-time setup

### 1. PyPI Trusted Publisher (before the first release)

Register a *pending publisher* so GitHub Actions can publish without a token:

1. Sign in at <https://pypi.org> → **Your account → Publishing → Add a pending publisher**.
2. Fill in exactly:
   - **PyPI Project Name:** `provisio`
   - **Owner:** `elisco-latour`
   - **Repository name:** `provisio`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
3. Save. After the first publish the project exists and the publisher is permanent.

Reference: <https://docs.pypi.org/trusted-publishers/>

### 2. GitHub `pypi` environment (recommended)

**Settings → Environments → New environment → `pypi`.** Optionally add *required
reviewers* so a human approves each publish. `release.yml` targets this environment.

### 3. GitHub Pages (docs)

**Settings → Pages → Source = "GitHub Actions".** (Needs the repo public, or a plan
that permits Pages on private repos.) `docs.yml` deploys on every push to `main`.

## Cutting a release

1. Make sure `main` is green (`ci.yml`) and the tree is clean.
2. Locally sanity-check the build: `uv build` then inspect `dist/`.
3. Bump the version in `pyproject.toml` → `[project] version = "X.Y.Z"` (SemVer).
4. Commit and push: `git commit -am "release: X.Y.Z" && git push`.
5. Create the GitHub Release (this triggers publishing):
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "…highlights…"
   ```
6. The `release` workflow builds the sdist + wheel and publishes to PyPI via OIDC.
7. Verify in a clean environment:
   ```bash
   pip install "provisio[cli]==X.Y.Z"
   python -c "import provisio; print(provisio.__version__)"
   ```
   and check <https://pypi.org/project/provisio/>.

## Versioning

- **SemVer.** Pre-1.0, a minor bump may carry breaking changes — call them out in the
  release notes.
- The version lives only in `pyproject.toml`; `provisio.__version__` reads it back from
  the installed package metadata (single source of truth).

## Security

- **No PyPI tokens** anywhere — OIDC Trusted Publishing only.
- The build is reproducible from the tagged commit; the wheel ships only the package
  (+ `py.typed` + `LICENSE`), never tests, docs, or local files.
- The audit logger redacts known secret values by construction — keep it that way, and
  never add code paths that log raw secrets.
