"""Check the workshop steps for the ways they rot. Maintainers only.

Nine near-identical copies of main.py drift quietly. The failure that actually
embarrasses you live is a step whose answer key -- the next folder -- no longer
matches what its own TODOs asked for. This catches the mechanical half of that.

Run it after editing any step:

    uv run scripts/verify_steps.py

Checks, in order of how badly each one fails a room:

  1. Every step compiles.
  2. No "TODO (Step N.x)" marker survives into folder N+1. A marker that leaks
     means the answer key is not actually finished.
  3. Every step folder has a LAB.md, and 99-final has a README.md.
  4. Step 1's setup check names the same models Step 2 configures.
  5. Each step's growth over its predecessor is plausible -- a step that got
     *smaller* almost always means an edit landed in the wrong folder.
  6. ruff passes on all of them, using the config in pyproject.toml.

What it deliberately does not check: whether the code in step N+1 is a correct
implementation of step N's TODOs. Nothing but reading it will tell you that.
"""

import re
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STEPS = REPO / "steps"

# "TODO (Step 8.1)" and "TODO (Step 5.1)" alike.
MARKER = re.compile(r"TODO \(Step (\d+)(?:\.\w+)?\)")

# 01 is a standalone environment checker, not part of the agent program, so it
# is exempt from the growth check against its "predecessor".
STANDALONE = {"01-setup"}

# Optional detours. They sit in steps/ and are compiled, linted, and required to
# ship a LAB.md like everything else, but they are not links in the answer-key
# chain: 07 is 06's answer key, not 06b's. A detour carries its own answer key
# in its LAB.md, because nothing downstream can be it.
OPTIONAL = {"06b-bring-your-own-llm", "07b-healthcare"}


def step_dirs() -> list[Path]:
    """Return every step folder that ships runnable code, in workshop order.

    Returns:
        Sorted list of directories under steps/ that contain a main.py.
    """
    return sorted(d for d in STEPS.iterdir() if d.is_dir() and (d / "main.py").exists())


def all_step_dirs() -> list[Path]:
    """Return every step folder, including doc-only ones like 00-overview.

    Returns:
        Sorted list of directories under steps/.
    """
    return sorted(d for d in STEPS.iterdir() if d.is_dir())


def check_compiles(steps: list[Path]) -> list[str]:
    """Byte-compile every step's main.py.

    Args:
        steps: Step folders to check.

    Returns:
        A list of failure messages, empty when every file compiles.
    """
    failures = []
    for step in steps:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(step / "main.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{step.name}/main.py does not compile:\n{result.stderr}")
    return failures


def check_marker_leakage(steps: list[Path]) -> list[str]:
    """Confirm each step's TODO markers are resolved by the following step.

    Args:
        steps: Step folders, in order.

    Returns:
        A list of failure messages, empty when no marker leaks forward.
    """
    failures = []
    for step, answer_key in pairwise(steps):
        own = {m.group(1) for m in MARKER.finditer((step / "main.py").read_text())}
        leaked = {m.group(1) for m in MARKER.finditer((answer_key / "main.py").read_text())}
        for number in sorted(own & leaked):
            failures.append(
                f"{answer_key.name}/main.py still contains 'TODO (Step {number})' "
                f"markers that {step.name} asks the attendee to resolve -- "
                f"the answer key is unfinished.",
            )
    return failures


def check_docs(steps: list[Path]) -> list[str]:
    """Confirm every step ships the document an attendee is told to open.

    Covers doc-only steps such as 00-overview, which have no main.py and so
    never reach the code checks.

    Args:
        steps: Step folders to check. Ignored -- every folder is inspected.

    Returns:
        A list of failure messages, empty when every doc exists.
    """
    del steps
    failures = []
    for step in all_step_dirs():
        wanted = "README.md" if step.name.startswith("99") else "LAB.md"
        if not (step / wanted).exists():
            failures.append(f"{step.name}/ is missing {wanted}")
    return failures


