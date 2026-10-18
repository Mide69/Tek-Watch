# Evidence hardening and release checks

This change is source implementation, not evidence of production deployment,
regulatory approval, competitive superiority or completed customer benchmarks.

## Assessment scope

The bundled UK pack contains 24 defined controls, of which 23 are eligible.
LAM-01 remains quarantined pending runtime-rule review. The pack has a version,
content hash, source references and an explicit engineering-review status.
International packs are not implemented or independently reviewed.

Assessments retain observation timestamps, field provenance, rule versions and
engine hashes. Missing, future or stale observations cannot produce a passing
verdict. A remediation requires an observation newer than the original pending
recheck request. Re-evaluating an old observation does not verify a fix.
Configuration alerts prompt breach triage; they do not start a legal clock.

## Evidence integrity

Append and head advancement use a DynamoDB transaction. Full verification checks
sequence continuity and the stored head; read failures and incomplete exports
fail closed. ZIP exports contain complete canonical bodies, a manifest, timestamp
responses and an offline verifier. Signature verification requires trusted TSA
certificates and OpenSSL. Retain a head externally to detect a complete rewrite;
trust the verifier independently of an archive supplied by an untrusted party.

Existing orphan entries are not automatically changed. An operator may preview:

```bash
python scripts/recover-evidence-head.py CUSTOMER_ID
```

After checking the complete valid chain and the proposed head, `--apply` performs
a conditional head repair. Back up the table and test recovery in staging first.
No recovery has been executed as part of this code review.

## Release validation and remaining capacity limits

The agent uses a shared explicit AWS operation policy instead of ReadOnlyAccess.
Payload reads are denied. Re-deploy customer onboarding stacks to apply the new
policy; existing installations are not changed by this commit. Test every enabled
collector against a staging account and review IAM before rollout. The self-hosted
agent receives its API key through its existing configuration and does not need
task-role access to the central application secret.

Customer scans paginate and recorder failures are isolated by customer. Numeric
inventory history is queried once per assessment. These improvements are not a
load-test result or a completed queue-based assessment architecture.

Evidence entries above 350,000 canonical bytes are rejected before writing.
Large inventories therefore require bounded or externally stored observation
payloads before expansion. Full-chain exports are built in memory; benchmark
large customer histories before promising unbounded retention or export scale.

Before production rollout, run Terraform validation/plan, staging collector and
transaction tests, a real trusted TSA signature verification, and representative
capacity tests. None of those live-cloud checks is implied by unit-test success.
