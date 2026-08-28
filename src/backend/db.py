"""
Database Connection Test Utility

This module provides a simple test script to verify database connectivity
for the Moodometer application. It uses SQLAlchemy to connect to PostgreSQL
and execute a basic query to confirm the connection is working.

Usage:
    python db.py

Requirements:
    - PostgreSQL database running and accessible
    - .env file in backend/app/ with DATABASE_URL configured
    - sqlalchemy and python-dotenv packages installed
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment variables from the .env file
    # This should contain DATABASE_URL with the PostgreSQL connection string
    load_dotenv()
    
    # Retrieve the database URL from environment variables
    # Expected format: postgresql://username:password@host:port/database
    database_url = str(os.getenv("DATABASE_URL"))

    # Create a SQLAlchemy engine for database connections
    # The engine manages connection pooling and database interactions
    engine = create_engine(database_url)

    # Open a connection and execute a test query
    with engine.connect() as conn:
        # Execute a simple SELECT query to test connectivity
        # The text() function allows raw SQL execution
        result = conn.execute(text("select 'hello world'"))
        
        # Print all results (should output: [('hello world',)])
        # If this prints successfully, the database connection is working
        print(result.all())
