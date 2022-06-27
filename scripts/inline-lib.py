#! /bin/python3

import os
import sys
from pathlib import Path

import jinja2 as jinja2

root = Path()


def inline_lib(lib: str):
    print(f"Rendering {lib} lib...")

    lib_root = Path() / 'libs' / lib
    sys.path.append(str(lib_root))

    try:
        import __version__  # noqa
    except ModuleNotFoundError:
        raise ValueError(lib)

    lib_py_file = lib + ".py"
    py = lib_root / (lib_py_file)
    template = lib_root / "lib_template.jinja"

    assert py.exists()
    assert template.exists()

    lib_file = (
        root
        / "lib"
        / "charms"
        / "harness_extensions"
        / f"v{__version__.version}"
        / lib_py_file
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
    import typer

    typer.run(inline_lib)

