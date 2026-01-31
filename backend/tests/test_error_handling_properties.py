"""Property-based tests for error handling and service failure resilience."""

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock, patch
import json
import uuid
from src.game_builder_agent import GameBuilderAgent
from src.hint_provider_agent import HintProviderAgent
from src.models import GameSession, SynonymSlot, GameStatus, GuessRequest


class TestErrorHandlingProperties:
    """Property-based tests for error handling scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.game_builder = GameBuilderAgent()
        self.hint_provider = HintProviderAgent()
    
    @given(st.integers(min_value=1, max_value=10))
    def test_property_16_service_failure_resilience_word_generation(self, failure_count):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any external service failure during word generation, the system SHALL handle 
        the failure gracefully and maintain system stability.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: External API failures occur
        with patch.object(self.game_builder, '_generate_from_external_api') as mock_external:
            # Simulate API failures
            mock_external.side_effect = Exception("External API unavailable")
            
            # When: Starting a new game despite API failures
            response = self.game_builder.start_new_game()
            
            # Then: System should handle failure gracefully
            assert response is not None
            assert hasattr(response, 'session_id')
            assert hasattr(response, 'target_word')
            assert hasattr(response, 'synonym_slots')
            assert response.target_word is not None
            assert len(response.synonym_slots) == 4
            
            # System should maintain stability
            assert response.session_id in self.game_builder.sessions
            session = self.game_builder.sessions[response.session_id]
            assert session.status == GameStatus.ACTIVE
    
    @given(st.text(min_size=1, max_size=20).filter(lambda x: x.strip() and x.isalpha()))
    def test_property_16_service_failure_resilience_hint_generation(self, guess):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any agent communication failure during hint generation, the system SHALL 
        provide fallback behavior and continue operation.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: A game session exists
        response = self.game_builder.start_new_game()
        session_id = response.session_id
        target_word = response.target_word
        
        # And: Agent communication fails
        with patch.object(self.game_builder, '_try_a2a_communication') as mock_a2a:
            with patch.object(self.game_builder, '_try_direct_http_communication') as mock_http:
                mock_a2a.side_effect = Exception("A2A communication failed")
                mock_http.side_effect = Exception("HTTP communication failed")
                
                # When: Requesting hint analysis despite communication failures
                hint = self.game_builder.request_hint_analysis(guess, target_word)
                
                # Then: System should provide fallback hint
                assert hint is not None
                assert isinstance(hint, str)
                assert len(hint.strip()) > 0
                
                # Hint should be helpful and not expose errors
                assert "error" not in hint.lower()
                assert "failed" not in hint.lower()
                assert "exception" not in hint.lower()
                
                # Should mention the guess and target word appropriately
                assert any(word in hint.lower() for word in [guess.lower(), target_word.lower()])
    
    @given(st.text(min_size=1, max_size=50))
    def test_property_16_service_failure_resilience_invalid_sessions(self, invalid_session_id):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any invalid or corrupted session, the system SHALL handle the error gracefully 
        without exposing internal details.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: An invalid session ID
        assume(invalid_session_id not in self.game_builder.sessions)
        
        # When: Attempting to submit a guess with invalid session
        request = GuessRequest(session_id=invalid_session_id, guess="test")
        response = self.game_builder.submit_guess(request)
        
        # Then: System should handle gracefully
        assert response is not None
        assert hasattr(response, 'success')
        assert response.success is False
        assert hasattr(response, 'message')
        assert isinstance(response.message, str)
        
        # Error message should be user-friendly, not technical
        message_lower = response.message.lower()
        assert "session" in message_lower
        assert "not found" in message_lower or "invalid" in message_lower
        
        # Should not expose internal details
        assert "exception" not in message_lower
        assert "error" not in message_lower or "session" in message_lower
        assert "traceback" not in message_lower
        assert "internal" not in message_lower
    
    @given(st.text(min_size=1, max_size=100))
    def test_property_16_service_failure_resilience_malformed_input(self, malformed_input):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any malformed or malicious input, the system SHALL sanitize and validate 
        input gracefully without system failure.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: A valid game session
        response = self.game_builder.start_new_game()
        session_id = response.session_id
        
        # When: Submitting malformed input
        try:
            request = GuessRequest(session_id=session_id, guess=malformed_input)
            response = self.game_builder.submit_guess(request)
            
            # Then: System should handle gracefully
            assert response is not None
            assert hasattr(response, 'success')
            assert hasattr(response, 'message')
            assert isinstance(response.message, str)
            
            # Should not crash or expose internal errors
            if not response.success:
                # Error messages should be user-friendly
                message_lower = response.message.lower()
                # Accept various types of validation messages
                assert any(keyword in message_lower for keyword in [
                    "invalid", "please", "enter", "word", "letters", "characters", 
                    "synonym", "not", "guess", "try"
                ])
                
                # Should not expose technical details
                assert "exception" not in message_lower
                assert "traceback" not in message_lower
                assert "internal" not in message_lower
            
        except Exception as e:
            # If validation raises exception, it should be a ValueError with clear message
            assert isinstance(e, ValueError)
            assert len(str(e)) > 0
            assert "internal" not in str(e).lower()
    
    @given(st.integers(min_value=1, max_value=5))
    def test_property_16_service_failure_resilience_session_corruption(self, corruption_type):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any session corruption or data integrity issues, the system SHALL recover 
        gracefully or provide appropriate error handling.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: A valid game session
        response = self.game_builder.start_new_game()
        session_id = response.session_id
        session = self.game_builder.sessions[session_id]
        
        # When: Session gets corrupted in various ways
        if corruption_type == 1:
            # Remove target word
            session.target_word = None
        elif corruption_type == 2:
            # Remove synonyms
            session.synonyms = None
        elif corruption_type == 3:
            # Corrupt synonym count
            session.synonyms = session.synonyms[:2]  # Wrong count
        elif corruption_type == 4:
            # Remove actual synonyms
            if hasattr(session, '_actual_synonyms'):
                delattr(session, '_actual_synonyms')
        elif corruption_type == 5:
            # Corrupt status
            session.status = None
        
        # Then: System should handle corruption gracefully
        request = GuessRequest(session_id=session_id, guess="test")
        response = self.game_builder.submit_guess(request)
        
        # Should either recover or provide clear error
        assert response is not None
        assert hasattr(response, 'success')
        assert hasattr(response, 'message')
        
        if not response.success:
            # Error message should be helpful
            message_lower = response.message.lower()
            # Accept various types of error messages
            assert any(keyword in message_lower for keyword in [
                "session", "game", "start", "new", "error", "try", "occurred", "processing",
                "not", "synonym", "word"  # Also accept normal game messages
            ])
            
            # Should not expose technical corruption details
            assert "none" not in message_lower
            assert "null" not in message_lower
            assert "corruption" not in message_lower
        else:
            # If system handles corruption gracefully and continues working, that's also valid
            # Just ensure the response is reasonable
            assert isinstance(response.message, str)
            assert len(response.message.strip()) > 0
    
    @given(st.integers(min_value=0, max_value=3))
    def test_property_16_service_failure_resilience_concurrent_access(self, access_pattern):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any concurrent access patterns, the system SHALL maintain session independence 
        and data integrity.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: Multiple concurrent sessions
        sessions = []
        for i in range(3):
            response = self.game_builder.start_new_game()
            sessions.append({
                'id': response.session_id,
                'target_word': response.target_word,
                'response': response
            })
        
        # When: Performing operations on different sessions
        if access_pattern == 0:
            # Submit guess to first session
            request = GuessRequest(session_id=sessions[0]['id'], guess="test")
            response1 = self.game_builder.submit_guess(request)
            
            # Submit different guess to second session
            request = GuessRequest(session_id=sessions[1]['id'], guess="word")
            response2 = self.game_builder.submit_guess(request)
            
        elif access_pattern == 1:
            # Give up first session
            response1 = self.game_builder.give_up(sessions[0]['id'])
            
            # Continue playing second session
            request = GuessRequest(session_id=sessions[1]['id'], guess="test")
            response2 = self.game_builder.submit_guess(request)
            
        elif access_pattern == 2:
            # Corrupt one session and access another
            corrupt_session = self.game_builder.sessions[sessions[0]['id']]
            corrupt_session.target_word = None
            
            # Access different session
            request = GuessRequest(session_id=sessions[1]['id'], guess="test")
            response2 = self.game_builder.submit_guess(request)
            
        elif access_pattern == 3:
            # Delete one session and access another
            del self.game_builder.sessions[sessions[0]['id']]
            
            # Access remaining session
            request = GuessRequest(session_id=sessions[1]['id'], guess="test")
            response2 = self.game_builder.submit_guess(request)
        
        # Then: Other sessions should remain unaffected
        for i, session_info in enumerate(sessions[1:], 1):  # Skip first session
            session_id = session_info['id']
            
            # Session should still exist (unless we deleted it specifically)
            if access_pattern != 3 or i != 0:
                assert session_id in self.game_builder.sessions
                
                # Session data should be intact
                session = self.game_builder.sessions[session_id]
                assert session.target_word == session_info['target_word']
                assert len(session.synonyms) == 4
                assert session.status == GameStatus.ACTIVE
    
    @given(st.text(min_size=1, max_size=20).filter(lambda x: x.strip() and x.isalpha()))
    def test_property_16_service_failure_resilience_hint_provider_errors(self, guess):
        """
        Feature: synonym-seeker, Property 16: Service Failure Resilience
        For any errors in hint provider analysis, the system SHALL provide fallback 
        behavior without exposing internal errors.
        **Validates: Requirements 6.4, 9.4**
        """
        # Given: Hint provider methods that may fail
        target_word = "happy"
        
        # When: Various hint provider methods encounter errors
        with patch.object(self.hint_provider, 'analyze_guess_relationship') as mock_analyze:
            with patch.object(self.hint_provider, 'detect_misspelling') as mock_detect:
                with patch.object(self.hint_provider, 'generate_contextual_hint') as mock_generate:
                    
                    # Simulate different types of failures
                    mock_analyze.side_effect = Exception("Analysis service down")
                    mock_detect.side_effect = Exception("Detection service error")
                    mock_generate.side_effect = Exception("Generation service failed")
                    
                    # Then: Should handle gracefully
                    try:
                        from src.models import HintRequest
                        request = HintRequest(
                            guess=guess,
                            target_word=target_word,
                            previous_guesses=[]
                        )
                        response = self.hint_provider.analyze_hint_request(request)
                        
                        # Should provide some response even if services fail
                        assert response is not None
                        assert hasattr(response, 'hint_text')
                        assert isinstance(response.hint_text, str)
                        
                        # Should not expose error details
                        hint_lower = response.hint_text.lower()
                        assert "exception" not in hint_lower
                        assert "service down" not in hint_lower
                        assert "error" not in hint_lower or "try" in hint_lower
                        
                    except Exception as e:
                        # If it does raise an exception, it should be handled gracefully
                        # by the calling code (game builder agent)
                        assert isinstance(e, (ValueError, RuntimeError))
                        assert "internal" not in str(e).lower()