"""
Moodometer FastAPI Application - Complete Implementation

This module defines the complete FastAPI application for the Moodometer mood tracking system.
It provides comprehensive RESTful API endpoints for:
- User management (CRUD operations)
- Mood tracking (CRUD operations)
- Journal entries (CRUD operations)
- Authentication (login/logout)
- Data export and analytics
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional

from database import get_db, init_db
from models import UserModel, MoodModel, EntryModel
from schemas import (
    UserCreate, UserUpdate, UserResponse, UserWithMoodsAndEntries,
    MoodCreate, MoodUpdate, MoodResponse,
    EntryCreate, EntryUpdate, EntryResponse,
    Token, LoginRequest
)
from auth import (
    hash_password, authenticate_user, create_access_token,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Create the FastAPI application instance
app = FastAPI(
    title="Moodometer API",
    description="A mood tracking application using the circumplex model of affect",
    version="1.0.0"
)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name='static')

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup"""
    init_db()


# ==================== ROOT & UI ENDPOINTS ====================

@app.get("/", tags=["UI"])
def read_root():
    """Serve the main mood board interface"""
    return FileResponse("index.html")


# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT access token.
    
    - **username**: User's username
    - **password**: User's password
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/logout", tags=["Authentication"])
async def logout(current_user: UserModel = Depends(get_current_active_user)):
    """
    Logout endpoint (JWT tokens are stateless, so this is mainly for client-side cleanup).
    Client should discard the token.
    """
    return {"message": "Successfully logged out"}


# ==================== USER ENDPOINTS ====================

@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Users"])
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.
    
    - **username**: Unique username (3-50 characters)
    - **password**: Password (minimum 8 characters)
    """
    # Check if username already exists
    existing_user = db.query(UserModel).filter(UserModel.username == user.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create new user with hashed password
    hashed_password = hash_password(user.password)
    db_user = UserModel(
        username=user.username,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@app.get("/users/{username}", response_model=UserResponse, tags=["Users"])
def get_user(username: str, db: Session = Depends(get_db)):
    """
    Retrieve user information by username.
    
    - **username**: The username to look up
    """
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    return user


@app.get("/users/{username}/full", response_model=UserWithMoodsAndEntries, tags=["Users"])
def get_user_with_data(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve user with all moods and entries (requires authentication).
    
    - **username**: The username to look up
    """
    # Users can only access their own full data
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's data"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    return user


