# Mastercard Official Fallback Report

Checked at: `2026-06-29T07:32:46+00:00`
Dry run: `True`

## Source Access
- Mastercard US Press Releases: accessible `False`, structurally valid `False`, links `0`, post-cutoff `0`, latest ``, recommendation `do_not_activate_collector`

## Candidate Results
- Direct/listing article rows inspected: 5
- Item-level verified rows: 1
- Publication dates verified: 1
- Body verified rows: 4
- True verified recent-item candidates: 0
- Claude eligible rows: 0
- Registry changes: 0

## Controlled Direct Articles
- Agent Pay for Machines: title `Access Denied`, date ``, body `283`, eligible `False`, reason `access_denied`
- Stablecoin settlement: title `Access Denied`, date ``, body `305`, eligible `False`, reason `access_denied`
- TIPS cross-currency pilot: title `Access Denied`, date ``, body `321`, eligible `False`, reason `access_denied`
- Amazon Business cards: title `Access Denied`, date ``, body `304`, eligible `False`, reason `access_denied`
- Original Agent Pay launch: title `Mastercard unveils Agent Pay, pioneering agentic payments technology to power commerce in the age of AI`, date `2025-04-29`, body `6501`, eligible `False`, reason `pre_cutoff`

## Idempotency
- First run canonical rows: 5
- Second run canonical rows: 5
- Same canonical set: True
- Duplicate canonical rows on second run: 0
- Idempotent: True

## Claude Pilot Readiness
- Claude was not run.
- A maximum 3-item Claude pilot is safe only if true verified recent-item candidates are present. Current run did not promote any item to Claude.
