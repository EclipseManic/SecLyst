## What changed

<!-- One or two sentences. What is different for a user after this merges? -->

## Why

<!-- The problem this solves. Link the issue if there is one. -->

## How

<!-- The approach, and anything a reviewer would otherwise have to guess. -->

## Checks

- [ ] `python -m pytest` passes
- [ ] `python -m ruff check .` passes
- [ ] `npm --prefix apps/web test` passes (if the shell changed)
- [ ] Documentation updated in this pull request, if behaviour changed
- [ ] `CHANGELOG.md` entry added under `Unreleased`, if a user can notice it

<!--
If a check could not be run, say which one and why. A known gap is acceptable.
A checked box that was not actually run is not.
-->

## Repository rules

- [ ] No README, requirements file, license, image, or interface was added inside `engines/<id>/`
- [ ] Any new dependency is in the root `requirements.txt` under its engine heading
- [ ] No secrets, tokens, `.env` files, or runtime data are included
