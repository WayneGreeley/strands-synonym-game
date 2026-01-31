"""Tests for Game Builder Agent."""

import os
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from hypothesis import given, strategies as st
from src.game_builder_agent import GameBuilderAgent
from src.models import GuessRequest, GameStatus


class TestGameBuilderAgent:
    """Test Game Builder Agent functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.agent = GameBuilderAgent()
    
    def test_agent_initialization(self):
        """
        Given: GameBuilderAgent initialization
        When: Creating a new agent instance
        Then: Agent should be properly configured with tools and system prompt
        """
        assert self.agent.agent is not None
        assert len(self.agent.agent.tool_names) == 3  # generate_word_puzzle, validate_guess, request_hint_analysis
        assert self.agent.sessions == {}
    
    def test_start_new_game(self):
        """
        Given: A request to start a new game
        When: Calling start_new_game
        Then: Should return a valid game session with target word and 4 synonym slots
        """
        response = self.agent.start_new_game()
        
        assert response.session_id is not None
        assert len(response.session_id) > 0
        assert response.target_word is not None
        assert len(response.target_word) > 0
        assert len(response.synonym_slots) == 4
        assert response.status == "active"
        
        # Verify session is stored
        assert response.session_id in self.agent.sessions
        session = self.agent.sessions[response.session_id]
        assert session.target_word == response.target_word
        assert len(session.synonyms) == 4
        assert session.status == GameStatus.ACTIVE
    
    @given(st.integers(min_value=1, max_value=100))
    def test_property_15_word_generation_quality(self, seed):
        """
        Feature: synonym-seeker, Property 15: Word Generation Quality
        For any generated word puzzle, the target word SHALL have exactly four distinct, 
        valid synonyms that are appropriate for the game context.
        """
        # Given: Any word generation request
        # When: Generating a word puzzle
        puzzle = self.agent.generate_word_puzzle()
        
        # Then: Should have exactly 4 distinct synonyms
        assert "target_word" in puzzle
        assert "synonyms" in puzzle
        assert len(puzzle["synonyms"]) == 4
        
        # Verify target word is valid
        target_word = puzzle["target_word"]
        assert isinstance(target_word, str)
        assert len(target_word) > 0
        assert target_word.isalpha()
        
        # Verify all synonyms are distinct and valid
        synonym_words = [syn["word"] for syn in puzzle["synonyms"]]
        assert len(set(synonym_words)) == 4  # All distinct
        
        for syn_data in puzzle["synonyms"]:
            syn_word = syn_data["word"]
            letter_count = syn_data["letter_count"]
            
            # Synonym should be valid
            assert isinstance(syn_word, str)
            assert len(syn_word) > 0
            assert syn_word.isalpha()
            assert len(syn_word) == letter_count
            
            # Synonym should be appropriate length (not too short/long)
            assert 3 <= len(syn_word) <= 15
            
            # Synonym should not be the target word
            assert syn_word.lower() != target_word.lower()
    
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20),
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20),
        st.lists(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20), min_size=1, max_size=10)
    )
    def test_property_2_synonym_validation_consistency(self, guess, target_word, synonym_list):
        """
        Feature: synonym-seeker, Property 2: Synonym Validation Consistency
        For any guess and target word combination, the validation result SHALL be 
        consistent and deterministic across multiple calls.
        """
        # Given: Any guess, target word, and synonym list
        # When: Validating the same guess multiple times
        synonyms = [{"word": syn, "letter_count": len(syn)} for syn in synonym_list]
        
        # Then: Results should be consistent
        result1 = self.agent.validate_guess(guess, target_word, synonyms)
        result2 = self.agent.validate_guess(guess, target_word, synonyms)
        result3 = self.agent.validate_guess(guess, target_word, synonyms)
        
        assert result1 == result2 == result3, "Validation should be deterministic"
        
        # Additional validation properties
        if guess.lower() == target_word.lower():
            assert result1 is False, "Target word should never be valid as guess"
        elif guess.lower() in [syn.lower() for syn in synonym_list]:
            assert result1 is True, "Exact synonym matches should be valid (unless it's the target word)"
    
    def test_validate_guess_correct_synonym(self):
        """
        Given: A correct synonym guess
        When: Validating the guess
        Then: Should return True
        """
        synonyms = [
            {"word": "joyful", "letter_count": 6},
            {"word": "cheerful", "letter_count": 8},
            {"word": "glad", "letter_count": 4},
            {"word": "pleased", "letter_count": 7}
        ]
        
        result = self.agent.validate_guess("joyful", "happy", synonyms)
        assert result is True
    
    def test_validate_guess_incorrect_word(self):
        """
        Given: An incorrect guess
        When: Validating the guess
        Then: Should return False
        """
        synonyms = [
            {"word": "joyful", "letter_count": 6},
            {"word": "cheerful", "letter_count": 8},
            {"word": "glad", "letter_count": 4},
            {"word": "pleased", "letter_count": 7}
        ]
        
        result = self.agent.validate_guess("sad", "happy", synonyms)
        assert result is False
    
    def test_validate_guess_target_word_rejected(self):
        """
        Given: The target word as a guess
        When: Validating the guess
        Then: Should return False (target word not allowed)
        """
        synonyms = [
            {"word": "joyful", "letter_count": 6},
            {"word": "cheerful", "letter_count": 8},
            {"word": "glad", "letter_count": 4},
            {"word": "pleased", "letter_count": 7}
        ]
        
        result = self.agent.validate_guess("happy", "happy", synonyms)
        assert result is False
    
    def test_validate_guess_close_misspelling(self):
        """
        Given: A close misspelling of a valid synonym
        When: Validating the guess
        Then: Should return True
        """
        synonyms = [
            {"word": "joyful", "letter_count": 6},
            {"word": "cheerful", "letter_count": 8},
            {"word": "glad", "letter_count": 4},
            {"word": "pleased", "letter_count": 7}
        ]
        
        # Test close misspelling
        result = self.agent.validate_guess("joyfull", "happy", synonyms)  # Extra 'l'
        assert result is True
        
        result = self.agent.validate_guess("joyfl", "happy", synonyms)  # Missing 'u'
        assert result is True
    
    def test_submit_guess_correct(self):
        """
        Given: A correct guess for an active game
        When: Submitting the guess
        Then: Should mark synonym as found and return success
        """
        # Start a game
        response = self.agent.start_new_game()
        session_id = response.session_id
        
        # Get the session and find a valid synonym from the target word
        session = self.agent.sessions[session_id]
        target_word = session.target_word
        
        # Use a known synonym based on the target word
        # This is a bit of a hack, but we need to know what synonyms are valid
        # for the target word that was generated
        known_synonyms = {
            "happy": ["joyful", "cheerful", "glad", "pleased"],
            "fast": ["quick", "rapid", "swift", "speedy"],
            "big": ["large", "huge", "enormous", "massive"],
            "smart": ["clever", "bright", "wise", "brilliant"],
            "cold": ["chilly", "freezing", "icy", "frigid"],
            "loud": ["noisy", "booming", "thunderous", "deafening"],
            "small": ["tiny", "little", "miniature", "petite"],
            "beautiful": ["gorgeous", "stunning", "lovely", "attractive"]
        }
        
        # Get a valid synonym for the target word
        valid_synonyms = known_synonyms.get(target_word, [])
        assert len(valid_synonyms) > 0, f"No known synonyms for target word: {target_word}"
        
        first_synonym = valid_synonyms[0]
        
        # Submit correct guess
        request = GuessRequest(session_id=session_id, guess=first_synonym)
        guess_response = self.agent.submit_guess(request)
        
        assert guess_response.success is True
        assert first_synonym.lower() in guess_response.message.lower()
        assert guess_response.game_state["guessCount"] == 1
    
    def test_submit_guess_incorrect(self):
        """
        Given: An incorrect guess for an active game
        When: Submitting the guess
        Then: Should return failure with hint
        """
        # Start a game
        response = self.agent.start_new_game()
        session_id = response.session_id
        
        # Submit incorrect guess
        request = GuessRequest(session_id=session_id, guess="wrong")
        guess_response = self.agent.submit_guess(request)
        
        assert guess_response.success is False
        assert "not a synonym" in guess_response.message
        assert guess_response.hint is not None
        assert len(guess_response.hint) > 0
        assert guess_response.game_state["guessCount"] == 1
    
    def test_submit_guess_duplicate(self):
        """
        Given: A duplicate guess
        When: Submitting the same guess twice
        Then: Should reject with appropriate message
        """
        # Start a game
        response = self.agent.start_new_game()
        session_id = response.session_id
        
        # Submit first guess
        request = GuessRequest(session_id=session_id, guess="wrong")
        self.agent.submit_guess(request)
        
        # Submit same guess again
        request = GuessRequest(session_id=session_id, guess="wrong")
        guess_response = self.agent.submit_guess(request)
        
        assert guess_response.success is False
        assert "already guessed" in guess_response.message
        assert guess_response.game_state["guessCount"] == 2  # Count still increments
    
    def test_give_up_functionality(self):
        """
        Given: An active game session
        When: Giving up the game
        Then: Should reveal all synonyms and mark game as given up
        """
        # Start a game
        response = self.agent.start_new_game()
        session_id = response.session_id
        
        # Give up
        give_up_response = self.agent.give_up(session_id)
        
        assert "Game ended" in give_up_response.message
        assert give_up_response.game_state["status"] == "given-up"
        
        # All synonyms should be revealed
        synonyms = give_up_response.game_state["synonyms"]
        for syn in synonyms:
            assert syn["word"] is not None
            assert syn["found"] is True
    
    def test_invalid_session_id(self):
        """
        Given: An invalid session ID
        When: Submitting a guess
        Then: Should return error
        """
        request = GuessRequest(session_id="invalid-id", guess="test")
        response = self.agent.submit_guess(request)
        
        assert response.success is False
        assert "Session not found" in response.message
    
    def test_request_hint_analysis(self):
        """
        Given: An incorrect guess
        When: Requesting hint analysis
        Then: Should return helpful hint text
        """
        hint = self.agent.request_hint_analysis("sad", "happy")
        
        assert isinstance(hint, str)
        assert len(hint) > 0
        assert "sad" in hint
        assert "happy" in hint
    
    def test_request_hint_target_word_guess(self):
        """
        Given: Target word submitted as guess
        When: Requesting hint analysis
        Then: Should return specific feedback about not using target word
        """
        hint = self.agent.request_hint_analysis("happy", "happy")
        
        assert "can't use the target word" in hint.lower()
        assert "happy" in hint
    
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20),
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20)
    )
    def test_property_6_agent_communication_round_trip(self, guess, target_word):
        """
        Feature: synonym-seeker, Property 6: Agent Communication Round-Trip
        For any incorrect guess, the Game Builder SHALL successfully send the guess 
        to the Hint Provider and receive structured feedback within a reasonable timeout.
        """
        # Given: Any incorrect guess and target word
        # When: Requesting hint analysis (with fallback behavior)
        hint = self.agent.request_hint_analysis(guess, target_word)
        
        # Then: Should receive structured feedback
        assert isinstance(hint, str)
        assert len(hint) > 0
        
        # Should contain contextual information about the guess or target word
        hint_lower = hint.lower()
        guess_lower = guess.lower()
        target_lower = target_word.lower()
        
        # Hint should reference either the guess or target word for context
        assert (guess_lower in hint_lower or target_lower in hint_lower), \
            f"Hint should reference guess '{guess}' or target '{target_word}' for context"
        
        # Should be reasonable length (not too short or too long)
        assert 10 <= len(hint) <= 200, f"Hint length {len(hint)} should be between 10-200 characters"
        
        # Should not contain error messages indicating communication failure
        error_indicators = ["error", "failed", "timeout", "unavailable", "exception"]
        for indicator in error_indicators:
            assert indicator not in hint_lower, f"Hint should not contain error indicator: {indicator}"
    
    @patch.dict(os.environ, {'HINT_PROVIDER_A2A_URL': 'http://localhost:9001'})
    @patch('src.game_builder_agent.asyncio.run')
    def test_a2a_communication_with_mock(self, mock_asyncio_run):
        """
        Given: A2A communication is configured
        When: Requesting hint analysis
        Then: Should attempt A2A communication and handle responses
        """
        # Mock successful A2A response
        mock_asyncio_run.return_value = "Great guess! Try thinking of words that express joy."
        
        hint = self.agent.request_hint_analysis("sad", "happy")
        
        # Should have attempted A2A communication
        mock_asyncio_run.assert_called_once()
        assert hint == "Great guess! Try thinking of words that express joy."
    
    @patch.dict(os.environ, {'HINT_PROVIDER_A2A_URL': 'http://localhost:9001'})
    @patch('src.game_builder_agent.asyncio.run')
    def test_a2a_communication_fallback(self, mock_asyncio_run):
        """
        Given: A2A communication fails
        When: Requesting hint analysis
        Then: Should fallback to basic hint generation
        """
        # Mock A2A communication failure
        mock_asyncio_run.side_effect = Exception("Connection failed")
        
        hint = self.agent.request_hint_analysis("sad", "happy")
        
        # Should have attempted A2A communication
        mock_asyncio_run.assert_called_once()
        
        # Should fallback to basic hint
        assert isinstance(hint, str)
        assert len(hint) > 0
        assert "sad" in hint or "happy" in hint