# Changelog

## v0.1.0 — initial release

- `CRAFTSMANSHIP.md` / `catalog.yaml`: 15 Tidy First tidyings (Beck), 9
  Fowler smell-and-fix pairs, 6 new-code principles (Martin, Beck-XP), the
  legacy-code characterization-test workflow (Feathers), and Sandi Metz's
  rules as an optional stricter reference.
- `scripts/check_tidy_ratchet.sh`: commit-message ratchet, recognizes
  `tidy(<type>):`, `test(characterize):`, and `Tidy-Exempt:`.
- `scripts/report_tidy_history.sh`: exemption-ratio and cited-sources report.
- `skills/tidy-first/SKILL.md`: thin Claude Code wrapper.
- `templates/`: CLAUDE.md section, pre-commit hook entry, CI job fragment.
- `bootstrap.sh`: install/update script for consuming repos.
