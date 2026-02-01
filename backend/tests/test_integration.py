"""Integration tests for SynonymSeeker multi-agent system."""

import pytest
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.game_builder_agent import GameBuilderAgent
from src.hint_provider_agent import HintProviderAgent
from src.models import GuessRequest, GameStatus


class TestCompleteGameFlows:
    """Test complete game flows from start to finish."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.game_builder = GameBuilderAgent()
        self.hint_provider = HintProviderAgent()
    
    def test_complete_successful_game_flow(self):
        """
        Given: A new game session
        When: Playing through a complete successful game
        Then: Should progress through all states correctly
        """
        # Given: Start a new game
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        target_word = start_response.target_word
        
        assert start_response.status == "active"
        assert len(start_response.synonym_slots) == 4
        
        # Get the session to access actual synonyms for testing
        session = self.game_builder.sessions[session_id]
        actual_synonyms = session._actual_synonyms
        
        # When: Submitting correct guesses for all synonyms
        correct_guesses = 0
        for synonym in actual_synonyms:
            request = GuessRequest(session_id=session_id, guess=synonym)
            response = self.game_builder.submit_guess(request)
            
            # Then: Each correct guess should be accepted
            assert response.success is True
            assert synonym.lower() in response.message.lower()
            correct_guesses += 1
            
            # Game state should update correctly
            game_state = response.game_state
            assert game_state["guessCount"] == correct_guesses
            
            # Check if game is complete
            if correct_guesses == 4:
                assert game_state["status"] == "completed"
                # All synonyms should be found
                for slot in game_state["synonyms"]:
                    assert slot["found"] is True
                    assert slot["word"] is not None
            else:
                assert game_state["status"] == "active"
    
    def test_complete_game_flow_with_incorrect_guesses(self):
        """
        Given: A new game session
        When: Playing with mix of correct and incorrect guesses
        Then: Should handle both types correctly and provide hints
        """
        # Given: Start a new game
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        session = self.game_builder.sessions[session_id]
        actual_synonyms = session._actual_synonyms
        
        # When: Submit some incorrect guesses first
        incorrect_guesses = ["wrong", "bad", "terrible"]
        for guess in incorrect_guesses:
            request = GuessRequest(session_id=session_id, guess=guess)
            response = self.game_builder.submit_guess(request)
            
            # Then: Should be rejected with hints
            assert response.success is False
            assert "not a synonym" in response.message
            assert response.hint is not None
            assert len(response.hint) > 0
        
        # When: Submit correct guesses
        for synonym in actual_synonyms:
            request = GuessRequest(session_id=session_id, guess=synonym)
            response = self.game_builder.submit_guess(request)
            
            # Then: Should be accepted
            assert response.success is True
        
        # Final state should be completed
        final_state = response.game_state
        assert final_state["status"] == "completed"
        assert final_state["guessCount"] == len(incorrect_guesses) + len(actual_synonyms)
    
    def test_give_up_flow(self):
        """
        Given: An active game session
        When: Player gives up
        Then: Should reveal all synonyms and end game
        """
        # Given: Start a new game and make some guesses
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        # Make a few incorrect guesses
        for guess in ["wrong", "bad"]:
            request = GuessRequest(session_id=session_id, guess=guess)
            self.game_builder.submit_guess(request)
        
        # When: Give up
        give_up_response = self.game_builder.give_up(session_id)
        
        # Then: Should reveal all synonyms
        assert "Game ended" in give_up_response.message
        game_state = give_up_response.game_state
        assert game_state["status"] == "given-up"
        
        # All synonyms should be revealed
        for slot in game_state["synonyms"]:
            assert slot["word"] is not None
            assert slot["found"] is True
    
    def test_duplicate_guess_handling_in_complete_flow(self):
        """
        Given: An active game session
        When: Submitting duplicate guesses during gameplay
        Then: Should handle duplicates correctly while maintaining game flow
        """
        # Given: Start a new game
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        # When: Submit a guess twice
        request = GuessRequest(session_id=session_id, guess="wrong")
        first_response = self.game_builder.submit_guess(request)
        second_response = self.game_builder.submit_guess(request)
        
        # Then: First should be processed normally, second should be duplicate
        assert first_response.success is False
        assert "not a synonym" in first_response.message
        
        assert second_response.success is False
        assert "already guessed" in second_response.message
        
        # Guess count should increment for both
        assert second_response.game_state["guessCount"] == 2


class TestConcurrentSessionHandling:
    """Test concurrent session handling and independence."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.game_builder = GameBuilderAgent()
    
    def test_concurrent_session_independence(self):
        """
        Given: Multiple concurrent game sessions
        When: Operating on different sessions simultaneously
        Then: Sessions should remain independent
        """
        # Given: Start multiple game sessions
        num_sessions = 5
        sessions = []
        
        for i in range(num_sessions):
            response = self.game_builder.start_new_game()
            sessions.append({
                'id': response.session_id,
                'target_word': response.target_word,
                'synonyms': self.game_builder.sessions[response.session_id]._actual_synonyms
            })
        
        # When: Make different guesses in each session concurrently
        def make_guess_in_session(session_data, guess):
            request = GuessRequest(session_id=session_data['id'], guess=guess)
            return self.game_builder.submit_guess(request)
        
        # Submit different guesses to each session
        with ThreadPoolExecutor(max_workers=num_sessions) as executor:
            futures = []
            for i, session in enumerate(sessions):
                # Use first synonym for even sessions, incorrect guess for odd
                if i % 2 == 0:
                    guess = session['synonyms'][0]
                else:
                    guess = f"wrong{i}"
                
                future = executor.submit(make_guess_in_session, session, guess)
                futures.append((future, session, guess, i % 2 == 0))
            
            # Then: Collect results and verify independence
            for future, session, guess, should_succeed in futures:
                response = future.result()
                
                if should_succeed:
                    assert response.success is True
                    assert guess.lower() in response.message.lower()
                else:
                    assert response.success is False
                    assert "not a synonym" in response.message
                
                # Verify session state is correct
                assert response.game_state["guessCount"] == 1
    
    def test_concurrent_operations_on_same_session(self):
        """
        Given: A single game session
        When: Multiple concurrent operations on the same session
        Then: Should handle operations safely without corruption
        """
        # Given: Start a single game session
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        # When: Submit multiple concurrent guesses to the same session
        num_concurrent_guesses = 10
        guesses = [f"guess{i}" for i in range(num_concurrent_guesses)]
        
        def submit_guess(guess):
            request = GuessRequest(session_id=session_id, guess=guess)
            return self.game_builder.submit_guess(request)
        
        with ThreadPoolExecutor(max_workers=num_concurrent_guesses) as executor:
            futures = [executor.submit(submit_guess, guess) for guess in guesses]
            responses = [future.result() for future in as_completed(futures)]
        
        # Then: All guesses should be processed
        assert len(responses) == num_concurrent_guesses
        
        # Find the response with the highest guess count (final state)
        final_response = max(responses, key=lambda r: r.game_state["guessCount"])
        assert final_response.game_state["guessCount"] == num_concurrent_guesses
        
        # Session should still be active (all guesses were incorrect)
        assert final_response.game_state["status"] == "active"
    
    def test_session_isolation_with_different_target_words(self):
        """
        Given: Multiple sessions with different target words
        When: Making guesses across sessions
        Then: Each session should validate against its own target word
        """
        # Given: Start multiple sessions
        sessions = []
        for _ in range(3):
            response = self.game_builder.start_new_game()
            sessions.append({
                'id': response.session_id,
                'target_word': response.target_word,
                'synonyms': self.game_builder.sessions[response.session_id]._actual_synonyms
            })
        
        # Ensure we have different target words (retry if needed)
        target_words = [s['target_word'] for s in sessions]
        if len(set(target_words)) < 2:
            # Add more sessions until we get different target words
            for _ in range(5):
                response = self.game_builder.start_new_game()
                new_target = response.target_word
                if new_target not in target_words:
                    sessions.append({
                        'id': response.session_id,
                        'target_word': new_target,
                        'synonyms': self.game_builder.sessions[response.session_id]._actual_synonyms
                    })
                    break
        
        # When: Use synonyms from one session in another session
        if len(sessions) >= 2:
            session_a = sessions[0]
            session_b = sessions[1]
            
            # Use session A's synonym in session B
            synonym_from_a = session_a['synonyms'][0]
            request = GuessRequest(session_id=session_b['id'], guess=synonym_from_a)
            response = self.game_builder.submit_guess(request)
            
            # Then: Should be rejected if target words are different
            if session_a['target_word'] != session_b['target_word']:
                assert response.success is False
                assert "not a synonym" in response.message


