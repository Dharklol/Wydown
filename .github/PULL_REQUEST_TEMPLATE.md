## Change summary
Explain the problem, change, and linked Wydown issue/RFC.

## Classification
- [ ] Documentation / design only
- [ ] Data contract or schema
- [ ] Accounting / risk / execution
- [ ] Strategy research
- [ ] Dependencies / build / security

## Evidence
- [ ] Tests and negative cases added or updated (or documented as not applicable)
- [ ] Formatting, static checks and relevant CI gates pass
- [ ] Reproducible inputs, fixtures and dependency changes described
- [ ] Impact on source-event ordering, arithmetic, and replay checked
- [ ] SQLite migration/backup/rollback assessed (or not applicable)
- [ ] Research, paper, live segregation verified
- [ ] No secrets, credentials, private account data or live order permission added
- [ ] Risk-policy, broker, instrument and options-collateral impacts documented
- [ ] No unreviewed live deployment or automatic model promotion

## Operational impact
List affected schema versions, release hashes, migrations, instrument permissions,
model revisions, and recovery plan. If not applicable, explicitly write N/A.

## Validation performed
Commands, environments, failure injection, and any unverified assumptions.

## Merge policy
PR checks alone do not prevent direct pushes: enforce `main` rulesets/branch
protection separately where the repository's GitHub plan supports it.