@app.put("/users/{username}", response_model=UserResponse, tags=["Users"])
def update_user(
    username: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update user information (requires authentication).
    
    - **username**: The username to update
    - **password**: New password (optional)
    """
    # Users can only update their own account
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    # Update password if provided
    if user_update.password:
        user.hashed_password = hash_password(user_update.password)
    
    db.commit()
    db.refresh(user)
    
    return user


@app.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"])
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a user account (requires authentication).
    
    - **username**: The username to delete
    """
    # Users can only delete their own account
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    db.delete(user)
    db.commit()
    
    return None


# ==================== MOOD ENDPOINTS ====================

@app.post("/users/{username}/moods", response_model=MoodResponse, status_code=status.HTTP_201_CREATED, tags=["Moods"])
def create_mood(
    username: str,
    mood: MoodCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a new mood entry for a user (requires authentication).
    
    - **username**: The username
    - **energy**: Energy level from -1 (low) to 1 (high)
    - **valence**: Valence from -1 (unpleasant) to 1 (pleasant)
    - **timestamp**: Optional timestamp (defaults to now)
    """
    # Users can only create moods for themselves
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create moods for this user"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    db_mood = MoodModel(
        user_id=user.id,
        energy=mood.energy,
        valence=mood.valence,
        timestamp=mood.timestamp or datetime.utcnow()
    )
    
    db.add(db_mood)
    db.commit()
    db.refresh(db_mood)
    
    return db_mood


@app.get("/users/{username}/moods", response_model=List[MoodResponse], tags=["Moods"])
def get_moods(
    username: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve all mood entries for a user (requires authentication).
    
    - **username**: The username
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    # Users can only access their own moods
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's moods"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    moods = db.query(MoodModel).filter(MoodModel.user_id == user.id)\
        .order_by(MoodModel.timestamp.desc())\
        .offset(skip).limit(limit).all()
    
    return moods


@app.get("/users/{username}/moods/{mood_id}", response_model=MoodResponse, tags=["Moods"])
def get_mood(
    username: str,
    mood_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve a specific mood entry (requires authentication).
    
    - **username**: The username
    - **mood_id**: The mood entry ID
    """
    # Users can only access their own moods
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's moods"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    mood = db.query(MoodModel).filter(
        MoodModel.id == mood_id,
        MoodModel.user_id == user.id
    ).first()
    
    if not mood:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    return mood


@app.put("/users/{username}/moods/{mood_id}", response_model=MoodResponse, tags=["Moods"])
def update_mood(
    username: str,
    mood_id: int,
    mood_update: MoodUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update a mood entry (requires authentication).
    
    - **username**: The username
    - **mood_id**: The mood entry ID
    - **energy**: New energy level
    - **valence**: New valence level
    """
    # Users can only update their own moods
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's moods"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    mood = db.query(MoodModel).filter(
        MoodModel.id == mood_id,
        MoodModel.user_id == user.id
    ).first()
    
    if not mood:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    mood.energy = mood_update.energy
    mood.valence = mood_update.valence
    
    db.commit()
    db.refresh(mood)
    
    return mood


@app.delete("/users/{username}/moods/{mood_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Moods"])
def delete_mood(
    username: str,
    mood_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a mood entry (requires authentication).
    
    - **username**: The username
    - **mood_id**: The mood entry ID
    """
    # Users can only delete their own moods
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user's moods"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    mood = db.query(MoodModel).filter(
        MoodModel.id == mood_id,
        MoodModel.user_id == user.id
    ).first()
    
    if not mood:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    db.delete(mood)
    db.commit()
    
    return None


# ==================== ENTRY ENDPOINTS ====================

@app.post("/users/{username}/entries", response_model=EntryResponse, status_code=status.HTTP_201_CREATED, tags=["Entries"])
def create_entry(
    username: str,
    entry: EntryCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a new journal entry for a user (requires authentication).
    
    - **username**: The username
    - **content**: Journal entry text
    - **timestamp**: Optional timestamp (defaults to now)
    """
    # Users can only create entries for themselves
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create entries for this user"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    db_entry = EntryModel(
        user_id=user.id,
        content=entry.content,
        timestamp=entry.timestamp or datetime.utcnow()
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return db_entry


@app.get("/users/{username}/entries", response_model=List[EntryResponse], tags=["Entries"])
def get_entries(
    username: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve all journal entries for a user (requires authentication).
    
    - **username**: The username
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    # Users can only access their own entries
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's entries"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    entries = db.query(EntryModel).filter(EntryModel.user_id == user.id)\
        .order_by(EntryModel.timestamp.desc())\
        .offset(skip).limit(limit).all()
    
    return entries


@app.get("/users/{username}/entries/{entry_id}", response_model=EntryResponse, tags=["Entries"])
def get_entry(
    username: str,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Retrieve a specific journal entry (requires authentication).
    
    - **username**: The username
    - **entry_id**: The entry ID
    """
    # Users can only access their own entries
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's entries"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    entry = db.query(EntryModel).filter(
        EntryModel.id == entry_id,
        EntryModel.user_id == user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    return entry


@app.put("/users/{username}/entries/{entry_id}", response_model=EntryResponse, tags=["Entries"])
def update_entry(
    username: str,
    entry_id: int,
    entry_update: EntryUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update a journal entry (requires authentication).
    
    - **username**: The username
    - **entry_id**: The entry ID
    - **content**: New entry text
    """
    # Users can only update their own entries
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's entries"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    entry = db.query(EntryModel).filter(
        EntryModel.id == entry_id,
        EntryModel.user_id == user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    entry.content = entry_update.content
    
    db.commit()
    db.refresh(entry)
    
    return entry


@app.delete("/users/{username}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Entries"])
def delete_entry(
    username: str,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a journal entry (requires authentication).
    
    - **username**: The username
    - **entry_id**: The entry ID
    """
    # Users can only delete their own entries
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user's entries"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    entry = db.query(EntryModel).filter(
        EntryModel.id == entry_id,
        EntryModel.user_id == user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    db.delete(entry)
    db.commit()
    
    return None


# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/users/{username}/analytics/statistics", tags=["Analytics"])
async def get_mood_statistics(
    username: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get comprehensive mood statistics for a user.
    
    - **username**: The username
    - **start_date**: Optional start date (ISO format)
    - **end_date**: Optional end date (ISO format)
    """
    from analytics import calculate_mood_statistics
    from datetime import datetime as dt
    
    # Users can only access their own analytics
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's analytics"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    # Parse dates if provided
    start = dt.fromisoformat(start_date) if start_date else None
    end = dt.fromisoformat(end_date) if end_date else None
    
    stats = calculate_mood_statistics(db, user.id, start, end)
    return stats


@app.get("/users/{username}/analytics/patterns", tags=["Analytics"])
async def get_mood_patterns(
    username: str,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Detect patterns in mood data.
    
    - **username**: The username
    - **days**: Number of days to analyze (default: 30)
    """
    from analytics import detect_mood_patterns
    
    # Users can only access their own analytics
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's analytics"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    patterns = detect_mood_patterns(db, user.id, days)
    return patterns


@app.get("/users/{username}/analytics/insights", response_model=List[str], tags=["Analytics"])
async def get_mood_insights(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get personalized insights from mood data.
    
    - **username**: The username
    """
    from analytics import generate_insights
    
    # Users can only access their own analytics
    if current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's insights"
        )
    
    user = db.query(UserModel).filter(UserModel.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {username} does not exist"
        )
    
    insights = generate_insights(db, user.id)
    return insights

# Made with Bob
