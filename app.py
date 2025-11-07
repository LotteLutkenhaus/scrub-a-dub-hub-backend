import logging

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from database import (
    add_office_member,
    get_all_duties,
    get_office_members,
    mark_duty_completed,
    mark_duty_uncompleted,
)
from models import DutyCompletionPayload, OfficeMemberPayload

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

        return jsonify({"duties": [duty.model_dump() for duty in duties], "total": len(duties)}), 200

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
            # Get updated duty list to return
            duties = get_all_duties(limit=50)
            return jsonify(
                {
                    "message": "Duty marked as uncompleted successfully",
                    "success": True,
                    "duties": [duty.model_dump() for duty in duties],  # Return updated list for immediate UI update
                }
            ), 200
        else:
            return jsonify({"error": "Failed to mark duty as uncompleted"}), 500

    except Exception as e:
        logger.error(f"Error in uncomplete_duty endpoint: {e}")
        return jsonify({"error": "Failed to uncomplete duty"}), 500


@app.route("/api/members", methods=["GET"])
def get_members() -> tuple[Response, int]:
    """
    Get all office members.
    """
    try:
        members_list = get_office_members()
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
            parsed_payload = OfficeMemberPayload.model_validate(data)
        except ValidationError as e:
            return jsonify({"error": f"Problem validating payload: {e}"}), 400

        success = add_office_member(parsed_payload)

        if success:
            # Get updated member list to return
            members_list = get_office_members()
            return jsonify(
                {
                    "message": "New member added to the office",
                    "success": True,
                    "members": [member.model_dump() for member in members_list],
                }
            ), 200
        else:
            return jsonify({"error": "Failed to add new member to the office"}), 500

    except Exception as e:
        logger.error(f"Error in add_member endpoint: {e}")
        return jsonify({"error": "Failed to add new member"}), 500


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 4999))
    app.run(debug=False, host="0.0.0.0", port=port)
