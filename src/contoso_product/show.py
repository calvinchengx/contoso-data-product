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
import shutil
import sys
from pathlib import Path

from . import gold_dir, silver_dir
from .contracts import PRODUCT_NAME

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


def inventory() -> dict[str, object]:
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
    for layer in ("silver", "gold"):
        data = inv[layer]
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
    for layer in ("silver", "gold"):
        data = inv[layer]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contoso_product.show", description=__doc__.splitlines()[0])
    parser.add_argument("--into", metavar="DIR", help="copy the product's dbt projects here and print the path")
    parser.add_argument("--markdown", action="store_true", help="emit the README inventory block")
    parser.add_argument("--check", metavar="README", help="fail if that README's block is not what this version contains")
    args = parser.parse_args(argv)

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
