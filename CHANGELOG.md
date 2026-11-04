# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Release notes are grouped into sections (Features, Bug Fixes, Performance,
  Code Refactoring, Documentation, Tests, Build, CI, Styles, Reverts, Chores,
  Other Changes) by their Conventional Commits prefix, with breaking changes
  listed first.
- `group-by` input: list merged pull requests (`pull-request`, default) or
  individual commits (`commit`) in the release notes.
- Unit tests, run in CI.

## [1.0.0] - 2026-08-16
### Added
- Initial release: create a git tag, build a changelog from commits since the
  previous tag, publish a GitHub release, and automatically roll back the tag
  and release if any step fails.
