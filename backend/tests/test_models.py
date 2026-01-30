"""Unit tests for data models."""

import pytest
from src.models import (
    GameStatus, SynonymSlot, GameSession, StartGameResponse,
    GuessRequest, GuessResponse, HintRequest, HintResponse
)


class TestSynonymSlot:
    """Test SynonymSlot model."""
    
    def test_valid_synonym_slot(self):
        """
        Given: Valid synonym slot data
        When: Creating a SynonymSlot
        Then: It should be created successfully
        """
        slot = SynonymSlot(word="happy", letter_count=5, found=True)
        assert slot.word == "happy"
        assert slot.letter_count == 5
        assert slot.found is True
    
    def test_empty_synonym_slot(self):
        """
        Given: Empty synonym slot data
        When: Creating a SynonymSlot
        Then: It should be created with defaults
        """
        slot = SynonymSlot(word=None, letter_count=6)
        assert slot.word is None
        assert slot.letter_count == 6
        assert slot.found is False
    
    def test_invalid_letter_count(self):
        """
        Given: Invalid letter count (zero or negative)
        When: Creating a SynonymSlot
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Letter count must be positive"):
            SynonymSlot(word=None, letter_count=0)
        
        with pytest.raises(ValueError, match="Letter count must be positive"):
            SynonymSlot(word=None, letter_count=-1)
    
    def test_word_length_mismatch(self):
        """
        Given: Word length doesn't match letter count
        When: Creating a SynonymSlot
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Word length must match letter count"):
            SynonymSlot(word="happy", letter_count=3)


