"""Types for the packaging module."""

from dataclasses import dataclass


@dataclass
class ArtifactBundle:
    """A single artifact ready for upload.

    storage_path follows the convention:
        repos/{repo_id}/runs/{run_id}/{filename}
    """

    filename: str
    storage_path: str
    content: str
    artifact_type: str
