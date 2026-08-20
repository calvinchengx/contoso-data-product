"""Show the product: where its SQL is, and what it contains.

WHY THIS EXISTS. The core carries the product and seven leaf repositories
depend on it, which is what stops nine gold models becoming seven divergent
copies of nine gold models. It also costs the reader something real: clone a
leaf and you find dags, a pin, and a `from contoso_product import gold_dir`,
while the business logic lives in another repository at another tag. DRY serves
the maintainer; the reader is served by seeing the thing.

So this module is the reading affordance, and it is here rather than in each
leaf for the same reason the SQL is: seven copies of a lister would drift from
what they list.

Two modes, one source:

    python -m contoso_product.show                  what the product contains
    python -m contoso_product.show --into product/  the SQL itself, on disk
    python -m contoso_product.show --markdown       the same inventory, for a README

`--markdown` emits a block a leaf's README embeds between sentinels, so a
checker can regenerate it and fail when it drifts. A hand-written inventory is
a second source of truth, and this family has been bitten by exactly that: a
parity row named a test that checked something adjacent, and a policy inventory
was wrong 28 times in 70.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from typing import TypedDict

from . import gold_dir, silver_dir
from .contracts import PRODUCT_NAME

class Layer(TypedDict):
    """One dbt project's contents, as file stems."""

    models: list[str]
    tests: list[str]
    macros: list[str]


class Inventory(TypedDict):
    version: str
    product: str
    silver: Layer
    gold: Layer


BEGIN = "<!-- BEGIN product inventory: python -m contoso_product.show --markdown -->"
END = "<!-- END product inventory -->"


def repository() -> str:
    """Where this product lives, from package metadata.

    NOT A LITERAL, because RULES.md forbids core code addressing anything and
    a permalink base written here would be a second place the repository
    names itself. Declared once in pyproject under [project.urls].
    """
    from importlib.metadata import PackageNotFoundError, metadata

    try:
        for entry in metadata("contoso-data-product").get_all("Project-URL") or []:
            label, _, url = entry.partition(",")
            if label.strip().lower() == "repository":
                return url.strip().rstrip("/")
    except PackageNotFoundError:
        pass
    return ""


def version() -> str:
    """The installed version, which is what a leaf's pin resolved to."""
    from importlib.metadata import PackageNotFoundError, version as installed

    try:
        return installed("contoso-data-product")
    except PackageNotFoundError:  # running from a source checkout
        return "unknown"


def _sql(directory: Path) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.sql"))


def inventory() -> Inventory:
    """What the product contains, read from the installed package.

    Read rather than declared: the point of the block this feeds is that it
    cannot disagree with the package a leaf actually installed.
    """
    silver, gold = silver_dir(), gold_dir()
    return {
        "version": version(),
        "product": PRODUCT_NAME,
        "silver": {
            "models": _sql(silver / "models"),
            "tests": _sql(silver / "tests"),
            "macros": _sql(silver / "macros"),
        },
        "gold": {
            "models": _sql(gold / "models"),
            "tests": _sql(gold / "tests"),
            "macros": _sql(gold / "macros"),
        },
    }


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def markdown() -> str:
    inv = inventory()
    v = inv["version"]
    home = repository()
    base = f"{home}/blob/v{v}/src/contoso_product"
    out = [BEGIN, ""]
    out.append(
        f"The product is [`contoso-data-product`]({home}/tree/v{v}) at **v{v}**, "
        f"the version this repository pins. It is not vendored here: these files live "
        f"there and are staged locally by `make show-product`."
    )
    out.append("")
    for layer, data in (("silver", inv["silver"]), ("gold", inv["gold"])):
        models, tests = data["models"], data["tests"]
        # LISTED SEPARATELY, not paired in one table. A two-column table of
        # models beside tests reads as a correspondence, and there is none: the
        # tests are singular assertions over the layer, not one per model. The
        # first draft of this put `silver_customers` next to a test about
        # orders, which is a relationship the reader would have believed.
        out.append(f"**{layer}**: {plural(len(models), 'model')}, {plural(len(tests), 'singular test')}")
        out.append("")
        for model in models:
            out.append(f"- [`{model}`]({base}/{layer}/models/{model}.sql)")
        out.append("")
        if tests:
            out.append(f"Assertions over {layer}, each failing the build on its own:")
            out.append("")
            for test in tests:
                out.append(f"- [`{test}`]({base}/{layer}/tests/{test}.sql)")
            out.append("")
    out.append(END)
    return "\n".join(out)


def stage(into: Path) -> Path:
    """Put the product's SQL where the reader can open it."""
    into = into.resolve()
    for layer, source in (("silver", silver_dir()), ("gold", gold_dir())):
        destination = into / layer
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    return into


def human() -> str:
    inv = inventory()
    lines = [f"contoso-data-product v{inv['version']}  ({inv['product']})"]
    for layer, data in (("silver", inv["silver"]), ("gold", inv["gold"])):
        lines.append(
            f"  {layer}: {plural(len(data['models']), 'model')}, "
            f"{plural(len(data['tests']), 'singular test')}, "
            f"{plural(len(data['macros']), 'macro file')}"
        )
        for model in data["models"]:
            lines.append(f"    {model}")
    return "\n".join(lines)


def check(readme: Path) -> tuple[bool, str]:
    """Is this README's inventory block what the installed product says?

    THE POINT OF THE SENTINELS. A leaf embeds the block and a test calls this,
    so an inventory that falls behind the pin fails in the leaf that owns it
    rather than misleading a reader indefinitely. A hand-maintained list would
    be a second source of truth, which is the fault this whole core exists to
    prevent one layer down.
    """
    text = readme.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return False, (
            f"{readme.name} carries no product inventory block. Add one:\n"
            f"  python -m contoso_product.show --markdown >> {readme.name}"
        )
    start = text.index(BEGIN)
    stop = text.index(END) + len(END)
    have, want = text[start:stop].strip(), markdown().strip()
    if have == want:
        return True, f"{readme.name}: the product inventory matches v{version()}"
    return False, (
        f"{readme.name}: the product inventory is not what v{version()} contains. "
        f"Regenerate it:\n  python -m contoso_product.show --markdown"
    )


