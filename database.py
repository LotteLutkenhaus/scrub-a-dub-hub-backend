import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    desc,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

from google_utils import get_secret
from models import DutyResponse, DutyType, OfficeMember, ReducedOfficeMember

logger = logging.getLogger(__name__)

# We're using some strategic type: ignore statements in this file to prevent this from becoming
# overcomplicated in order to ensure type safety.
Base = declarative_base()  # type: ignore[assignment]


class MemberTable(Base):  # type: ignore[valid-type,misc]
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    coffee_drinker = Column(Boolean, default=True)
    active = Column(Boolean, default=True)


class DutyAssignmentTable(Base):  # type: ignore[valid-type,misc]
    __tablename__ = "duty_assignments"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    duty_type = Column(String(20), nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())
    cycle_id = Column(Integer, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)


def get_database_url() -> str:
    """
    Get database connection URL from environment variable or Google Secret Manager.

    Priority:
    1. DATABASE_DEV_URL environment variable (for local development)
    2. Google Secret Manager (for production)
    """
    # Check for local environment variable first
    connection_string = os.getenv("DATABASE_URL_DEV")

    if connection_string:
        logger.info("Using development database connection")
        return connection_string

    # Fall back to Google Secret Manager
    secret_name = "neon-database-connection-string"
    logger.info(f"Using database URL from Google Secret Manager: {secret_name}")
    connection_string = get_secret(secret_name)

    return connection_string


@contextmanager
def get_db_session() -> Generator[Session, Any, None]:
    """
    Context manager for database sessions.
    """
    engine = create_engine(get_database_url())
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_active_office_members(coffee_drinkers_only: bool = False) -> list[OfficeMember]:
    """
    Fetch office members from database.
    """
    with get_db_session() as session:
        query = session.query(MemberTable).filter(MemberTable.active == True)

        if coffee_drinkers_only:
            query = query.filter(MemberTable.coffee_drinker == True)

        members = query.all()

        return [OfficeMember.model_validate(member.__dict__) for member in members]


def add_office_member(payload: ReducedOfficeMember) -> bool:
    """
    Add an office member to the database
    """
    # TODO: add support for the case a deactivated member gets reactivated
    try:
        with get_db_session() as session:
            new_member = MemberTable(
                username=payload.username,
                full_name=payload.full_name,
                coffee_drinker=payload.coffee_drinker,
                active=True,
            )
            session.add(new_member)
            session.flush()  # Get the auto-generated ID

            logger.info(f"Added new office member: {payload.username} (ID: {new_member.id})")

            return True
    except IntegrityError:
        logger.warning(f"Member with username '{payload.username}' already exists")
        return False


def deactivate_office_member(id_: int) -> bool:
    """
    Deactivate an office member
    """
    with get_db_session() as session:
        member = session.query(MemberTable).filter(MemberTable.id == id_).first()

        if not member:
            logger.warning(f"No member found with ID {id_}")
            return False

        if not member.active:
            logger.warning(f"Member {id_} is already inactive")
            return False

        member.active = False  # type: ignore[assignment]
        logger.info(f"Deactivated office member: {member.username} (ID: {id_})")

        return True


def update_office_member(office_member: OfficeMember) -> bool:
    """
    Update the data for an existing office member
    """
    try:
        with get_db_session() as session:
            member = session.query(MemberTable).filter(MemberTable.id == office_member.id).first()

            if not member:
                logger.warning(f"No member found with ID {office_member.id}")
                return False

            # Update fields
            member.username = office_member.username  # type: ignore[assignment]
            member.full_name = office_member.full_name  # type: ignore[assignment]
            member.coffee_drinker = office_member.coffee_drinker  # type: ignore[assignment]
            member.active = office_member.active  # type: ignore[assignment]

            logger.info(f"Updated office member: {office_member.username} (ID: {office_member.id})")

            return True
    except IntegrityError:
        logger.warning(f"Cannot update member {office_member.id}: username '{office_member.username}' already exists")
        return False


def get_all_duties(limit: int = 100) -> list[DutyResponse]:
    """
    Retrieve all duty assignments with completion status.
    """
    with get_db_session() as session:
        query = (
            session.query(DutyAssignmentTable, MemberTable.username, MemberTable.full_name)  # type: ignore[call-overload]
            .join(MemberTable, DutyAssignmentTable.member_id == MemberTable.id)
            .filter(MemberTable.active == True)
            .order_by(desc(DutyAssignmentTable.assigned_at))
            .limit(limit)
        )

        results = []
        for assignment, username, full_name in query:
            duty_response = DutyResponse(
                duty_id=str(assignment.id),
                duty_type=DutyType(assignment.duty_type),
                user_id=str(assignment.member_id),
                username=username,
                name=full_name or username,
                selection_timestamp=assignment.assigned_at.isoformat(),
                cycle_id=assignment.cycle_id,
                completed=assignment.completed,
                completed_timestamp=assignment.completed_at.isoformat() if assignment.completed_at else None,
            )
            results.append(duty_response)

        logger.info(f"Retrieved {len(results)} duties from database")
        return results


def mark_duty_completed(duty_id: str, duty_type: str) -> bool:
    """
    Mark a duty as completed by updating the completed flag and setting the timestamp.
    """
    with get_db_session() as session:
        assignment = (
            session.query(DutyAssignmentTable)
            .filter(
                DutyAssignmentTable.id == int(duty_id),
                DutyAssignmentTable.duty_type == duty_type,
            )
            .first()
        )

        if not assignment:
            logger.warning(f"No {duty_type} duty found with ID {duty_id}")
            return False

        if assignment.completed:
            logger.warning(f"{duty_type.capitalize()} duty {duty_id} is already completed")
            return False

        assignment.completed = True  # type: ignore[assignment]
        assignment.completed_at = datetime.now()  # type: ignore[assignment]

        logger.info(f"Marked {duty_type} duty {duty_id} as completed")
        return True


def mark_duty_uncompleted(duty_id: str, duty_type: str) -> bool:
    """
    Mark a duty as uncompleted by updating the completed flag and clearing timestamp.
    """
    with get_db_session() as session:
        assignment = (
            session.query(DutyAssignmentTable)
            .filter(
                DutyAssignmentTable.id == int(duty_id),
                DutyAssignmentTable.duty_type == duty_type,
            )
            .first()
        )

        if not assignment:
            logger.warning(f"No {duty_type} duty found with ID {duty_id}")
            return False

        if not assignment.completed:
            logger.warning(f"{duty_type.capitalize()} duty {duty_id} is already uncompleted")
            return False

        assignment.completed = False  # type: ignore[assignment]
        assignment.completed_at = None  # type: ignore[assignment]

        logger.info(f"Marked {duty_type} duty {duty_id} as uncompleted")
        return True
