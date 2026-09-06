# Provenance

`raw-artifact-index.json` binds the private raw evidence by workspace-relative
locator, byte size, and SHA-256. Raw trajectories, service logs, identities, and
cloud lifecycle state are intentionally excluded from this public repository.
The index also records every public sanitization that changes source bytes and
lists the external frozen inputs needed to rebuild or launch the diagnostic
bundles.

`checkpoint-manifest.json` binds the public files exactly as committed. The
manifest excludes itself to avoid a recursive hash. This subtree is marked
`-text` in the repository's `.gitattributes`, so Git does not normalize line
endings and invalidate frozen payload hashes on another platform.

The historical receipt under `cache-resume/trace-analysis/` binds its original
private-tree README and negative-control bytes. Use the transformation entries
in `raw-artifact-index.json`, followed by `checkpoint-manifest.json`, to verify
their sanitized public counterparts.
