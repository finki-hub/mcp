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
- Filter courses by program, semester or winter/summer term, name or abbreviation, and enrolled-student range in one call; list outputs are compact, paginated (`limit`/`offset`) and flag truncation
- List FINKI study programs for all three cycles (`list_study_programs`: names, duration, accreditation, language of instruction where officially confirmed)
- Get course staff/participants information
- Fuzzy query matching support
- Course lookup by abbreviation (Cyrillic or Latin, e.g. `АПС`, `БнП`/`БП`, `paps`); shared abbreviations return all matching courses as suggestions
- Search FINKI announcements from finki.ukim.mk (`search_announcements`: deadlines for semester enrollment, exam registration, admission rounds, scholarships; Cyrillic or Latin keywords) and read one in full (`get_announcement`)

## License

This project is licensed under the terms of the MIT license.
