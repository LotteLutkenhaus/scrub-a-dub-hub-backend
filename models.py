from enum import StrEnum

from pydantic import BaseModel, field_validator


class DutyType(StrEnum):
    COFFEE = "coffee"
    FRIDGE = "fridge"


class OfficeMember(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    coffee_drinker: bool = True
    active: bool = True


class DutyResponse(BaseModel):
    duty_id: str
    duty_type: DutyType
    user_id: str
    username: str
    name: str
    selection_timestamp: str
    cycle_id: int
    completed: bool
    completed_timestamp: str | None = None


class DutyCompletionPayload(BaseModel):
    duty_id: str
    duty_type: DutyType


class OfficeMemberPayload(BaseModel):
    username: str
    full_name: str
    coffee_drinker: bool

    @field_validator("username")
    def cleanup_username(cls, value: str) -> str:
        """
        Lowercase, and remove the `@` in case a user enters this for `username`.
        """
        value = value.lower()

        if value.startswith("@"):
            return value[1:]

        return value

    @field_validator("full_name")
    def capitalize_name(cls, value: str) -> str:
        return value.capitalize()
