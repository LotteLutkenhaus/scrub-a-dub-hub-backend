from enum import StrEnum

from pydantic import BaseModel


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
