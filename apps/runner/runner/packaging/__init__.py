"""Packaging module for artifact bundling and upload.

Public API:
    bundle_artifacts(run_id, repo_id, baseline_result, logs) -> list[ArtifactBundle]
    upload_artifacts(api_base_url, artifacts) -> list[dict]
"""

from runner.packaging.bundler import bundle_artifacts
from runner.packaging.uploader import upload_artifacts

__all__ = ["bundle_artifacts", "upload_artifacts"]
