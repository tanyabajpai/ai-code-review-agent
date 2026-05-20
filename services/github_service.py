import os
import re
import shutil
import tempfile
import time
from git import Repo
import logging

logger = logging.getLogger(__name__)

# Regex for a valid GitHub HTTPS URL
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(\.git)?/?$"
)


class GitHubService:
    """Service for handling GitHub repository operations."""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone_repository(self, repo_url: str) -> str:
        """
        Clone a GitHub repository to a temporary directory.

        Args:
            repo_url: Public GitHub repository URL (HTTPS).

        Returns:
            Path to the cloned repository directory.

        Raises:
            ValueError: If the URL is not a valid GitHub repository URL.
            Exception:  If the clone operation fails.
        """
        # Validate URL before attempting to clone
        self._validate_url(repo_url)

        try:
            repo_name = self._extract_repo_name(repo_url)
            timestamp = int(time.time())
            clone_path = os.path.join(
                self.temp_dir, f"code_review_{repo_name}_{timestamp}"
            )

            # Remove stale directory from a previous run if it exists
            if os.path.exists(clone_path):
                self.cleanup_repository(clone_path)

            logger.info(f"Cloning {repo_url} → {clone_path}")
            Repo.clone_from(repo_url, clone_path, depth=1)  # shallow clone for speed

            return clone_path

        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            raise Exception(f"Failed to clone repository: {e}") from e

    def cleanup_repository(self, clone_path: str) -> None:
        """
        Remove a cloned repository directory.

        Handles Windows read-only file attributes that prevent deletion.

        Args:
            clone_path: Absolute path to the cloned repository.
        """
        if not clone_path or not os.path.exists(clone_path):
            return

        try:
            if os.name == "nt":  # Windows — clear read-only flags first
                for root, dirs, files in os.walk(clone_path):
                    for dir_name in dirs:
                        os.chmod(os.path.join(root, dir_name), 0o777)
                    for file_name in files:
                        os.chmod(os.path.join(root, file_name), 0o777)

            shutil.rmtree(clone_path, ignore_errors=True)

            # Retry once if the directory still exists (common on Windows)
            if os.path.exists(clone_path):
                logger.warning(f"First rmtree pass incomplete; retrying: {clone_path}")
                time.sleep(0.5)
                shutil.rmtree(clone_path, ignore_errors=True)

            logger.info(f"Cleaned up repository at {clone_path}")

        except Exception as e:
            logger.error(f"Error cleaning up repository: {e}")
            # Do not raise — cleanup failures are non-fatal

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_url(repo_url: str) -> None:
        """
        Raise ValueError if *repo_url* is not a valid GitHub HTTPS URL.

        Args:
            repo_url: URL string to validate.
        """
        if not repo_url or not isinstance(repo_url, str):
            raise ValueError("Repository URL must be a non-empty string.")

        url = repo_url.strip()
        if not _GITHUB_URL_RE.match(url):
            raise ValueError(
                f"'{url}' is not a valid GitHub repository URL. "
                "Expected format: https://github.com/<owner>/<repo>"
            )

    @staticmethod
    def _extract_repo_name(repo_url: str) -> str:
        """
        Extract a filesystem-safe repository name from the URL.

        Args:
            repo_url: Validated GitHub repository URL.

        Returns:
            Repository name string safe for use in a directory name.
        """
        name = repo_url.rstrip("/").split("/")[-1]
        name = name.replace(".git", "")
        # Replace any remaining non-alphanumeric chars (except _ and -) with _
        name = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
        return name or "repo"