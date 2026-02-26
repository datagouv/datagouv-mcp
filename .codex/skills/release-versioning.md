---
name: release-versioning
description: Use when preparing a release, generating changelog entries, creating tags, or validating versioning workflow through `tag_version.sh` and Conventional Commit history.
prerequisites: git, gh CLI authenticated, clean working tree, permission to push tags/releases
---

# Release and Versioning

<purpose>
Execute safe, repeatable release flow using `tag_version.sh` while avoiding accidental tag/push mistakes.
</purpose>

<context>
- Version is derived from git tags (`setuptools_scm`); no manual version bump in `pyproject.toml`.
- `tag_version.sh` updates `CHANGELOG.md`, commits it, creates annotated tag `v<version>`, pushes, and opens GitHub release.
- Script expects current branch to be `main` or `master` and local branch to be up to date.
- Breaking changes are detected by commit subjects matching `type(scope)!:` or `type!:`.
</context>

<procedure>
1. Confirm prerequisites:
- `gh` installed and authenticated
- clean working tree
- on main branch and synced with origin
2. Run dry run first:
- `./tag_version.sh <version> --dry-run`
3. Inspect generated changelog section ordering and breaking-change grouping.
4. Run real release:
- `./tag_version.sh <version>`
5. Verify outputs:
- commit exists (`chore: release <version> (CHANGELOG)`)
- tag `v<version>` exists
- GitHub release published
6. If script fails, fix root cause and re-run (never partially hand-edit then force-push without approval).
</procedure>

<patterns>
<do>
- Use semantic version string format (`X.Y.Z`).
- Keep commit subjects conventional for clean changelog generation.
- Prefer dry-run for every release.
- Run from repository root.
</do>
<dont>
- Don’t release from feature branches -> script blocks this for safety.
- Don’t run release with dirty working tree -> commit/stash first.
- Don’t edit `CHANGELOG.md` manually right before scripted release unless explicitly required.
- Don’t bypass script safety checks with manual tag+push sequence.
</dont>
</patterns>

<examples>
Example: Dry run
```bash
./tag_version.sh 0.2.18 --dry-run
```

Example: Real release
```bash
./tag_version.sh 0.2.18
```
</examples>

<troubleshooting>
| Symptom | Cause | Fix |
|---|---|---|
| `Error: GitHub CLI is not authenticated` | `gh auth` missing | Run `gh auth login` |
| `You must be on the main branch` | Running from feature branch | Checkout `main`, pull latest |
| `Working copy is not clean` | Uncommitted changes present | Commit/stash and retry |
| `Tag vX.Y.Z already exists` | Version already used | Pick next version |
| macOS awk/asort error | `gawk` not installed | `brew install gawk` |
</troubleshooting>

<references>
- `tag_version.sh`: release script implementation and safeguards.
- `CHANGELOG.md`: generated release history.
- `README.md` (Releases section): contributor-facing release usage.
</references>
