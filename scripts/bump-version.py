#! /bin/python3

from pathlib import Path

import sys
sys.path.append(str(Path()))

import __version__

root = Path()


def bump_version(minor: bool = True, major: bool = False):
    if not (major or minor):
        print("either major or minor needs to be true")
        return

    current_minor = __version__.revision
    current_major = __version__.version

    if minor:
        new_minor = current_minor + 1
        new_major = current_major
    else:
        new_minor = 0  # reset minor
        new_major = current_major + 1

    print(f"bumped to v{new_major}.{new_minor}")

    (root / "__version__.py").write_text(
        f"""version = {new_major}\nrevision = {new_minor}\n"""
    )


if __name__ == "__main__":
    import typer

    typer.run(bump_version)
