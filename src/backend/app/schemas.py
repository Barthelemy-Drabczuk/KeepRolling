"""
Pydantic Schemas for API Request/Response Validation

This module defines the data validation schemas used by the FastAPI endpoints.
These schemas ensure type safety and automatic validation of incoming requests
and outgoing responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """Base schema for user data"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    password: Optional[str] = Field(None, min_length=8, description="New password")


class UserResponse(UserBase):
    """Schema for user response (without password)"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Mood Schemas ====================

class MoodBase(BaseModel):
    """Base schema for mood data"""
    energy: float = Field(..., ge=-1.0, le=1.0, description="Energy level from -1 (low) to 1 (high)")
    valence: float = Field(..., ge=-1.0, le=1.0, description="Valence from -1 (unpleasant) to 1 (pleasant)")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional note attached to this mood")


class MoodCreate(MoodBase):
    """Schema for creating a new mood entry"""
    timestamp: Optional[datetime] = Field(None, description="Timestamp of mood (defaults to now)")


class MoodUpdate(MoodBase):
    """Schema for updating a mood entry"""
    pass


class MoodResponse(MoodBase):
    """Schema for mood response"""
    id: int
    user_id: int
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Entry Schemas ====================

class EntryBase(BaseModel):
    """Base schema for journal entry data"""
    content: str = Field(..., min_length=1, max_length=5000, description="Journal entry text")
    mood_id: Optional[int] = Field(None, description="Optional id of a mood this entry relates to")


class EntryCreate(EntryBase):
    """Schema for creating a new journal entry"""
    timestamp: Optional[datetime] = Field(None, description="Timestamp of entry (defaults to now)")


class EntryUpdate(EntryBase):
    """Schema for updating a journal entry"""
    pass


class EntryResponse(EntryBase):
    """Schema for entry response"""
    id: int
    user_id: int
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Authentication Schemas ====================

class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data"""
    username: Optional[str] = None


class LoginRequest(BaseModel):
    """Schema for login request"""
    username: str
    password: str


# ==================== Combined Response Schemas ====================

class UserWithMoodsAndEntries(UserResponse):
    """Schema for user with all moods and entries"""
    moods: list[MoodResponse] = []
    entries: list[EntryResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Statistics Schemas ====================

class MoodStatistics(BaseModel):
    """Schema for mood statistics"""
    average_energy: float
    average_valence: float
    total_moods: int
    date_range: tuple[datetime, datetime]
    most_common_quadrant: str

# Made with Bob
