# FINKI HUB / MCP

Model Context Protocol (MCP) servers for FCSE course management and public APIs.

## Structure

- **`local-mcp/`** - Course management MCP server
- **`public-mcp/`** - Submodule linking to [finki-public-apis](https://gitlab.finki.ukim.mk/wp/finki-public-apis)
- **`data/`** - Course participants and staff JSON files

## Quick Start

### Clone with submodules

```bash
git clone --recurse-submodules https://github.com/finki-hub/mcp.git
cd mcp
```

### Local development

```bash
cd local-mcp
uv sync
uv run python -m app.main
```

### Docker

```bash
docker compose up -d
```

Server runs on `http://localhost:8808`

## Tools

- Get available courses (staff/participants)
- Get course staff/participants information
- Fuzzy query matching support
- Course lookup by abbreviation (Cyrillic or Latin, e.g. `АПС`, `БнП`/`БП`, `paps`); shared abbreviations return all matching courses as suggestions

## License

This project is licensed under the terms of the MIT license.