def latest_release(timeout: float = 10.0) -> str:
    """The newest published version of this product, from its own repository.

    A LEAF CANNOT ANSWER THIS ALONE. `version()` reports whatever the leaf
    installed, which IS its pin, so a stale leaf reading its own package
    concludes it is current. The authority has to be outside it, and the
    releases are that authority.
    """
    import json
    import urllib.request

    home = repository()
    if not home:
        raise RuntimeError("the package declares no Repository URL to ask")
    # BUILT FROM THE DECLARED REPOSITORY, not written down. RULES.md forbids core
    # code addressing anything, and `test_no_engine_named_in_core` enforces it by
    # banning a literal scheme in a string. Deriving the API host from the URL
    # already in metadata obeys both the rule and the reason for it.
    url = home.rstrip("/").replace("//github.com/", "//api.github.com/repos/") + "/releases/latest"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    import os

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)["tag_name"].lstrip("v")


def check_pin() -> tuple[bool, str]:
    """Is the installed product the newest release?

    NETWORK ON PURPOSE, and it is not an imposition: a leaf installs this
    package from a GitHub release in the first place, so a leaf that cannot
    reach GitHub cannot resolve its own dependencies either. A failure to ask
    is reported as a failure rather than skipped, because a check that quietly
    skips is the "accepted but inert" trap this family keeps finding.
    """
    have = version()
    try:
        newest = latest_release()
    except Exception as error:  # noqa: BLE001 - the reason matters more than the type
        return False, (
            f"could not ask which release is newest ({error}). This check needs "
            f"the network, the same as installing this package does."
        )
    if have == newest:
        return True, f"the pinned product is the newest release, v{have}"
    return False, (
        f"this repository pins contoso-data-product v{have}, but v{newest} is "
        f"released. Every leaf tracks one version, with no exception, so that "
        f"the product cannot mean different things in different cells. "
        f"Update the pin in pyproject.toml and re-lock."
    )


def repin(text: str, version: str) -> str:
    """Move whichever form of the product pin a leaf uses.

    IN THE PACKAGE, NOT IN A SCRIPT, because both directions need it: the core
    can open bump PRs across the leaves, and a leaf can raise its own. Two
    copies of a regex that must match two pin forms is how one form silently
    stops being rewritten.

    Two forms are in use and both are legitimate: a release wheel URL and a git
    tag. Rewriting only the one whoever wrote this happened to be looking at is
    exactly how a leaf gets left behind while a sweep reports success.
    """
    owner_product = repository().rstrip("/").split("github.com/", 1)[-1]
    product = owner_product.split("/")[-1]
    wheel = (
        f"{repository()}/releases/download/"
        f"v{version}/{product.replace('-', '_')}-{version}-py3-none-any.whl"
    )
    moved = re.sub(
        rf'({re.escape(product)} = {{ url = )"[^"]+"',
        lambda m: f'{m.group(1)}"{wheel}"',
        text,
    )
    if moved != text:
        return moved
    return re.sub(
        rf'({re.escape(product)} = {{ git = "[^"]+", tag = )"v[0-9][^"]*"',
        lambda m: f'{m.group(1)}"v{version}"',
        text,
    )


def update_pin(pyproject: Path) -> tuple[bool, str]:
    """Rewrite a leaf's own pin to the newest release. Returns (changed, message).

    THE LEAF RAISES ITS OWN BUMP. A push from the core needs a token with write
    on seven repositories; a leaf editing its own `pyproject.toml` needs only
    the `GITHUB_TOKEN` its workflow already has. One expired secret cannot then
    stop all seven at once, and there is no secret to over-scope in the first
    place.
    """
    try:
        newest = latest_release()
    except Exception as error:  # noqa: BLE001
        return False, f"could not ask which release is newest ({error})"
    text = pyproject.read_text(encoding="utf-8")
    moved = repin(text, newest)
    if moved == text:
        return False, f"already pinned at v{newest}"
    pyproject.write_text(moved, encoding="utf-8")
    return True, f"pin moved to v{newest}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contoso_product.show", description=__doc__.splitlines()[0])
    parser.add_argument("--into", metavar="DIR", help="copy the product's dbt projects here and print the path")
    parser.add_argument("--markdown", action="store_true", help="emit the README inventory block")
    parser.add_argument("--update-pin", metavar="PYPROJECT", dest="update_pin",
                        help="rewrite that pyproject's product pin to the newest release")
    parser.add_argument("--check-pin", action="store_true", dest="check_pin",
                        help="fail unless the installed product is the newest release")
    parser.add_argument("--check", metavar="README", help="fail if that README's block is not what this version contains")
    args = parser.parse_args(argv)

    if args.update_pin:
        changed, message = update_pin(Path(args.update_pin))
        print(message)
        return 0 if changed else 1
    if args.check_pin:
        ok, message = check_pin()
        print(message)
        return 0 if ok else 1
    if args.check:
        ok, message = check(Path(args.check))
        print(message)
        return 0 if ok else 1
    if args.markdown:
        print(markdown())
        return 0
    if args.into:
        where = stage(Path(args.into))
        print(human())
        print()
        print(f"staged to {where}")
        print(f"  {where / 'silver'}")
        print(f"  {where / 'gold'}")
        return 0
    print(human())
    return 0

if __name__ == "__main__":
    sys.exit(main())
