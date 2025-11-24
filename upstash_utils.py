import json
import logging
import os
from typing import Any

import requests

from google_utils import get_secret
from models import DutyType

logger = logging.getLogger(__name__)


def get_upstash_credentials() -> tuple[str, str]:
    """
    Get Upstash REST API credentials from environment or Google Secret Manager.

    Priority:
    1. UPSTASH_REST_URL and UPSTASH_REST_TOKEN environment variables (for local development)
    2. Google Secret Manager (for production)
    """
    # Check for local environment variables first
    upstash_url = os.getenv("UPSTASH_REST_URL")
    upstash_token = os.getenv("UPSTASH_REST_TOKEN")

    if upstash_url and upstash_token:
        logger.info("Using development Upstash credentials from environment")
        return upstash_url, upstash_token

    # Fall back to Google Secret Manager
    logger.info("Using Upstash credentials from Google Secret Manager")
    upstash_url = get_secret("upstash-rest-url")
    upstash_token = get_secret("upstash-rest-token")

    return upstash_url, upstash_token


def redis_set(key: str, value: str, ttl: int | None = None) -> bool:
    """
    Set a key-value pair in Redis via Upstash REST API.
    """
    upstash_url, upstash_token = get_upstash_credentials()

    # Build command
    command = ["SET", key, value]
    if ttl is not None:
        command.extend(["EX", str(ttl)])

    response = requests.post(
        upstash_url,
        headers={"Authorization": f"Bearer {upstash_token}"},
        json=command,
        timeout=5,
    )

    if response.status_code == 200:
        logger.info(f"Successfully set key: {key}")
        return True
    else:
        logger.error(f"Failed to set key {key}: {response.status_code} - {response.text}")
        return False


def redis_get(key: str) -> dict[str, Any] | None:
    """
    Get a value from Redis via Upstash REST API.
    """
    upstash_url, upstash_token = get_upstash_credentials()

    response = requests.post(
        upstash_url,
        headers={"Authorization": f"Bearer {upstash_token}"},
        json=["GET", key],
        timeout=5,
    )

    if response.status_code == 200:
        result = response.json()

        # Upstash returns {"result": value} or {"result": null}
        value = result.get("result")
        if value is None:
            logger.info(f"Key not found: {key}")
            return None

        logger.info(f"Successfully retrieved key: {key}")
        try:
            json_result: dict[str, Any] = json.loads(value)
            return json_result
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in cache for key: {key}")
            return None

    else:
        logger.error(f"Failed to get key {key}: {response.status_code} - {response.text}")
        return None


def redis_delete(key: str) -> bool:
    """
    Delete a key from Redis via Upstash REST API.
    """
    upstash_url, upstash_token = get_upstash_credentials()

    response = requests.post(
        upstash_url,
        headers={"Authorization": f"Bearer {upstash_token}"},
        json=["DEL", key],
        timeout=5,
    )

    if response.status_code == 200:
        logger.info(f"Successfully deleted key: {key}")
        return True
    else:
        logger.error(f"Failed to delete key {key}: {response.status_code} - {response.text}")
        return False


def cache_recent_duty(
    duty_type: DutyType, duty_json: dict[str, Any], ttl_seconds: int = 3600
) -> bool:
    """
    Cache the most recent duty for a given duty type.
    """
    cache_key = f"recent_duty:{duty_type}"
    return redis_set(cache_key, json.dumps(duty_json), ttl=ttl_seconds)


def get_cached_recent_duty(duty_type: DutyType) -> dict[str, Any] | None:
    """
    Get the cached most recent duty for a given duty type.
    """
    cache_key = f"recent_duty:{duty_type}"
    return redis_get(cache_key)


def invalidate_recent_duty_cache(duty_type: DutyType) -> bool:
    """
    Invalidate the cache for a specific duty type.
    """
    cache_key = f"recent_duty:{duty_type}"
    return redis_delete(cache_key)
