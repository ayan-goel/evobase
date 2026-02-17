"""Artifact uploader — sends bundled artifacts to the API.

Uses API callbacks to create artifact records in the database.
In Phase 6, storage upload is stubbed; real Supabase Storage
integration comes when the infra is wired.

The upload flow:
1. POST artifact content to the API (or directly to Supabase Storage)
2. API creates an artifact record in Postgres with the storage path
3. Frontend fetches signed URLs through the API to access artifacts
"""

import logging

import httpx

from runner.packaging.types import ArtifactBundle

logger = logging.getLogger(__name__)

# Timeout for API callbacks
API_TIMEOUT = 30


async def upload_artifacts(
    api_base_url: str,
    proposal_id: str,
    bundles: list[ArtifactBundle],
) -> list[dict]:
    """Upload artifact bundles via API callbacks.

    For each bundle, POSTs the artifact metadata to the API.
    The API creates artifact records pointing to the storage path.

    Returns a list of created artifact records.
    """
    results: list[dict] = []

    async with httpx.AsyncClient(
        base_url=api_base_url,
        timeout=API_TIMEOUT,
    ) as client:
        for bundle in bundles:
            try:
                result = await _upload_single(client, proposal_id, bundle)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Failed to upload artifact %s: %s",
                    bundle.filename,
                    exc,
                )
                results.append({
                    "filename": bundle.filename,
                    "error": str(exc),
                    "uploaded": False,
                })

    logger.info(
        "Uploaded %d/%d artifacts",
        sum(1 for r in results if r.get("uploaded", True) and "error" not in r),
        len(bundles),
    )
    return results


async def _upload_single(
    client: httpx.AsyncClient,
    proposal_id: str,
    bundle: ArtifactBundle,
) -> dict:
    """Upload a single artifact bundle.

    In Phase 6, this creates an artifact record via API callback.
    The actual file content would be uploaded to Supabase Storage
    in a production setup.
    """
    payload = {
        "proposal_id": proposal_id,
        "storage_path": bundle.storage_path,
        "type": bundle.artifact_type,
        "content": bundle.content,
    }

    response = await client.post(
        "/artifacts/upload",
        json=payload,
    )

    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"Upload failed: {response.status_code}",
            request=response.request,
            response=response,
        )

    return {
        "filename": bundle.filename,
        "storage_path": bundle.storage_path,
        "uploaded": True,
        **response.json(),
    }
