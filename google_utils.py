import logging

import requests
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


def get_project_id() -> str | None:
    """
    Get the Google Cloud project ID.
    """
    try:
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(metadata_url, headers=headers, timeout=5)
        if response.status_code != 200:
            logger.info(f"Failed to get project ID from Google's metadata service, response: {response}")
            return None

        project_id = response.text
        assert isinstance(project_id, str)
        return project_id

    except Exception:
        logger.error("Failed to get project ID from Google's metadata service", exc_info=True)
        return None


def get_secret(token_name: str) -> str:
    """
    Gets the secret from Google Secret Manager
    """
    client = secretmanager.SecretManagerServiceClient()
    project_id = get_project_id()
    assert project_id, "Project ID not set in environment variables"
    name = f"projects/{project_id}/secrets/{token_name}/versions/latest"
    response = client.access_secret_version(name=name)
    secret = response.payload.data.decode("UTF-8")

    assert isinstance(secret, str)

    return secret
