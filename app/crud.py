"""
CRUD (Create, Read, Update, Delete) operations for database models.
Provides a clean interface for database interactions.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.schemas import UserCreate, UserUpdate


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user in the database.

    Args:
        db: Database session
        user_data: User creation data (name, email)

    Returns:
        Created User object

    Raises:
        ValueError: If email already exists
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise ValueError(f"User with email '{user_data.email}' already exists")

    user = User(name=user_data.name, email=user_data.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """
    Retrieve all users with pagination.

    Args:
        db: Database session
        skip: Number of records to skip (offset)
        limit: Maximum number of records to return

    Returns:
        List of User objects
    """
    return db.query(User).offset(skip).limit(limit).all()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Retrieve a single user by their ID.

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        User object if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Retrieve a user by their email address.

    Args:
        db: Database session
        email: The user's email

    Returns:
        User object if found, None otherwise
    """
    return db.query(User).filter(User.email == email).first()


def update_user(db: Session, user_id: int, user_data: UserUpdate) -> Optional[User]:
    """
    Update an existing user's information.

    Args:
        db: Database session
        user_id: The user's ID to update
        user_data: Fields to update (name and/or email)

    Returns:
        Updated User object if found, None otherwise

    Raises:
        ValueError: If email is already taken by another user
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = user_data.model_dump(exclude_unset=True)

    # Check for email conflicts
    if "email" in update_data:
        existing = get_user_by_email(db, update_data["email"])
        if existing and existing.id != user_id:
            raise ValueError(f"Email '{update_data['email']}' is already in use")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """
    Delete a user from the database.

    Args:
        db: Database session
        user_id: The user's ID to delete

    Returns:
        True if user was deleted, False if not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    db.delete(user)
    db.commit()
    return True
