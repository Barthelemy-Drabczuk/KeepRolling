from datetime import datetime

class User:
    """
    Represents a user in the Moodometer application with mood tracking and journal entry capabilities.
    
    The User class manages two types of data:
    1. Moods: Emotional states represented as (energy, valence) tuples mapped to timestamps
    2. Entries: Text-based journal entries mapped to timestamps
    
    Both moods and entries are stored as private attributes to enforce controlled access
    through getter/setter methods.
    """
    
    def __init__(self, username: str,
                 password: str,
                 moods: dict[datetime, tuple[int, int]]=dict(),
                 entries: dict[datetime, str] = dict()) -> None:
        """
        Initialize a new User instance.
        
        Args:
            username: Unique identifier for the user
            password: User's password (currently stored as plain text - should be hashed in production)
            moods: Optional dictionary mapping timestamps to mood tuples (energy, valence)
            entries: Optional dictionary mapping timestamps to journal entry strings
        """
        self.name: str = username
        self.password: str = password
        # Private attributes to encapsulate mood and entry data
        self.__moods: dict[datetime, tuple[int, int]] = moods
        self.__entries: dict[datetime, str] = entries

    def to_string(self) -> str:
        """
        Generate a string representation of the user.
        
        Returns:
            A formatted string containing username and password
        """
        return f"User(name={self.name},password={self.password})"

    # ==================== MOOD MANAGEMENT METHODS ====================
    
    def get_moods(self) -> dict[datetime, tuple[int, int]]:
        """
        Retrieve all mood entries for this user.
        
        Returns:
            Dictionary mapping datetime objects to mood tuples (energy, valence)
            where energy and valence are integers representing the emotional state
        """
        return self.__moods
    
    def add_mood(self, timestamp: datetime, mood: tuple[int, int]) -> None:
        """
        Add a new mood entry for the user.
        
        Args:
            timestamp: The datetime when the mood was recorded
            mood: A tuple of (energy, valence) representing the emotional state
                  - energy: High (positive) to Low (negative) energy level
                  - valence: Pleasant (positive) to Unpleasant (negative) feeling
        
        Note:
            If a mood already exists at the given timestamp, it will be overwritten.
            Use modify_mood() for explicit updates with error checking.
        """
        self.__moods[timestamp] = mood

    def modify_mood(self, timestamp: datetime, mood: tuple[int, int]) -> None:
        """
        Update an existing mood entry.
        
        Args:
            timestamp: The datetime of the mood entry to modify
            mood: The new mood tuple (energy, valence) to replace the existing one
        
        Raises:
            KeyError: If no mood entry exists at the given timestamp
        """
        if timestamp in self.__moods.keys():
            self.__moods[timestamp] = mood
        else:
            raise KeyError("User.modify_mood(): Given timestamp does not exist, use add_mood() method instead.")
        
    def remove_mood(self, timestamp: datetime) -> None:
        """
        Delete a mood entry from the user's history.
        
        Args:
            timestamp: The datetime of the mood entry to remove
        
        Raises:
            KeyError: If no mood entry exists at the given timestamp
        """
        if timestamp in self.__moods.keys():
            self.__moods.pop(timestamp)
        else:
            raise KeyError("User.remove_mood(): Given timestamp doest not exist, the entry was not removed.")

    # ==================== JOURNAL ENTRY MANAGEMENT METHODS ====================
    
    def get_entries(self) -> dict[datetime, str]:
        """
        Retrieve all journal entries for this user.
        
        Returns:
            Dictionary mapping datetime objects to journal entry strings
        """
        return self.__entries
    
    def add_entry(self, timestamp: datetime, entry: str) -> None:
        """
        Add a new journal entry for the user.
        
        Args:
            timestamp: The datetime when the entry was created
            entry: The text content of the journal entry
        
        Note:
            If an entry already exists at the given timestamp, it will be overwritten.
            Use modify_entry() for explicit updates with error checking.
        """
        self.__entries[timestamp] = entry

    def modify_entry(self, timestamp: datetime, entry: str) -> None:
        """
        Update an existing journal entry.
        
        Args:
            timestamp: The datetime of the entry to modify
            entry: The new text content to replace the existing entry
        
        Raises:
            KeyError: If no entry exists at the given timestamp
        """
        if timestamp in self.__entries.keys():
            self.__entries[timestamp] = entry
        else:
            raise KeyError("User.modify_entry: Given timestamp does not exist, use add_entry() method instead.")
    
    def remove_entry(self, timestamp: datetime) -> None:
        """
        Delete a journal entry from the user's history.
        
        Args:
            timestamp: The datetime of the entry to remove
        
        Raises:
            KeyError: If no entry exists at the given timestamp
        """
        if timestamp in self.__entries.keys():
            self.__entries.pop(timestamp)
        else:
            raise KeyError("User.remove_entry: Given timestamp doest not exist, the entry was not removed.")