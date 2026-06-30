# Mastercard Official Fallback Report

Checked at: `2026-06-29T07:37:26+00:00`
Dry run: `True`

## Source Access
- Mastercard US Press Releases: accessible `False`, structurally valid `False`, links `0`, post-cutoff `0`, latest ``, recommendation `do_not_activate_collector`
- Mastercard Legacy Newsroom Press: accessible `True`, structurally valid `True`, links `100`, post-cutoff `0`, latest `2025-06-09`, recommendation `historical_resolution_only`
- Mastercard Legacy Newsroom Landing: accessible `True`, structurally valid `True`, links `4`, post-cutoff `0`, latest `2025-06-09`, recommendation `historical_resolution_only`

## Candidate Results
- Direct/listing article rows inspected: 104
- Item-level verified rows: 97
- Publication dates verified: 97
- Body verified rows: 101
- True verified recent-item candidates: 0
- Claude eligible rows: 0
- Registry changes: 0

## Controlled Direct Articles
- Agent Pay for Machines: title `Access Denied`, date ``, body `283`, eligible `False`, reason `access_denied`
- Stablecoin settlement: title `Access Denied`, date ``, body `305`, eligible `False`, reason `access_denied`
- TIPS cross-currency pilot: title `Access Denied`, date ``, body `321`, eligible `False`, reason `access_denied`
- Amazon Business cards: title `Access Denied`, date ``, body `304`, eligible `False`, reason `access_denied`
- Original Agent Pay launch: title ``, date ``, body `0`, eligible `False`, reason ``

## Idempotency
- First run canonical rows: 104
- Second run canonical rows: 104
- Same canonical set: True
- Duplicate canonical rows on second run: 0
- Idempotent: True

## Claude Pilot Readiness
- Claude was not run.
- A maximum 3-item Claude pilot is safe only if true verified recent-item candidates are present. Current run did not promote any item to Claude.
