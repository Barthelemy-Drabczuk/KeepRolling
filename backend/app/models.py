"""
SQLAlchemy Database Models for Moodometer

This module defines the database schema using SQLAlchemy ORM.
It includes three main tables:
- User: Stores user account information
- Mood: Stores mood entries with energy and valence values
- Entry: Stores journal entries associated with moods
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class UserModel(Base):
    """
    User table for storing user account information.
    
    Attributes:
        id: Primary key
        username: Unique username for login
        hashed_password: Bcrypt hashed password
        created_at: Account creation timestamp
        moods: Relationship to mood entries
        entries: Relationship to journal entries
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    moods = relationship("MoodModel", back_populates="user", cascade="all, delete-orphan")
    entries = relationship("EntryModel", back_populates="user", cascade="all, delete-orphan")


class MoodModel(Base):
    """
    Mood table for storing emotional state entries.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        timestamp: When the mood was recorded
        energy: Energy level (-1.0 to 1.0, high to low)
        valence: Emotional valence (-1.0 to 1.0, pleasant to unpleasant)
        notes: Optional free-text note attached to this mood
        user: Relationship to user
    """
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    energy = Column(Float, nullable=False)  # -1.0 (low) to 1.0 (high)
    valence = Column(Float, nullable=False)  # -1.0 (unpleasant) to 1.0 (pleasant)
    notes = Column(String, nullable=True)

    # Relationship
    user = relationship("UserModel", back_populates="moods")


class EntryModel(Base):
    """
    Entry table for storing journal entries.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        timestamp: When the entry was created
        content: Text content of the journal entry
        user: Relationship to user
    """
    __tablename__ = "entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    content = Column(String, nullable=False)
    
    # Relationship
    user = relationship("UserModel", back_populates="entries")

# Made with Bob
