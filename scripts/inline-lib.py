#! /bin/python3

import os
from pathlib import Path

import jinja2 as jinja2

import sys
sys.path.append(str(Path()))

import __version__

root = Path()


def inline_lib():
    print("Rendering $LIB_NAME lib...")
    py = root / "$LIB_NAME.py"
    template = root / "lib_template.jinja"

    assert py.exists()
    assert template.exists()

    lib_file = (
        root
        / "lib"
        / "charms"
        / "$LIB_NAME"  # $ TEMPLATE: Filled in by ./scripts/init.sh
        / f"v{__version__.version}"
        / "$LIB_NAME.py"  # $ TEMPLATE: Filled in by ./scripts/init.sh
    )

    if not lib_file.parent.exists():
        os.makedirs(lib_file.parent)

    rendered = jinja2.Template(template.read_text()).render(
        {
            "py": py.read_text(),
            "revision": __version__.revision,
            "version": __version__.version,
        }
    )
    print(f"Dropped {lib_file}.")
    lib_file.write_text(rendered)


if __name__ == "__main__":
    inline_lib()
