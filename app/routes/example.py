"""
User routes providing REST API endpoints for user management.
Implements CRUD operations for the User model.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserCreate, UserResponse, UserUpdate
from app import crud

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """
    Create a new user.

    Args:
        user_data: User creation data (name, email)
        db: Database session (injected)

    Returns:
        Created user with generated ID and timestamp

    Raises:
        HTTPException 400: If email already exists
    """
    try:
        user = crud.create_user(db, user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[UserResponse]:
    """
    Retrieve all users with pagination.

    Args:
        skip: Number of users to skip (default: 0)
        limit: Maximum number of users to return (default: 100)
        db: Database session (injected)

    Returns:
        List of users
    """
    return crud.get_all_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserResponse:
    """
    Retrieve a single user by their ID.

    Args:
        user_id: The user's unique ID
        db: Database session (injected)

    Returns:
        User data

    Raises:
        HTTPException 404: If user not found
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Update an existing user's information.

    Args:
        user_id: The user's ID to update
        user_data: Fields to update (name and/or email)
        db: Database session (injected)

    Returns:
        Updated user data

    Raises:
        HTTPException 404: If user not found
        HTTPException 400: If email is already in use
    """
    try:
        user = crud.update_user(db, user_id, user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> None:
    """
    Delete a user by their ID.

    Args:
        user_id: The user's ID to delete
        db: Database session (injected)

    Raises:
        HTTPException 404: If user not found
    """
    success = crud.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
