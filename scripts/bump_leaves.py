#!/usr/bin/env python3
"""Open a pin-bump PR on every leaf, from the core's own release.

WHY THE CORE DOES THIS. Seven leaves pinned five different versions of this
package, one of them six releases behind, and nobody decided that: it is what
happens when keeping current is somebody's memory. The `--check-pin` gate makes
drift impossible to ignore, and this makes it rare, which is the half that
stops the gate becoming noise everyone learns to scroll past.

ONE IMPLEMENTATION, NOT SEVEN WORKFLOWS. A `repository_dispatch` per leaf would
need a receiving workflow in each, so the mechanism would live seven times and
drift the way seven copies of anything drift. This edits each leaf through the
API instead: read its pyproject, rewrite the pin, push a branch, open a PR.

IT OPENS A PR RATHER THAN PUSHING TO MAIN. A leaf's own CI is what decides
whether the new product still works there, and a bump that lands unreviewed on
seven default branches is how one bad release becomes seven broken repositories.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys

LEAVES = [
    "contoso-data-product-databricks-airflow3",
    "contoso-data-product-databricks-jobs",
    "contoso-data-product-fabric-airflow-builtin",
    "contoso-data-product-fabric-airflow3",
    "contoso-data-product-fabric-notebook-pipelines",
    "contoso-data-product-snowflake-airflow3",
    "contoso-data-product-snowflake-tasks",
]
OWNER = "calvinchengx"
PRODUCT = "contoso-data-product"


def api(*args: str, method: str | None = None, body: dict | None = None) -> object:
    command = ["gh", "api"]
    if method:
        command += ["-X", method]
    command += list(args)
    if body is not None:
        command += ["--input", "-"]
    done = subprocess.run(
        command,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)}: {done.stderr.strip()[:400]}")
    return json.loads(done.stdout) if done.stdout.strip() else {}


def one(*args: str, method: str | None = None, body: dict | None = None) -> dict:
    """A single JSON object from the API.

    SPLIT FROM `many` because the return type is the difference that matters:
    subscripting a list with a string key is the bug, and one helper returning
    `dict | list` hides it from the type checker and from the reader.
    """
    got = api(*args, method=method, body=body)
    if not isinstance(got, dict):
        raise RuntimeError(f"expected one object from {args[0]}, got {type(got).__name__}")
    return got


def many(*args: str) -> list:
    """A JSON array from the API."""
    got = api(*args)
    if not isinstance(got, list):
        raise RuntimeError(f"expected a list from {args[0]}, got {type(got).__name__}")
    return got


def repin(text: str, version: str) -> str:
    """Move whichever form of the pin this leaf uses.

    Two forms are in use and both are legitimate: a release wheel URL, and a git
    tag. Rewriting only the one this repository happens to prefer would silently
    skip the others, which is the failure this script exists to prevent.
    """
    wheel = (
        f"https://github.com/{OWNER}/{PRODUCT}/releases/download/"
        f"v{version}/contoso_data_product-{version}-py3-none-any.whl"
    )
    moved = re.sub(
        rf'({PRODUCT} = {{ url = )"[^"]+"',
        lambda m: f'{m.group(1)}"{wheel}"',
        text,
    )
    if moved != text:
        return moved
    return re.sub(
        rf'({PRODUCT} = {{ git = "[^"]+", tag = )"v[0-9][^"]*"',
        lambda m: f'{m.group(1)}"v{version}"',
        text,
    )


def bump(leaf: str, version: str) -> str:
    repo = f"repos/{OWNER}/{leaf}"
    default = one(repo)["default_branch"]
    head = one(f"{repo}/git/ref/heads/{default}")["object"]["sha"]

    current = one(f"{repo}/contents/pyproject.toml?ref={default}")
    text = base64.b64decode(current["content"]).decode()
    moved = repin(text, version)
    if moved == text:
        return f"{leaf}: already on v{version}"

    branch = f"chore/product-v{version}"
    try:
        one(f"{repo}/git/refs", method="POST",
            body={"ref": f"refs/heads/{branch}", "sha": head})
    except RuntimeError as error:
        if "already exists" not in str(error):
            raise

    one(f"{repo}/contents/pyproject.toml", method="PUT", body={
        "message": f"chore: contoso-data-product v{version}",
        "content": base64.b64encode(moved.encode()).decode(),
        "sha": current["sha"],
        "branch": branch,
    })

    # The lockfile and the README block still need regenerating, and only the
    # leaf's own tooling can do that. Saying so in the PR is better than a bump
    # that looks complete and fails its own inventory check.
    existing = many(f"{repo}/pulls?head={OWNER}:{branch}&state=open")
    if existing:
        return f"{leaf}: PR already open ({existing[0]['html_url']})"
    opened = one(f"{repo}/pulls", method="POST", body={
        "title": f"chore: contoso-data-product v{version}",
        "head": branch,
        "base": default,
        "body": (
            f"The core released **v{version}**, and every leaf tracks one version "
            f"with no exception, so that the product cannot mean different things "
            f"in different cells.\n\n"
            f"Opened by the core's release workflow. **It moves the pin only.** "
            f"Run `uv lock` and regenerate the README inventory before merging:\n\n"
            f"```sh\nuv lock\npython -m contoso_product.show --markdown\n```\n\n"
            f"`--check-pin` in this repository's CI is what fails if the bump is "
            f"never taken, and `test_the_readme_inventory_matches_the_pinned_core` "
            f"is what fails if the block is left behind."
        ),
    })
    return f"{leaf}: {opened['html_url']}"


def main() -> int:
    version = (os.environ.get("GITHUB_REF_NAME") or "").lstrip("v")
    if len(sys.argv) > 1:
        version = sys.argv[1].lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"not a version: {version!r}")

    failures = []
    for leaf in LEAVES:
        try:
            print(bump(leaf, version), flush=True)
        except Exception as error:  # noqa: BLE001
            failures.append(f"{leaf}: {error}")
            print(f"{leaf}: FAILED {error}", flush=True)
    if failures:
        # LOUD, because a dispatch that fails quietly is how a leaf falls six
        # releases behind. The gate would catch it eventually; this says so now.
        print(f"\n{len(failures)} leaf/leaves were not bumped:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
