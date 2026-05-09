# Release procedure

This is how a new version of `fscars` ships to PyPI. The release pipeline is
fully automated by `.github/workflows/release.yml` once the one-time setup is
done. There are **no API tokens** stored anywhere — PyPI authenticates the
publish step via OIDC trusted publishers.

---

## One-time PyPI setup (do this exactly once before v0.1.0)

1. **Create a PyPI account** if you do not have one. Use 2FA.
2. Open <https://pypi.org/manage/account/publishing/> and click **"Add a new
   pending publisher"**.
3. Fill the form with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI Project Name | `fscars` |
   | Owner | `VDP89` |
   | Repository name | `fscars` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. **In GitHub**, open <https://github.com/VDP89/fscars/settings/environments>
   and create an environment named **`pypi`**. No secrets needed — OIDC
   handles auth. Optionally enable "Required reviewers" so a release pause
   waits for explicit approval before the upload step actually publishes.

That is the entire setup. From now on, every tag push triggers a release.

---

## Release flow (every version)

```bash
# 1. Bump the version in pyproject.toml.
#    The workflow will fail if the tag does not match this value.
$EDITOR pyproject.toml          # change version = "0.1.0" -> "0.2.0"

# 2. Update CHANGELOG.md with the new entry under [Unreleased] -> [0.2.0].
$EDITOR CHANGELOG.md

# 3. Commit and push.
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): v0.2.0"
git push

# 4. Tag and push the tag. This is what triggers the release workflow.
git tag v0.2.0
git push origin v0.2.0
```

The workflow then:

1. Verifies the tag (`v0.2.0`) matches the pyproject version (`0.2.0`).
2. Builds wheel + sdist with `python -m build`.
3. Validates both distributions with `twine check`.
4. Publishes to PyPI via OIDC.
5. Creates a GitHub Release with auto-generated notes from the diff since
   the previous tag.

If the version does not match, the workflow fails at step 1 — no upload
happens, the tag stays, you fix `pyproject.toml`, push the fix, then
delete and re-push the tag:

```bash
git tag -d v0.2.0
git push --delete origin v0.2.0
# fix and re-tag
```

---

## What the user types after a release

```bash
pip install fscars              # latest stable
pip install "fscars==0.2.0"     # pin
pip install --upgrade fscars
```

---

## Local sanity check before tagging (recommended)

```bash
# Same commands the CI runs, in the same order:
python -m pip install --upgrade pip
pip install build twine
python -m build
python -m twine check dist/*
```

If `twine check dist/*` reports anything other than `PASSED` for both files,
**do not tag**. Fix the metadata first.

---

## Yanking a bad release

If a release ships with a critical bug:

1. **Yank** (do not delete) on PyPI: <https://pypi.org/manage/project/fscars/release/> → click "Yank". A yanked version stays installable for users who pinned it but disappears from the default resolver.
2. Bump the next version, fix the bug, release.

PyPI does not allow re-uploading a version once it has been published — even
after a delete. Tagging `v0.2.0` again after yanking will fail with "version
already exists." Always go forward.
