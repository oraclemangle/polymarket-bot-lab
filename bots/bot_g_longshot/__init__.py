"""Bot G Prime — 15-min crypto Up/Down late-dislocation paper trader.

Raw "buy cheap tails" cohorts were archived on 2026-04-30 after negative
live-paper evidence. Prime keeps the same recorder-fed execution shell but
only buys 4-8c tails in the final ~30 seconds when the CEX tape confirms the
cheap side.

Paper-only until Prime proves its own cohort edge.

Module layout:
  * config.py    — env-var tunables (entry window, sizes, caps)
  * __main__.py  — scan loop: discover markets → CEX-confirm → place paper orders
  * CLAUDE.md    — operator context / thesis / kill criteria
"""
