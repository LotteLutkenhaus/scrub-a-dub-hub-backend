import logging

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from database import (
    add_office_member,
    deactivate_office_member,
    get_active_office_members,
    get_all_duties,
    get_most_recent_duty_by_type,
    mark_duty_completed,
    mark_duty_uncompleted,
    update_office_member,
)
from models import DutyCompletionPayload, DutyType, OfficeMember, ReducedOfficeMember
from upstash_utils import cache_recent_duty, get_cached_recent_duty, invalidate_recent_duty_cache

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/api/duties", methods=["GET"])
def get_duties() -> tuple[Response, int]:
    """
    Get all duties from the database
    """
    try:
        limit = request.args.get("limit", 100, type=int)

        duties = get_all_duties(limit=limit)

        return jsonify(
            {"duties": [duty.model_dump() for duty in duties], "total": len(duties)}
        ), 200

    except Exception as e:
        logger.error(f"Error in get_duties endpoint: {e}")
        return jsonify({"error": "Failed to retrieve duties"}), 500


@app.route("/api/duties/complete", methods=["POST"])
def complete_duty() -> tuple[Response, int]:
    """
    Mark a duty as completed
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        try:
            payload = DutyCompletionPayload.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": f"Problem validating payload: {e}"}), 400

        success = mark_duty_completed(payload.duty_id, payload.duty_type)

        if success:
            # Invalidate cache for this duty type
            invalidate_recent_duty_cache(payload.duty_type)

            # Get updated duty list to return
            duties = get_all_duties(limit=50)
            return jsonify(
                {
                    "message": "Duty marked as completed successfully",
                    "success": True,
                    "duties": [duty.model_dump() for duty in duties],
                }
            ), 200
        else:
            return jsonify({"error": "Failed to mark duty as completed"}), 500

    except Exception as e:
        logger.error(f"Error in complete_duty endpoint: {e}")
        return jsonify({"error": "Failed to complete duty"}), 500


@app.route("/api/duties/uncomplete", methods=["POST"])
def uncomplete_duty() -> tuple[Response, int]:
    """
    Mark a duty as uncompleted
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        try:
            payload = DutyCompletionPayload.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": f"Problem validating payload: {e}"}), 400

        success = mark_duty_uncompleted(payload.duty_id, payload.duty_type)

        if success:
            # Invalidate cache for this duty type
            invalidate_recent_duty_cache(payload.duty_type)

            # Get updated duty list to return
            duties = get_all_duties(limit=50)
            return jsonify(
                {
                    "message": "Duty marked as uncompleted successfully",
                    "success": True,
                    "duties": [duty.model_dump() for duty in duties],
                }
            ), 200
        else:
            return jsonify({"error": "Failed to mark duty as uncompleted"}), 500

    except Exception as e:
        logger.error(f"Error in uncomplete_duty endpoint: {e}")
        return jsonify({"error": "Failed to uncomplete duty"}), 500


@app.route("/api/duties/recent", methods=["GET"])
def get_recent_duty() -> tuple[Response, int]:
    """
    Get the most recent duty for a given duty type. Uses Redis caching to limit database requests.
    """
    try:
        duty_type_param = request.args.get("duty_type")

        if not duty_type_param:
            return jsonify({"error": "duty_type query parameter is required"}), 400

        try:
            duty_type = DutyType(duty_type_param)
        except ValueError:
            return jsonify({"error": f"Invalid duty_type {duty_type_param}"}), 400

        cached_duty_json = get_cached_recent_duty(duty_type)

        # Case: we found a recent duty in the cache
        if cached_duty_json:
            logger.info(f"Found recent {duty_type.value} duty in cache")
            return jsonify({"duty": cached_duty_json, "source": "cache"}), 200

        # Case: we didn't find a recent duty (or it was invalid json) in the cache
        logger.info(f"Didn't find {duty_type.value} duty in cache, fetching from database")
        duty = get_most_recent_duty_by_type(duty_type)

        if not duty:
            return jsonify({"error": f"No {duty_type.value} duty found"}), 404

        # Cache the result (1 hour TTL)
        cache_recent_duty(duty_type, duty.model_dump(), ttl_seconds=3600)

        return jsonify({"duty": duty.model_dump(), "source": "database"}), 200

    except Exception as e:
        logger.error(f"Error in get_recent_duty endpoint: {e}")
        return jsonify({"error": "Failed to retrieve recent duty"}), 500


@app.route("/api/members", methods=["GET"])
def get_members() -> tuple[Response, int]:
    """
    Get all office members.
    """
    try:
        members_list = get_active_office_members()
        members = [member.model_dump() for member in members_list]
        return jsonify({"members": members}), 200

    except Exception as e:
        logger.error(f"Error in get_members endpoint: {e}")
        return jsonify({"error": "Failed to retrieve members"}), 500


@app.route("/api/members", methods=["POST"])
def add_member() -> tuple[Response, int]:
    """
    Add a member to the office
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No member data provided"}), 400

        try:
            parsed_payload = ReducedOfficeMember.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": f"Problem validating payload: {e}"}), 400

        success = add_office_member(parsed_payload)

        if success:
            # Get updated member list to return
            members_list = get_active_office_members()
            return jsonify(
                {
                    "message": "New member added to the office",
                    "success": True,
                    "members": [member.model_dump() for member in members_list],
                }
            ), 200
        else:
            return jsonify({"error": f"Username '{parsed_payload.username}' already exists"}), 409

    except Exception as e:
        logger.error(f"Error in add_member endpoint: {e}")
        return jsonify({"error": "Failed to add new member"}), 500


@app.route("/api/members", methods=["DELETE"])
def deactivate_member() -> tuple[Response, int]:
    """
    Deactivate an office member.

    We won't delete them as we need the info for the historic overview of duties.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No member data provided"}), 400

        if (member_id := data.get("id")) is None:
            return jsonify({"error": "No member id provided"}), 400

        success = deactivate_office_member(member_id)

        if success:
            members_list = get_active_office_members()
            return jsonify(
                {
                    "message": "Deactivated office member",
                    "success": True,
                    "members": [member.model_dump() for member in members_list],
                }
            ), 200
        else:
            return jsonify({"error": "Failed to deactivate member"}), 500

    except Exception as e:
        logger.error(f"Error in deactivate_member endpoint: {e}")
        return jsonify({"error": "Failed to deactivate member"}), 500


@app.route("/api/members", methods=["PUT"])
def update_member() -> tuple[Response, int]:
    """
    Update an office member.
    """
    try:
        data = request.get_json()

        try:
            parsed_payload = OfficeMember.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": f"Problem validating payload: {e}"}), 400

        success = update_office_member(parsed_payload)

        if success:
            members_list = get_active_office_members()
            return jsonify(
                {
                    "message": "Updated office member",
                    "success": True,
                    "members": [member.model_dump() for member in members_list],
                }
            ), 200
        else:
            return jsonify({"error": "Failed to update member"}), 500

    except Exception as e:
        logger.error(f"Error in update_member endpoint: {e}")
        return jsonify({"error": "Failed to update a member"}), 500


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 4999))
    app.run(debug=False, host="0.0.0.0", port=port)
