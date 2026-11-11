# GitHub Release Action

[![CI](https://github.com/carlspring/release-action/actions/workflows/ci.yml/badge.svg)](https://github.com/carlspring/release-action/actions/workflows/ci.yml)
[![LICENSE](https://img.shields.io/badge/License-Apache%202.0-brightgreen.svg)](https://github.com/carlspring/release-action/blob/master/LICENSE.Apache-2.0.md)


A GitHub Action that creates a git tag and a GitHub release generated from
the commits since the previous tag — and automatically rolls back the tag
and release if anything goes wrong partway through.

## Features

- 🏷️ Creates and pushes an annotated git tag
- 🔢 Computes the next version from the latest tag when no tag is given
- 📝 Builds release notes from the commits since the previous tag, grouped into
  Features, Bug Fixes, Documentation, CI, … by their
  [Conventional Commits](https://www.conventionalcommits.org) prefix
- 🔀 Lists either the merged pull requests or the individual commits
- 🚀 Publishes a GitHub release for that tag
- 🔗 Optionally creates alias tags (e.g. `v1`, `v1.0`) pointing to the same commit
- ↩️ Rolls back the tag, alias tags, and release on any failure
- 🖥️ Implemented in plain Python — no extra runtime beyond what `setup-python` provides

## Usage

```yaml
name: Create Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to create (e.g. v1.2.3); leave empty to compute the next version'
        required: false
        default: ''
        type: string
      target:
        description: 'Branch or commit to tag'
        required: false
        default: 'main'
        type: string
      prerelease:
        description: 'Mark as a pre-release'
        required: false
        default: false
        type: boolean
      aliases:
        description: 'Space-separated alias tags (e.g. "v1 v1.0")'
        required: false
        default: ''
        type: string

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v7
        with:
          fetch-depth: 0   # full history + tags are needed to build the changelog
          ref: ${{ inputs.target }}

      - name: Tag and release
        id: release
        uses: carlspring/release-action@v1
        with:
          tag: ${{ inputs.tag }}
          target: ${{ inputs.target }}
          prerelease: ${{ inputs.prerelease }}
          aliases: ${{ inputs.aliases }}   # e.g. "v1 v1.0"

      - name: Show result
        run: echo "Release created at ${{ steps.release.outputs.release_url }}"
```

A ready-to-run copy of this workflow is in
[`.github/workflows/example-release.yml`](.github/workflows/example-release.yml).
Trigger it from the **Actions** tab → **Create Release** → **Run workflow**.

> **Note:** replace `your-org/tag-and-release-action@v1` with `uses: ./` if
> you're calling the action from within this same repository rather than
> as a published dependency.

## Inputs

| Name           | Required | Default               | Description                                       |
|----------------|----------|-----------------------|---------------------------------------------------|
| `tag`          | No       | `''`                  | Tag to create, e.g. `v1.2.3`; [computed](#computed-versions) if empty |
| `target`       | No       | `main`                | Branch or commit the tag should point to          |
| `draft`        | No       | `false`               | Create the release as a draft                     |
| `prerelease`   | No       | `false`               | Mark the release as a pre-release                 |
| `aliases`      | No       | `''`                  | Space-separated alias tags, e.g. `"v1 v1.0"`      |
| `group-by`     | No       | `pull-request`        | List `pull-request`s or `commit`s in the notes    |
| `github-token` | No       | `${{ github.token }}` | Token used to push the tag and manage the release |

## Outputs

| Name          | Description                            |
|---------------|----------------------------------------|
| `tag`         | The tag that was created (given or computed) |
| `release_id`  | ID of the created GitHub release       |
| `release_url` | HTML URL of the created GitHub release |

## Permissions

The job calling this action needs:

```yaml
permissions:
  contents: write
```

so the default `GITHUB_TOKEN` can push tags and create releases.

## Computed versions

If `tag` is left empty, the action computes the next version from the latest
version tag reachable from `target`:

| Latest tag          | Next version        | Rule                                  |
|---------------------|---------------------|---------------------------------------|
| `1.2.3`             | `1.2.4`             | Increment the patch number            |
| `v1.2.3`            | `v1.2.4`            | A `v` prefix is kept                  |
| `1.2.3-alpha-1`     | `1.2.3-alpha-2`     | Increment the pre-release number      |
| `1.2.3-beta-1`      | `1.2.3-beta-2`      | Increment the pre-release number      |
| `1.2.3-milestone-1` | `1.2.3-milestone-2` | Increment the pre-release number      |
| `1.2.3-rc-1`        | `1.2.3-rc-2`        | Increment the pre-release number      |
| `1.2.3-beta`        | *(fails)*           | Doesn't follow the convention         |
| *(none)*            | `1.0.0`             | No version tags yet                   |

Pre-releases must follow the convention `-alpha-N`, `-beta-N`, `-milestone-N`
or `-rc-N`, and rank in that order, below their final release:

```
1.2.3-alpha-1 < 1.2.3-beta-1 < 1.2.3-milestone-1 < 1.2.3-rc-1 < 1.2.3
```

If the latest version tag has any other suffix (e.g. `1.2.3-beta`, `1.2.3-rc1`,
`1.2.3-rc.1`, `1.2.3-RC-1`), the action doesn't guess: it fails before creating
anything and asks for the `tag` to be set explicitly. Such a tag ranks above the
pre-releases of its version, so it can't be skipped silently, but it's harmless
once a newer version exists.

Only tags of the form `[v]MAJOR.MINOR.PATCH[-SUFFIX]` count; alias tags such as
`v1` or `v1.0` are ignored. Of those, the highest version wins, and a final
release ranks above its pre-releases (so after `1.0.0-rc-2` and `1.0.0` the next
version is `1.0.1`). Tags with and without the `v` prefix are compared by their
numbers, and the next version keeps the style of the latest one (after `1.1.0`
and `v1.2.0` it is `v1.2.1`). The computed tag is available as the `tag` output.

For a minor or major release, or to start a pre-release series, pass the `tag`
explicitly.

## Release notes

The release notes list the changes since the previous tag, grouped into
sections by their [Conventional Commits](https://www.conventionalcommits.org)
prefix (`type(scope): subject`):

| Prefix     | Section          |
|------------|------------------|
| `feat`     | Features         |
| `fix`      | Bug Fixes        |
| `perf`     | Performance      |
| `refactor` | Code Refactoring |
| `docs`     | Documentation    |
| `test`     | Tests            |
| `build`    | Build            |
| `ci`       | CI               |
| `style`    | Styles           |
| `revert`   | Reverts          |
| `chore`    | Chores           |

Anything without one of these prefixes goes under **Other Changes**. Breaking
changes (`feat!: …` or a `BREAKING CHANGE:` footer) are listed once, in a
**⚠ Breaking Changes** section at the top. Empty sections are left out.

The `group-by` input chooses what each line represents:

- `pull-request` (default): the merged pull requests that contain the commits
  since the previous tag, categorised by their **title**:

  ```markdown
  ### Features

  - **tracing**: wire OpenTelemetry export ([#42](https://github.com/org/repo/pull/42)) (@carlspring)
  ```

  If no pull requests are found, or there is no previous tag, the commits are
  listed instead.

- `commit`: the individual (non-merge) commits, categorised by their message:

  ```markdown
  ### Bug Fixes

  - **publishing**: declare explicit dependency versions ([6840708a](https://github.com/org/repo/commit/6840708a91b2...))
  ```

## How rollback works

The action tracks what it has created as it goes:

1. Creates and pushes the git tag.
2. Creates the GitHub release from that tag.
3. Creates any alias tags (e.g. `v1`, `v1.0`).

If step 2 or 3 (or anything else after the tag is pushed) raises an error, the
action:

- Deletes the GitHub release, if one was created.
- Deletes the git tag, both on the remote and locally.
- Deletes any alias tags that were already created, both on the remote and locally.

This keeps a failed run from leaving a dangling tag or an incomplete release
behind. Rollback is best-effort: failures encountered while cleaning up are
logged rather than raised, so the original error is what surfaces in the
workflow.

## Project structure

```
.
├── action.yml                            # Action metadata (inputs/outputs, runs config)
├── requirements.txt                      # Python dependencies
├── scripts/
│   ├── release.py                        # Core logic: tag, release, rollback
│   ├── next_version.py                   # Computes the next version from the tags
│   └── release_notes.py                  # Groups commits/PRs into release-note sections
├── tests/                                # Unit tests (unittest)
└── .github/workflows/
    ├── ci.yml                            # Lints/validates the action's source
    └── release.yml                       # Example consumer workflow
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the script directly against a real repo/token for local testing
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=your-org/your-repo
python scripts/release.py --tag v0.0.1-test --target main
```

Run the tests (standard-library `unittest`, no extra dependencies):

```bash
python -m unittest discover -s tests -v
```

CI (`.github/workflows/ci.yml`) compiles, lints and tests the scripts on every
push and pull request against `main`.

## License

[Apache 2.0](LICENSE)
