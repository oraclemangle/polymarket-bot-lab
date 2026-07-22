# Redaction Manifest

This pack was built from a private trading repo but is intentionally sanitized.

## Excluded

- private keys;
- API tokens;
- wallet addresses;
- exact production hostnames;
- production service names;
- local filesystem paths;
- database files;
- raw trade rows;
- order ids;
- condition ids;
- dashboard credentials;
- `.env` contents;
- personal names and local usernames;
- operational deployment steps that would reveal infrastructure.

## Included

- high-level strategy logic;
- station/source reasoning;
- aggregate evidence only;
- sanitized sizing ladder;
- pseudocode with no private imports or endpoints.

## Notes For Reviewer

The evidence sample is intentionally described as small. The strategy is in
live-probe mode, not full production scale. The most useful review questions
are:

1. Are the station/source gates sensible?
2. Is the sizing ladder overfit to a small sample?
3. Should Tier A be recalibrated, given Tier B has the stronger realised ROI?
4. Should weak cities be skipped rather than held at fallback size?
5. Is the 99c take-profit policy reasonable for weather markets?

