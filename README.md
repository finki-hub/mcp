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

### Environment

- `DIRECTUS_URL` - FINKI Hub Directus base URL, read for the study programs (default `https://data.finki-hub.com`)

## Tools

- Filter courses by program, semester or winter/summer term, name or abbreviation, and enrolled-student range in one call; list outputs are compact, paginated (`limit`/`offset`) and flag truncation
- List FINKI study programs for all three cycles from Directus (`list_study_programs`: names, duration, accreditation, language of instruction where officially confirmed, awarded degree title, total ECTS, master's coordinator; with `details`, the description and curriculum rules, and a master's program's layout: mandatory courses and elective slots per semester, and its elective lists)
- Ask who teaches what, when and where in the latest main timetable (`schedule`: by staff member, course or abbreviation, room and/or class, optionally one day; from Directus, with courses, rooms and staff already matched)
- Get a course with what is asked for (`get_course`: by name or abbreviation, plus `curricula` per accreditation, `syllabus` objectives and content, `equivalencies` across accreditations, `enrollments` per year, `teaching` from the latest main timetable the course is taught in, `schedule` in the current one, `programs` for the master's programs a course is in; master's courses included, same-named courses told apart by cycle)
- Search theses by student (name or index), committee member and role, year and title (`find_theses`: bachelor's and master's, newest first); `get_diploma`/`get_master` give one thesis in full
- Ranked statistics in one call (`stats`: `top_courses` by enrollment in an academic year, `theses_per_year` overall or for one mentor, `top_mentors`, `teaching_load` in the current timetable)
- Get a staff member with what is asked for (`get_staff`: profile, plus `teaching`, `schedule`, `theses` counts and recent mentorships, `programs` they coordinate)
- Fuzzy query matching support
- Course lookup by abbreviation (Cyrillic or Latin, e.g. `АПС`, `БнП`/`БП`, `paps`); shared abbreviations return all matching courses as suggestions
- Search FINKI announcements from finki.ukim.mk (`search_announcements`: deadlines for semester enrollment, exam registration, admission rounds, scholarships; Cyrillic or Latin keywords) and read one in full (`get_announcement`)

## License

This project is licensed under the terms of the MIT license.
