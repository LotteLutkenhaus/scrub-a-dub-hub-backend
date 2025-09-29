import os

from google.cloud import secretmanager

# Get project ID from environment variables (automatically set in Cloud Run)
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")


def get_secret(token_name: str) -> str:
    """
    Gets the secret from Google Secret Manager
    :param token_name: str with name of the token in GSM
    :return: secret: str unhashed version of the secret
    """
    client = secretmanager.SecretManagerServiceClient()

    assert PROJECT_ID, "Project ID not set in environment variables"
    name = f"projects/{PROJECT_ID}/secrets/{token_name}/versions/latest"
    response = client.access_secret_version(name=name)
    secret = response.payload.data.decode("UTF-8")

    assert isinstance(secret, str)

    return secret