def check_lab_links(_steps: list[Path]) -> list[str]:
    """Confirm every relative link in a step doc points at a file that exists.

    A broken "Next:" link strands an attendee mid-workshop, which is the kind
    of thing nobody notices until it happens in a room.

    Returns:
        A list of failure messages, empty when every link resolves.
    """
    link = re.compile(r"\]\((?!https?:)([^)#]+)\)")
    failures = []
    for doc in sorted(STEPS.glob("*/*.md")) + [REPO / "README.md", REPO / "FACILITATOR.md"]:
        for target in link.findall(doc.read_text()):
            if not (doc.parent / target).exists():
                failures.append(f"{doc.relative_to(REPO)} links to missing {target}")
    return failures


def check_setup_models(_steps: list[Path]) -> list[str]:
    """Confirm Step 1 checks the same models Step 2 configures.

    Step 1 opens the agent connection for real, so it names the three models
    itself rather than importing another step. That is the second place they
    are written down, and the failure it invites is a room whose setup check
    passes on models the workshop no longer uses.

    Returns:
        A list of failure messages, empty when the two agree.
    """
    setup = (STEPS / "01-setup" / "main.py").read_text()
    connect = (STEPS / "02-connect" / "main.py").read_text()

    failures = []
    for constant in ("LISTEN_MODEL", "THINK_MODEL", "SPEAK_MODEL"):
        match = re.search(rf'^{constant} = "([^"]+)"', setup, re.MULTILINE)
        if match is None:
            failures.append(f"01-setup/main.py no longer defines {constant}")
        elif f'model="{match.group(1)}"' not in connect:
            failures.append(
                f"01-setup/main.py checks {constant} = {match.group(1)!r}, which "
                f"02-connect/main.py does not configure. The setup check is "
                f"proving the wrong pipeline works.",
            )
    return failures


def check_growth(steps: list[Path]) -> list[str]:
    """Flag any step whose main.py shrank relative to the step before it.

    Each step adds to its predecessor, so line counts should climb. A drop
    almost always means an edit landed in the wrong folder.

    Args:
        steps: Step folders, in order.

    Returns:
        A list of failure messages, empty when every step grew or held steady.
    """
    failures = []
    for previous, step in pairwise(steps):
        if previous.name in STANDALONE or step.name in STANDALONE:
            continue
        before = len((previous / "main.py").read_text().splitlines())
        after = len((step / "main.py").read_text().splitlines())
        # Resolving a TODO block usually nets out shorter than the instructions
        # it replaces, so allow real slack -- this is a tripwire, not a metric.
        if after < before - 60:
            failures.append(
                f"{step.name}/main.py is {before - after} lines shorter than "
                f"{previous.name}/main.py. Did an edit land in the wrong folder?",
            )
    return failures


def check_lint() -> list[str]:
    """Run ruff over the steps, scripts, and the shared browser bridge.

    web/ is in the list deliberately. Attendees read it, and the repo's whole
    quality story is docstrings on everything -- letting the one folder nobody
    edits escape that is worse than the one-word diff.

    Returns:
        A list containing ruff's output when it fails, empty when it passes or
        ruff is unavailable.
    """
    try:
        result = subprocess.run(
            ["uvx", "ruff", "check", "steps", "scripts", "web"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("  (skipped: uvx not found)")
        return []

    if result.returncode != 0:
        return [result.stdout or result.stderr]
    return []


def main() -> None:
    """Run every check and report. Exits non-zero if any check fails."""
    steps = step_dirs()
    if not steps:
        print(f"No step folders found under {STEPS}")
        sys.exit(1)

    print(f"Checking {len(steps)} steps: {', '.join(s.name for s in steps)}\n")

    # The two pairwise checks run over the main line only. Leaving a detour in
    # would pair it with its neighbours and assert relationships that were never
    # meant to hold.
    chain = [step for step in steps if step.name not in OPTIONAL]

    failures = []
    for label, check in (
        ("compiles", lambda: check_compiles(steps)),
        ("no leaked TODO markers", lambda: check_marker_leakage(chain)),
        ("docs present", lambda: check_docs(steps)),
        ("doc links resolve", lambda: check_lab_links(steps)),
        ("setup checks the right models", lambda: check_setup_models(steps)),
        ("steps grow", lambda: check_growth(chain)),
        ("ruff", check_lint),
    ):
        print(f"- {label}")
        found = check()
        for failure in found:
            print(f"    FAIL: {failure}")
        failures.extend(found)

    if failures:
        print(f"\n{len(failures)} problem(s) found.")
        sys.exit(1)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
