"""README.md must describe the real CI (GitHub Actions), not a GitLab CI pipeline.

Pins REQ-DOCS-PERCEVASE-AE82E293D53D, -23AE62532A63, -247169E1574C,
-085986DF2E2A, -199ADE570088 and -F0DF817496BA (Task
TASK-DOCS-PERCEVASE-EBBE6CF149AE). Plain file reads only: nothing here
imports the application.

The README's other GitLab mentions (clone URL, "Open an issue on GitLab")
are out of scope and deliberately not asserted.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "README.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    """Body of the markdown section titled exactly `heading` (any level),
    up to the next heading of the same or a higher level. Empty if absent."""
    lines = _readme().splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*?)\s*$", line)
        if m and m.group(2) == heading:
            level = len(m.group(1))
            body = []
            for nxt in lines[i + 1 :]:
                n = re.match(r"^(#+)\s", nxt)
                if n and len(n.group(1)) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


def _bullet(section: str, label: str) -> str:
    """The `- **<label>**: ...` bullet line of `section`. Empty if absent."""
    for line in section.splitlines():
        if line.strip().startswith(f"- **{label}**"):
            return line
    return ""


def _architecture_tree() -> str:
    """The first fenced code block of the Architecture section."""
    m = re.search(r"```[^\n]*\n(.*?)```", _section("Architecture"), re.DOTALL)
    return m.group(1) if m else ""


def test_features_ci_bullet_names_github_actions():
    # REQ-DOCS-PERCEVASE-AE82E293D53D
    bullet = _bullet(_section("Features"), "CI/CD Pipeline")
    assert bullet, "Features section has no '- **CI/CD Pipeline**' bullet"
    assert "GitHub Actions" in bullet, f"Features CI/CD bullet: {bullet!r}"


def test_tech_stack_ci_bullet_names_github_actions():
    # REQ-DOCS-PERCEVASE-23AE62532A63
    bullet = _bullet(_section("Technology Stack"), "CI/CD")
    assert bullet, "Technology Stack section has no '- **CI/CD**' bullet"
    assert "GitHub Actions" in bullet, f"Technology Stack CI/CD bullet: {bullet!r}"


def test_project_tree_lists_github_workflow():
    # REQ-DOCS-PERCEVASE-247169E1574C: the tree names the file, and the file
    # the README points at really exists.
    assert WORKFLOW.is_file(), f"{WORKFLOW} does not exist"
    tree = _architecture_tree()
    assert tree, "Architecture section has no project tree code block"
    assert ".github/workflows/ci.yml" in tree, (
        "project tree does not list .github/workflows/ci.yml:\n" + tree
    )


def test_code_quality_describes_test_job():
    # REQ-DOCS-PERCEVASE-085986DF2E2A
    section = _section("Code Quality")
    assert section.strip(), "README.md has no 'Code Quality' section"
    low = section.lower()
    missing = [
        p for p in ("github actions", "pytest", "push", "pull request", "main")
        if p not in low
    ]
    assert not missing, f"Code Quality lacks {missing}:\n{section}"


def test_code_quality_describes_non_gating_lint_job():
    # REQ-DOCS-PERCEVASE-199ADE570088
    section = _section("Code Quality")
    assert section.strip(), "README.md has no 'Code Quality' section"
    low = section.lower()
    missing = [
        p for p in ("github actions", "ruff check", "ruff format --check", "non-gating")
        if p not in low
    ]
    assert not missing, f"Code Quality lacks {missing}:\n{section}"


@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param(r"gitlab ci", id="gitlab-ci"),
        pytest.param(r"\bSAST\b", id="sast"),
        pytest.param(r"secret detection", id="secret-detection"),
        pytest.param(r"security scanning", id="security-scanning"),
        pytest.param(r"\.gitlab-ci\.yml", id="gitlab-ci-yml"),
    ],
)
def test_readme_has_no_false_ci_claims(pattern):
    # REQ-DOCS-PERCEVASE-F0DF817496BA. Case-insensitive except SAST
    # (an acronym; case-insensitive would also match ordinary words).
    flags = 0 if pattern == r"\bSAST\b" else re.IGNORECASE
    hits = [
        f"{n}: {line}"
        for n, line in enumerate(_readme().splitlines(), 1)
        if re.search(pattern, line, flags)
    ]
    assert not hits, f"README.md still contains {pattern!r}:\n" + "\n".join(hits)
