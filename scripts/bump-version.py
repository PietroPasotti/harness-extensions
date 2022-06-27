#! /bin/python3

import sys
from pathlib import Path


def bump_version(lib: str, minor: bool = True, major: bool = False):
    if not (major or minor):
        print("either major or minor needs to be true")
        return
    lib_root = Path() / 'libs' / lib
    sys.path.append(str(lib_root))

    try:
        import __version__  # noqa
    except ModuleNotFoundError:
        raise ValueError(lib)

    current_minor = __version__.revision
    current_major = __version__.version

    if minor:
        new_minor = current_minor + 1
        new_major = current_major
    else:
        new_minor = 0  # reset minor
        new_major = current_major + 1

    print(f"bumped to v{new_major}.{new_minor}")

    (lib_root / "__version__.py").write_text(
        f"""version = {new_major}\nrevision = {new_minor}\n"""
    )


if __name__ == "__main__":
    import typer

    typer.run(bump_version)