class TestGameSession:
    """Test GameSession model."""
    
    def test_valid_game_session(self):
        """
        Given: Valid game session data
        When: Creating a GameSession
        Then: It should be created successfully
        """
        synonyms = [
            SynonymSlot(word=None, letter_count=6),
            SynonymSlot(word=None, letter_count=8),
            SynonymSlot(word=None, letter_count=4),
            SynonymSlot(word=None, letter_count=7)
        ]
        session = GameSession(
            session_id="test-123",
            target_word="happy",
            synonyms=synonyms,
            guess_count=0,
            status=GameStatus.ACTIVE,
            guessed_words=[]
        )
        assert session.session_id == "test-123"
        assert session.target_word == "happy"
        assert len(session.synonyms) == 4
        assert session.guess_count == 0
        assert session.status == GameStatus.ACTIVE
    
    def test_empty_session_id(self):
        """
        Given: Empty session ID
        When: Creating a GameSession
        Then: It should raise ValueError
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(4)]
        with pytest.raises(ValueError, match="Session ID cannot be empty"):
            GameSession("", "happy", synonyms, 0, GameStatus.ACTIVE, [])
    
    def test_invalid_target_word(self):
        """
        Given: Invalid target word (empty or with numbers/symbols)
        When: Creating a GameSession
        Then: It should raise ValueError
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(4)]
        
        with pytest.raises(ValueError, match="Target word must contain only letters"):
            GameSession("test", "", synonyms, 0, GameStatus.ACTIVE, [])
        
        with pytest.raises(ValueError, match="Target word must contain only letters"):
            GameSession("test", "happy123", synonyms, 0, GameStatus.ACTIVE, [])
    
    def test_wrong_synonym_count(self):
        """
        Given: Wrong number of synonyms (not 4)
        When: Creating a GameSession
        Then: It should raise ValueError
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(3)]
        with pytest.raises(ValueError, match="Game must have exactly 4 synonym slots"):
            GameSession("test", "happy", synonyms, 0, GameStatus.ACTIVE, [])
    
    def test_negative_guess_count(self):
        """
        Given: Negative guess count
        When: Creating a GameSession
        Then: It should raise ValueError
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(4)]
        with pytest.raises(ValueError, match="Guess count cannot be negative"):
            GameSession("test", "happy", synonyms, -1, GameStatus.ACTIVE, [])
    
    def test_is_complete_all_found(self):
        """
        Given: All synonyms are found
        When: Checking if game is complete
        Then: It should return True
        """
        synonyms = [
            SynonymSlot(word="joyful", letter_count=6, found=True),
            SynonymSlot(word="cheerful", letter_count=8, found=True),
            SynonymSlot(word="glad", letter_count=4, found=True),
            SynonymSlot(word="pleased", letter_count=7, found=True)
        ]
        session = GameSession("test", "happy", synonyms, 4, GameStatus.COMPLETED, [])
        assert session.is_complete() is True
    
    def test_is_complete_some_missing(self):
        """
        Given: Some synonyms are not found
        When: Checking if game is complete
        Then: It should return False
        """
        synonyms = [
            SynonymSlot(word="joyful", letter_count=6, found=True),
            SynonymSlot(word=None, letter_count=8, found=False),
            SynonymSlot(word=None, letter_count=4, found=False),
            SynonymSlot(word=None, letter_count=7, found=False)
        ]
        session = GameSession("test", "happy", synonyms, 1, GameStatus.ACTIVE, [])
        assert session.is_complete() is False
    
    def test_add_guess_new(self):
        """
        Given: A new guess
        When: Adding the guess
        Then: It should be added to guessed words and increment count
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(4)]
        session = GameSession("test", "happy", synonyms, 0, GameStatus.ACTIVE, [])
        
        session.add_guess("joyful")
        
        assert "joyful" in session.guessed_words
        assert session.guess_count == 1
    
    def test_add_guess_duplicate(self):
        """
        Given: A duplicate guess
        When: Adding the guess
        Then: It should not be added again but count should increment
        """
        synonyms = [SynonymSlot(word=None, letter_count=5) for _ in range(4)]
        session = GameSession("test", "happy", synonyms, 1, GameStatus.ACTIVE, ["joyful"])
        
        session.add_guess("joyful")
        
        assert session.guessed_words.count("joyful") == 1
        assert session.guess_count == 2


class TestGuessRequest:
    """Test GuessRequest model."""
    
    def test_valid_guess_request(self):
        """
        Given: Valid guess request data
        When: Creating a GuessRequest
        Then: It should be created and sanitized
        """
        request = GuessRequest(session_id="test-123", guess="Happy")
        assert request.session_id == "test-123"
        assert request.guess == "happy"  # Should be sanitized to lowercase
    
    def test_sanitize_guess_with_spaces(self):
        """
        Given: Guess with spaces and special characters
        When: Creating a GuessRequest
        Then: It should sanitize the guess
        """
        request = GuessRequest(session_id="test", guess="  happy!@#  ")
        assert request.guess == "happy"
    
    def test_empty_session_id(self):
        """
        Given: Empty session ID
        When: Creating a GuessRequest
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Session ID cannot be empty"):
            GuessRequest(session_id="", guess="happy")
    
    def test_empty_guess_after_sanitization(self):
        """
        Given: Guess that becomes empty after sanitization
        When: Creating a GuessRequest
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Guess cannot be empty after sanitization"):
            GuessRequest(session_id="test", guess="!@#$%")
    
    def test_guess_too_long(self):
        """
        Given: Very long guess
        When: Creating a GuessRequest
        Then: It should raise ValueError
        """
        long_guess = "a" * 51
        with pytest.raises(ValueError, match="Guess too long"):
            GuessRequest(session_id="test", guess=long_guess)


class TestHintRequest:
    """Test HintRequest model."""
    
    def test_valid_hint_request(self):
        """
        Given: Valid hint request data
        When: Creating a HintRequest
        Then: It should be created and sanitized
        """
        request = HintRequest(
            guess="sad",
            target_word="happy",
            previous_guesses=["angry", "mad"]
        )
        assert request.guess == "sad"
        assert request.target_word == "happy"
        assert request.previous_guesses == ["angry", "mad"]
    
    def test_sanitize_inputs(self):
        """
        Given: Inputs with special characters
        When: Creating a HintRequest
        Then: It should sanitize all inputs
        """
        request = HintRequest(
            guess="sad!@#",
            target_word="happy$%^",
            previous_guesses=["angry&*(", "mad123"]
        )
        assert request.guess == "sad"
        assert request.target_word == "happy"
        assert request.previous_guesses == ["angry", "mad"]
    
    def test_empty_guess_or_target(self):
        """
        Given: Empty guess or target word
        When: Creating a HintRequest
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Guess and target word cannot be empty"):
            HintRequest(guess="", target_word="happy", previous_guesses=[])
        
        with pytest.raises(ValueError, match="Guess and target word cannot be empty"):
            HintRequest(guess="sad", target_word="", previous_guesses=[])


class TestHintResponse:
    """Test HintResponse model."""
    
    def test_valid_hint_response(self):
        """
        Given: Valid hint response data
        When: Creating a HintResponse
        Then: It should be created successfully
        """
        response = HintResponse(
            hint_text="Try thinking of words that express joy",
            analysis_type="unrelated",
            confidence=0.8
        )
        assert response.hint_text == "Try thinking of words that express joy"
        assert response.analysis_type == "unrelated"
        assert response.confidence == 0.8
    
    def test_empty_hint_text(self):
        """
        Given: Empty hint text
        When: Creating a HintResponse
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Hint text cannot be empty"):
            HintResponse(hint_text="", analysis_type="unrelated", confidence=0.5)
    
    def test_invalid_analysis_type(self):
        """
        Given: Invalid analysis type
        When: Creating a HintResponse
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Invalid analysis type"):
            HintResponse(
                hint_text="Test hint",
                analysis_type="invalid",
                confidence=0.5
            )
    
    def test_invalid_confidence_range(self):
        """
        Given: Confidence outside 0.0-1.0 range
        When: Creating a HintResponse
        Then: It should raise ValueError
        """
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            HintResponse(
                hint_text="Test hint",
                analysis_type="unrelated",
                confidence=1.5
            )
        
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            HintResponse(
                hint_text="Test hint",
                analysis_type="unrelated",
                confidence=-0.1
            )