class TestExternalServiceIntegration:
    """Test integration with external services and A2A communication."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.game_builder = GameBuilderAgent()
        self.hint_provider = HintProviderAgent()
    
    def test_hint_provider_integration(self):
        """
        Given: Game Builder and Hint Provider agents
        When: Requesting hint analysis for incorrect guesses
        Then: Should receive structured feedback
        """
        # Given: Various incorrect guesses and target words
        test_cases = [
            ("sad", "happy"),      # Related emotion
            ("car", "happy"),      # Unrelated
            ("joyfull", "happy"),  # Misspelling
            ("happy", "happy"),    # Target word
        ]
        
        for guess, target_word in test_cases:
            # When: Requesting hint analysis
            hint = self.game_builder.request_hint_analysis(guess, target_word)
            
            # Then: Should receive meaningful feedback
            assert isinstance(hint, str)
            assert len(hint) > 10
            assert len(hint) < 200
            
            # Should contain contextual information
            hint_lower = hint.lower()
            assert (guess.lower() in hint_lower or 
                   target_word.lower() in hint_lower or
                   "word" in hint_lower or
                   "synonym" in hint_lower)
    
    @patch.dict('os.environ', {'HINT_PROVIDER_A2A_URL': 'http://localhost:9001'})
    def test_a2a_communication_integration(self):
        """
        Given: A2A communication is configured
        When: Making requests that trigger agent communication
        Then: Should handle A2A protocol correctly
        """
        # Given: Start a game and make an incorrect guess
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        # When: Submit incorrect guess (triggers A2A communication)
        request = GuessRequest(session_id=session_id, guess="wrong")
        
        # Mock A2A communication to test integration
        with patch('src.game_builder_agent.asyncio.run') as mock_asyncio:
            mock_asyncio.return_value = "This is a hint from A2A communication."
            
            response = self.game_builder.submit_guess(request)
            
            # Then: Should have attempted A2A communication
            mock_asyncio.assert_called_once()
            
            # Response should include the A2A hint
            assert response.success is False
            assert response.hint == "This is a hint from A2A communication."
    
    def test_a2a_communication_fallback_integration(self):
        """
        Given: A2A communication fails
        When: Making requests that would trigger agent communication
        Then: Should fallback gracefully to basic hints
        """
        # Given: Start a game
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        
        # When: Submit incorrect guess with A2A failure
        request = GuessRequest(session_id=session_id, guess="wrong")
        
        with patch('src.game_builder_agent.asyncio.run') as mock_asyncio:
            mock_asyncio.side_effect = Exception("A2A communication failed")
            
            response = self.game_builder.submit_guess(request)
            
            # Then: Should fallback to basic hint
            assert response.success is False
            assert response.hint is not None
            assert len(response.hint) > 0
            assert "wrong" in response.hint or "synonym" in response.hint.lower()
    
    def test_word_generation_service_integration(self):
        """
        Given: Word generation functionality
        When: Starting multiple games
        Then: Should generate valid word puzzles consistently
        """
        # When: Generate multiple word puzzles
        puzzles = []
        for _ in range(10):
            puzzle = self.game_builder.generate_word_puzzle()
            puzzles.append(puzzle)
        
        # Then: All puzzles should be valid
        for puzzle in puzzles:
            assert "target_word" in puzzle
            assert "synonyms" in puzzle
            assert len(puzzle["synonyms"]) == 4
            
            target_word = puzzle["target_word"]
            assert isinstance(target_word, str)
            assert len(target_word) > 0
            assert target_word.isalpha()
            
            # All synonyms should be distinct and valid
            synonym_words = [syn["word"] for syn in puzzle["synonyms"]]
            assert len(set(synonym_words)) == 4  # All distinct
            
            for syn_data in puzzle["synonyms"]:
                syn_word = syn_data["word"]
                letter_count = syn_data["letter_count"]
                
                assert isinstance(syn_word, str)
                assert len(syn_word) > 0
                assert syn_word.isalpha()
                assert len(syn_word) == letter_count
                assert syn_word.lower() != target_word.lower()
    
    def test_guess_validation_service_integration(self):
        """
        Given: Guess validation functionality
        When: Validating various guess types
        Then: Should handle all validation scenarios correctly
        """
        # Given: A target word and its synonyms
        target_word = "happy"
        synonyms = [
            {"word": "joyful", "letter_count": 6},
            {"word": "cheerful", "letter_count": 8},
            {"word": "glad", "letter_count": 4},
            {"word": "pleased", "letter_count": 7}
        ]
        
        # Test cases: (guess, expected_result, description)
        test_cases = [
            ("joyful", True, "exact synonym match"),
            ("JOYFUL", True, "case insensitive match"),
            ("joyfull", True, "close misspelling"),
            ("joyfl", True, "missing letter"),
            ("happy", False, "target word rejection"),
            ("sad", False, "incorrect word"),
            ("car", False, "unrelated word"),
        ]
        
        for guess, expected, description in test_cases:
            # When: Validating the guess
            result = self.game_builder.validate_guess(guess, target_word, synonyms)
            
            # Then: Should match expected result
            assert result == expected, f"Failed for {description}: guess='{guess}', expected={expected}, got={result}"


class TestEndToEndIntegration:
    """Test complete end-to-end integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create fresh agent instance for each test to ensure isolation
        self.game_builder = GameBuilderAgent()
    
    def test_full_game_with_mixed_scenarios(self):
        """
        Given: A complete game session
        When: Playing through various scenarios (correct, incorrect, duplicates, misspellings)
        Then: Should handle all scenarios correctly in sequence
        """
        # Given: Start a new game
        start_response = self.game_builder.start_new_game()
        session_id = start_response.session_id
        session = self.game_builder.sessions[session_id]
        actual_synonyms = session._actual_synonyms
        
        guess_count = 0
        
        # Scenario 1: Incorrect guesses with hints
        incorrect_guesses = ["wrong", "bad", "terrible"]
        for guess in incorrect_guesses:
            request = GuessRequest(session_id=session_id, guess=guess)
            response = self.game_builder.submit_guess(request)
            guess_count += 1
            
            assert response.success is False
            assert response.hint is not None
            assert response.game_state["guessCount"] == guess_count
            assert response.game_state["status"] == "active"
        
        # Scenario 2: Duplicate guess
        request = GuessRequest(session_id=session_id, guess="wrong")
        response = self.game_builder.submit_guess(request)
        guess_count += 1
        
        assert response.success is False
        assert "already guessed" in response.message
        assert response.game_state["guessCount"] == guess_count
        
        # Scenario 3: Misspelling of correct synonym
        first_synonym = actual_synonyms[0]
        misspelled = first_synonym + "x"  # Add extra character
        request = GuessRequest(session_id=session_id, guess=misspelled)
        response = self.game_builder.submit_guess(request)
        guess_count += 1
        
        # Should be accepted as close misspelling
        assert response.success is True
        assert response.game_state["guessCount"] == guess_count
        
        # Scenario 4: Correct guesses for remaining synonyms
        remaining_synonyms = actual_synonyms[1:]  # Skip first (already guessed via misspelling)
        for synonym in remaining_synonyms:
            request = GuessRequest(session_id=session_id, guess=synonym)
            response = self.game_builder.submit_guess(request)
            guess_count += 1
            
            assert response.success is True
            assert response.game_state["guessCount"] == guess_count
        
        # Final state should be completed
        assert response.game_state["status"] == "completed"
        
        # All synonyms should be found
        for slot in response.game_state["synonyms"]:
            assert slot["found"] is True
            assert slot["word"] is not None
    
    def test_performance_under_load(self):
        """
        Given: Multiple concurrent game sessions with high activity
        When: Performing many operations simultaneously
        Then: Should maintain performance and correctness
        """
        # Given: Start multiple sessions
        num_sessions = 10
        operations_per_session = 5
        
        def run_session_operations(session_index):
            """Run a series of operations on a single session."""
            # Start game
            start_response = self.game_builder.start_new_game()
            session_id = start_response.session_id
            
            results = []
            
            # Make several guesses
            for i in range(operations_per_session):
                guess = f"guess{session_index}_{i}"
                request = GuessRequest(session_id=session_id, guess=guess)
                response = self.game_builder.submit_guess(request)
                results.append(response)
            
            return results
        
        # When: Run operations concurrently
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_sessions) as executor:
            futures = [
                executor.submit(run_session_operations, i) 
                for i in range(num_sessions)
            ]
            all_results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        
        # Then: All operations should complete successfully
        assert len(all_results) == num_sessions
        
        for session_results in all_results:
            assert len(session_results) == operations_per_session
            
            # Each session should have correct guess count
            final_response = session_results[-1]
            assert final_response.game_state["guessCount"] == operations_per_session
        
        # Performance should be reasonable (less than 30 seconds for all operations)
        total_time = end_time - start_time
        assert total_time < 30, f"Operations took too long: {total_time:.2f} seconds"
    
    @given(st.integers(min_value=1, max_value=3))
    @settings(deadline=None)  # Disable deadline for this test
    def test_property_based_integration_flow(self, num_incorrect_guesses):
        """
        Property-based test for integration flows.
        For any number of incorrect guesses followed by correct completion,
        the game should maintain consistent state and complete successfully.
        """
        # Given: Start a new game (ensure fresh session)
        # Create a completely fresh agent instance to avoid any state pollution
        fresh_game_builder = GameBuilderAgent()
        start_response = fresh_game_builder.start_new_game()
        session_id = start_response.session_id
        session = fresh_game_builder.sessions[session_id]
        actual_synonyms = session._actual_synonyms
        
        # Ensure we have a fresh session
        assert session.guess_count == 0
        assert len(session.guessed_words) == 0
        
        # When: Make unique incorrect guesses (using only alphabetic characters)
        alphabet_suffixes = ['alpha', 'beta', 'gamma']
        for i in range(num_incorrect_guesses):
            # Use alphabetic suffixes to ensure uniqueness
            unique_guess = f"wrong{alphabet_suffixes[i]}"
            request = GuessRequest(session_id=session_id, guess=unique_guess)
            response = fresh_game_builder.submit_guess(request)
            
            # Then: Should be rejected with hints
            assert response.success is False
            # Should have hint for incorrect guesses (not duplicates)
            assert response.hint is not None, f"Expected hint for guess '{unique_guess}', got response: {response}"
            assert response.game_state["status"] == "active"
            assert response.game_state["guessCount"] == i + 1
        
        # When: Complete with correct guesses
        for j, synonym in enumerate(actual_synonyms):
            request = GuessRequest(session_id=session_id, guess=synonym)
            response = fresh_game_builder.submit_guess(request)
            
            # Then: Should be accepted
            assert response.success is True
            expected_count = num_incorrect_guesses + j + 1
            assert response.game_state["guessCount"] == expected_count
        
        # Final state should be completed
        assert response.game_state["status"] == "completed"
        
        # All synonyms should be found
        for slot in response.game_state["synonyms"]:
            assert slot["found"] is True
            assert slot["word"] is not None