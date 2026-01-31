"""Data models for SynonymSeeker backend."""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import re


class GameStatus(Enum):
    """Game status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    GIVEN_UP = "given-up"


@dataclass
class SynonymSlot:
    """Represents a synonym slot in the game."""
    word: Optional[str]
    letter_count: int
    found: bool = False
    
    def __post_init__(self):
        """Validate synonym slot data."""
        if self.letter_count <= 0:
            raise ValueError("Letter count must be positive")
        if self.word is not None and len(self.word) != self.letter_count:
            raise ValueError("Word length must match letter count")


@dataclass
class GameSession:
    """Represents a complete game session."""
    session_id: str
    target_word: str
    synonyms: List[SynonymSlot]
    guess_count: int
    status: GameStatus
    guessed_words: List[str]
    
    def __post_init__(self):
        """Validate game session data."""
        if not self.session_id:
            raise ValueError("Session ID cannot be empty")
        if not self.target_word or not re.match(r'^[a-zA-Z]+$', self.target_word):
            raise ValueError("Target word must contain only letters")
        if len(self.synonyms) != 4:
            raise ValueError("Game must have exactly 4 synonym slots")
        if self.guess_count < 0:
            raise ValueError("Guess count cannot be negative")
    
    def is_complete(self) -> bool:
        """Check if all synonyms have been found."""
        return all(slot.found for slot in self.synonyms)
    
    def add_guess(self, guess: str) -> None:
        """Add a guess to the guessed words list."""
        if guess not in self.guessed_words:
            self.guessed_words.append(guess)
        self.guess_count += 1


# API Request/Response Models

@dataclass
class StartGameRequest:
    """Request to start a new game."""
    pass  # No parameters needed


@dataclass
class StartGameResponse:
    """Response when starting a new game."""
    session_id: str
    target_word: str
    synonym_slots: List[dict]  # Contains only letter counts
    status: str = "active"
    
    def __post_init__(self):
        """Validate start game response."""
        if not self.session_id:
            raise ValueError("Session ID cannot be empty")
        if len(self.synonym_slots) != 4:
            raise ValueError("Must have exactly 4 synonym slots")


@dataclass
class GuessRequest:
    """Request to submit a guess."""
    session_id: str
    guess: str
    
    def __post_init__(self):
        """Validate and sanitize guess request."""
        if not self.session_id:
            raise ValueError("Session ID cannot be empty")
        
        # Store original guess for error messages
        original_guess = self.guess
        
        # Sanitize guess input
        self.guess = self._sanitize_guess(self.guess)
        
        # Comprehensive input validation
        self._validate_input(original_guess, self.guess)
    
    def _sanitize_guess(self, guess: str) -> str:
        """Sanitize user input by removing non-alphabetic characters."""
        if not guess:
            return ""
        
        # Strip whitespace and convert to lowercase
        sanitized = guess.strip().lower()
        
        # Keep only Unicode letters (not just ASCII)
        sanitized = ''.join(c for c in sanitized if c.isalpha())
        
        return sanitized
    
    def _validate_input(self, original: str, sanitized: str) -> None:
        """Comprehensive input validation with specific error messages."""
        # Check for empty input first
        if not original or not original.strip():
            raise ValueError("Guess cannot be empty")
        
        # Check for multiple words (spaces in original input) - high priority
        if ' ' in original.strip():
            raise ValueError("Please enter only one word")
        
        # Check for excessive length (before sanitization to catch attempts to bypass)
        if len(original) > 50:
            raise ValueError("Input too long (maximum 50 characters)")
        
        # Check for suspicious patterns that might indicate injection attempts - before other checks
        suspicious_patterns = [
            r'[<>{}[\]\\]',  # HTML/XML/JSON brackets
            r'[;|&$`]',      # Shell command separators
            r'(script|javascript|eval|function)',  # Script-related keywords
            r'(select|insert|update|delete|drop)',  # SQL keywords
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, original, re.IGNORECASE):
                raise ValueError("Invalid characters detected in input")
        
        # Check if input became empty after sanitization
        if not sanitized:
            raise ValueError("Guess must contain at least one letter")
        
        # Check sanitized length
        if len(sanitized) > 50:
            raise ValueError("Word too long (maximum 50 letters)")
        
        # Check minimum length
        if len(sanitized) < 1:
            raise ValueError("Word too short (minimum 1 letter)")
        
        # Ensure only alphabetic characters remain (allow Unicode letters)
        if not sanitized.isalpha():
            raise ValueError("Word must contain only letters")


@dataclass
class GuessResponse:
    """Response to a guess submission."""
    success: bool
    message: str
    hint: Optional[str]
    game_state: dict
    
    def __post_init__(self):
        """Validate guess response."""
        if not self.message:
            raise ValueError("Response message cannot be empty")


@dataclass
class GiveUpRequest:
    """Request to give up the current game."""
    session_id: str
    
    def __post_init__(self):
        """Validate give up request."""
        if not self.session_id:
            raise ValueError("Session ID cannot be empty")


@dataclass
class GiveUpResponse:
    """Response when giving up a game."""
    message: str
    game_state: dict
    
    def __post_init__(self):
        """Validate give up response."""
        if not self.message:
            raise ValueError("Response message cannot be empty")


# Agent Communication Models

@dataclass
class HintRequest:
    """Request for hint analysis from Hint Provider agent."""
    guess: str
    target_word: str
    previous_guesses: List[str]
    
    def __post_init__(self):
        """Validate hint request."""
        if not self.guess or not self.target_word:
            raise ValueError("Guess and target word cannot be empty")
        # Sanitize inputs to prevent prompt injection
        self.guess = self._sanitize_input(self.guess)
        self.target_word = self._sanitize_input(self.target_word)
        self.previous_guesses = [self._sanitize_input(g) for g in self.previous_guesses]
    
    def _sanitize_input(self, text: str) -> str:
        """Sanitize input to prevent prompt injection attacks."""
        if not text:
            return ""
        # Remove potential prompt injection patterns and limit to alphabetic characters
        sanitized = re.sub(r'[^a-zA-Z\s]', '', text.strip())
        return sanitized[:50]  # Limit length


@dataclass
class HintResponse:
    """Response from Hint Provider agent."""
    hint_text: str
    analysis_type: str  # "misspelling", "related", "unrelated"
    confidence: float
    
    def __post_init__(self):
        """Validate hint response."""
        if not self.hint_text:
            raise ValueError("Hint text cannot be empty")
        if self.analysis_type not in ["misspelling", "related", "unrelated"]:
            raise ValueError("Invalid analysis type")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")