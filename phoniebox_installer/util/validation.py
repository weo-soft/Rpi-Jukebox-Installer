"""Input validation helpers."""

from typing import Optional, Tuple
from urllib.parse import urlparse


def parse_github_branch_url(url: str) -> Optional[Tuple[str, str, str]]:
    """Parse a GitHub repo/tree URL into ``(owner, repo, branch)``.

    Accepts:
        https://github.com/<owner>/<repo>
        https://github.com/<owner>/<repo>/tree/<branch>
        http:// variants, an optional trailing slash and an optional ".git"
        suffix on the repository name.

    The branch is empty when the URL points at the repository root, and may
    itself contain slashes (e.g. "future3/feature/..."). Everything after
    ``/tree/`` is treated as the branch name.

    :return: ``(owner, repo, branch)`` or ``None`` if the URL is not a
        GitHub repository URL.
    """
    url = url.strip().rstrip("/")
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        return None
    if parsed.netloc not in ("github.com", "www.github.com"):
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    branch = ""
    if len(parts) >= 4 and parts[2] == "tree":
        branch = "/".join(parts[3:])

    return owner, repo, branch
