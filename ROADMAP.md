# Roadmap

What is planned, in the order it is likely to happen. This is a direction, not a
commitment: items move, and anything here can be dropped if it turns out to cost
more than it is worth.

## Next

### One interface instead of five framed ones

The workbench currently hosts each tool's original interface inside a sandboxed
frame. That was the right call for getting five working tools into one shell
without rewriting them, and it is the largest remaining gap between "a shell
around five tools" and "one platform".

The plan is to move each tool's screens into `apps/web` as native routes on the
shared design system, one tool at a time, starting with IOC. That also removes
the second React application in `engines/ioc/ui`.

### One origin for the browser

When the tool screens are native, the browser talks only to the platform, the
engine ports stop being browser-reachable, and the access-token bootstrap for
frames can be deleted.

## Later

### Packaging

A single installable artifact with a pinned dependency lock, so a fresh machine
does not need a working Node toolchain to run a release build.

### Documentation site

Publish `docs/` as a browsable site with a generated API reference, instead of
GitHub-rendered Markdown.

### Coverage gate

The platform suite runs in CI but has no coverage floor. Once the number is
known and stable, a floor stops silent regression in the control plane.

## Not planned

- **Multi-user or remote deployment.** Seclyst is a single-analyst local
  workbench. Every listener binds loopback and the security model assumes one
  trusted operator. Turning it into a shared service is a different product.
- **A plugin API for third-party engines.** The engine contract is internal and
  may change without notice. It is documented so the repository stays coherent,
  not as a public extension point.
- **Replacing the analysis engines.** The engines are the substance of the
  product. Work goes into the platform around them, not into rewriting them.

## Suggesting a change to this list

Open an issue describing the problem, not only the feature. A roadmap entry that
starts from a real analyst workflow gets picked up faster than one that starts
from a capability list.
