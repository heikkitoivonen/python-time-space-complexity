# Python Complexity Skill Distribution

`python-complexity/` contains the authored skill instructions and its independent
release version. English pages in `docs/` remain the reference source. Build
outputs are ignored by Git and are never needed to maintain the documentation.
The repository-maintenance skills under `.agents/skills/` are not distributed.

## Build and Verify

```bash
make skills-build
make skills-check
make skills-package
make skills-eval
```

`skills-build` writes an installable directory to `build/skills/python-complexity/`.
`skills-check` builds in a temporary directory and checks its frontmatter, file
inventory, content hashes, and local Markdown file links. `make check` includes
this validation and package tests. Link checking verifies file destinations,
not Markdown heading slugs or external websites. Documents are copied byte for
byte, so their examples, table notes, and qualifications remain intact.

`skills-package` builds these artifacts in `dist/skills/`:

- `python-complexity-<version>.zip`: the standalone skill, with a single
  `python-complexity/` root directory.
- `python-complexity-marketplace-<version>.zip`: a marketplace root with one
  plugin under `plugins/python-complexity/`, Codex and Claude Code manifests,
  and the identical portable skill under that plugin's `skills/` directory.
- `SHA256SUMS`: SHA-256 digests for both ZIP files.

Each skill contains an MIT license and a manifest recording its release version,
source revision, supported Python versions (from project classifiers), source
document hashes, and packaged file hashes. Builds from local changes carry a
`-dirty` revision suffix. ZIP entries have stable ordering, timestamps, and
permissions; identical inputs and compression tooling produce identical bytes.

`skills-eval` prepares the built skill and displays a manual evaluation packet.
It does not run an agent. See [evaluations.md](evaluations.md) for prompts and a
rubric. Automated tests establish content fidelity and package portability;
they do not establish every source claim or end-to-end behavior in agent clients.

## Release

1. Update `python-complexity/version.txt` with a stable semantic version. Use a
   patch release for reference corrections, a minor release for added coverage
   or compatible capabilities, and a major release for incompatible installation
   or usage changes.
2. Run `make format`, `make check`, and `make skills-package`. Evaluate affected
   prompts when instructions or reference routing change.
3. Review and commit the source changes, then push a tag matching the version,
   for example `python-complexity-v1.0.0`, on that commit.

The [skill workflow](../.github/workflows/skills.yml) runs checks and uploads
preview packages on pull requests, main-branch pushes, and manual dispatch.
Preview artifacts are for testing and may expire according to Actions retention.
On a matching tag push, the workflow also attaches the packages and checksums
to a GitHub Release. GitHub's generated source archives are not skill packages.
As in the site workflow, deterministic tests gate publication and timing tests
run in a separate reporting job. Local `make check` runs both kinds of tests.

Release packaging requires a clean checkout, a tag matching `version.txt`, and
that tag pointing to HEAD. It can be reproduced from the tagged checkout with:

```bash
uv run python scripts/build_skills.py package --release-tag python-complexity-v1.0.0
```

Only the publishing job receives `contents: write`. It uses the workflow's
`GITHUB_TOKEN`; no marketplace credentials are required. Repository Actions must
be allowed to create releases. Publication refuses to overwrite an existing
release. If publication fails, inspect whether a release already exists before
rerunning; publish corrections with a new version rather than replacing assets
people may have pinned.

## Marketplace Distribution

The marketplace archive contains `.agents/plugins/marketplace.json` for Codex
and `.claude-plugin/marketplace.json` for Claude Code. Both resolve plugin paths
relative to the extracted marketplace root, not the manifest's own directory.
Only `python-complexity` is included; no maintenance workflows, hooks, external
services, or runtime dependencies are installed.

The archive can be registered locally using the agent-specific marketplace
documentation linked below. An operator can also commit
its complete extracted contents, including generated references, to a separate
distribution repository and register that Git repository with the agent.
Preserve the leading-dot manifest directories when copying files.

This workflow publishes downloadable GitHub Releases. Public directory
submissions and updates to third-party marketplace repositories are separate
operator actions; it does not imply acceptance or upload to those services.
Git-based installers, including skills.sh-style installers, should target a
complete distribution tree rather than this project's source-only skill folder.
Agent formats and registration steps are documented by
[OpenAI](https://developers.openai.com/plugins/build/plugins) and
[Anthropic](https://code.claude.com/docs/en/plugin-marketplaces).
