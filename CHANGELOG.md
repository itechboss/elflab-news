# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- CLAUDE.md with project context and rules

### Changed

- Remove full name from UI, replace with "elflab"
- Add YouTube collector: TechWorld with Nana, NetworkChuck, Fireship, DevOps Toolkit (RSS, no API key)

## [2026-11-04] - Initial Release

### Added

- Python app: aiohttp server + APScheduler (hourly collect + digest)
- GitHub Trending collector (Search API, velocity scoring)
- Hacker News collector (top stories, score + comments scoring)
- RSS collectors: CNCF blog, Kubernetes blog, Lobste.rs, TheNewStack, InfoQ
- SQLite storage with deduplication (UNIQUE source + source_id)
- Keyword-based categorization: ai-ml, security, infra, tools, trending-repo
- Static HTML digest generation via Jinja2
- RSS feed output at /feed.xml (RSS 2.0, top 30 items)
- Dark theme, responsive layout, category filters (JS)
- About section in footer (name, role, GitHub, RSS link)
- K3s Deployment (ConfigMap pattern, no Docker build)
- PVC for SQLite + generated HTML
- Ingress for elflab.eu with TLS (cert-manager)
- ArgoCD Application manifest
- assemble.sh for ConfigMap generation
