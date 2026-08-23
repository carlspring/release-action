# GitHub Release Action

[![CI](https://github.com/carlspring/release-action/actions/workflows/ci.yml/badge.svg)](https://github.com/carlspring/release-action/actions/workflows/ci.yml)
[![LICENSE](https://img.shields.io/badge/License-Apache%202.0-brightgreen.svg)](https://github.com/carlspring/release-action/blob/master/LICENSE.Apache-2.0.md)


A GitHub Action that creates a git tag and a GitHub release generated from
the commits since the previous tag — and automatically rolls back the tag
and release if anything goes wrong partway through.

## Features

- 🏷️ Creates and pushes an annotated git tag
- 📝 Builds release notes from `git log <previous-tag>..HEAD`
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
        description: 'Tag to create (e.g. v1.2.3)'
        required: true
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
        uses: actions/checkout@v4
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
| `tag`          | Yes      | —                     | Tag to create, e.g. `v1.2.3`                      |
| `target`       | No       | `main`                | Branch or commit the tag should point to          |
| `draft`        | No       | `false`               | Create the release as a draft                     |
| `prerelease`   | No       | `false`               | Mark the release as a pre-release                 |
| `aliases`      | No       | `''`                  | Space-separated alias tags, e.g. `"v1 v1.0"`      |
| `github-token` | No       | `${{ github.token }}` | Token used to push the tag and manage the release |

## Outputs

| Name          | Description                            |
|---------------|----------------------------------------|
| `tag`         | The tag that was created               |
| `release_id`  | ID of the created GitHub release       |
| `release_url` | HTML URL of the created GitHub release |

## Permissions

The job calling this action needs:

```yaml
permissions:
  contents: write
```

so the default `GITHUB_TOKEN` can push tags and create releases.

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
│   └── release.py                        # Core logic: tag, release, rollback
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

CI (`.github/workflows/ci.yml`) compiles and lints `scripts/release.py` on
every push and pull request against `main`.

## License

[Apache 2.0](LICENSE)
