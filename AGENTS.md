# Repository Guidelines

## Project Structure & Module Organization

This repository is a German-language running-coach workspace for a sub-17-minute 5 km goal. Core context lives at the root: `athlete_profile.md` records athlete constraints, `coach_instructions.md` defines coaching rules, and `annual_plan_2026_2027.md` provides the long-term progression. Put training blocks and planning prompts in `plans/`, weekly records and reusable diary templates in `logs/`, Garmin exports in `data/raw/garmin/`, and generated summaries in `data/processed/`. The `scripts/` directory is reserved for future local analysis tools.

## Development and Validation Commands

There is currently no build system, package manifest, or automated test suite. Use lightweight repository checks before submitting changes:

```powershell
rg --files
rg "^#" -g "*.md" .
git diff --check
```

The first command reviews tracked workspace content, the second checks Markdown heading structure, and the third detects whitespace errors when the directory is used as a Git checkout. If analysis scripts are added, document their installation and invocation in `scripts/README.md`.

## Writing Style & Naming Conventions

Write Markdown in UTF-8 and preserve the repository's German terminology. Use one `#` title per document, descriptive `##` sections, short paragraphs, and fenced blocks for templates or examples. Keep units explicit (`km`, `min/km`, `W`, `bpm`) and dates unambiguous. Garmin files follow `YYYY-MM-DD_sport_session.ext`, for example `2026-07-08_run_8x400.fit`. Use lowercase snake_case for future scripts and generated CSV files, such as `weekly_summary.py` and `interval_splits.csv`.

## Coaching and Data Validation

Before coaching, read `athlete_profile.md`, `coach_instructions.md`, `annual_plan_2026_2027.md`, `current_status.md`, and recent entries in `logs/training_diary_2026.md`. After receiving an activity, update both persistent status files. Separate measurements, athlete reports, and interpretations; mark missing data rather than estimating it. Do not require or routinely request RPE, feelings, or complaints. Confirm dates, distances, units, planned versus completed sessions, and plan consistency. Never edit raw Garmin exports in place. Future scripts need focused tests with anonymized fixtures; do not use personal exports as test data.

## Commit & Pull Request Guidelines

No Git history is available in the current workspace, so no established commit convention can be inferred. Use concise, imperative messages such as `docs: update July training block` or `data: add weekly summary schema`. Pull requests should explain the coaching or data change, list affected files, note manual validation, and link an issue when applicable. Include screenshots only when rendered Markdown or charts change. Keep athlete health and identifiable training data out of public discussions and fixtures.
