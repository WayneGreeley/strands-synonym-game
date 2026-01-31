"""Property-based tests for input validation."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from src.models import GuessRequest


class TestInputValidationProperties:
    """Property-based tests for input validation - Property 5."""
    
    @given(st.text().filter(lambda x: ' ' in x.strip() and x.strip() and len(x) <= 50 and any(c.isalpha() for c in x)))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_5_input_validation_multi_word_rejection(self, input_text):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input containing multiple words, the system SHALL reject the input
        and prompt for valid single-word input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input text that contains multiple words (spaces)
        # When: Creating a GuessRequest with multi-word input
        # Then: Should raise ValueError for multiple words
        with pytest.raises(ValueError, match="Please enter only one word"):
            GuessRequest(session_id="test-session", guess=input_text)
    
    @given(st.text(min_size=51).filter(lambda x: ' ' not in x.strip()))
    def test_property_5_input_validation_length_limits(self, long_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input exceeding reasonable length, the system SHALL reject the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input text longer than 50 characters without spaces
        # When: Creating a GuessRequest with long input
        # Then: Should raise ValueError for excessive length
        with pytest.raises(ValueError, match="Input too long \\(maximum 50 characters\\)"):
            GuessRequest(session_id="test-session", guess=long_input)
    
    @given(st.text().filter(lambda x: not x.strip()))
    def test_property_5_input_validation_empty_input(self, empty_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any empty input, the system SHALL reject the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Empty or whitespace-only input
        # When: Creating a GuessRequest with empty input
        # Then: Should raise ValueError for empty input
        with pytest.raises(ValueError, match="Guess cannot be empty"):
            GuessRequest(session_id="test-session", guess=empty_input)
    
    @given(st.text().filter(lambda x: x and x.strip() and not any(c.isalpha() for c in x) and len(x) <= 50 and ' ' not in x and not any(c in x for c in '<>{}[]\\;|&$`')))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_5_input_validation_no_letters(self, no_letters_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input with no alphabetic characters, the system SHALL reject the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input with no alphabetic characters, not too long, no spaces, not empty after strip, no suspicious chars
        # When: Creating a GuessRequest
        # Then: Should raise ValueError for no letters
        with pytest.raises(ValueError, match="Guess must contain at least one letter"):
            GuessRequest(session_id="test-session", guess=no_letters_input)
    
    @given(st.text().filter(lambda x: any(c in x for c in '<>{}[]\\;|&$`') and len(x) <= 50 and ' ' not in x and any(c.isalpha() for c in x)))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_5_input_validation_suspicious_characters(self, suspicious_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input containing suspicious patterns, the system SHALL reject the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input containing suspicious characters, not too long, no spaces, has letters
        # When: Creating a GuessRequest
        # Then: Should raise ValueError for invalid characters
        with pytest.raises(ValueError, match="Invalid characters detected in input"):
            GuessRequest(session_id="test-session", guess=suspicious_input)
    
    @given(st.sampled_from(['script', 'javascript', 'eval', 'function', 'select', 'insert', 'update', 'delete', 'drop']))
    def test_property_5_input_validation_injection_keywords(self, injection_keyword):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input containing injection-related keywords, the system SHALL reject the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input containing specific injection keywords
        # When: Creating a GuessRequest
        # Then: Should raise ValueError for invalid characters
        with pytest.raises(ValueError, match="Invalid characters detected in input"):
            GuessRequest(session_id="test-session", guess=injection_keyword)
    
    @given(st.text(alphabet=st.characters(whitelist_categories=['Lu', 'Ll']), min_size=1, max_size=50).filter(lambda x: ' ' not in x))
    def test_property_5_input_validation_valid_inputs_accepted(self, valid_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any valid single-word alphabetic input, the system SHALL accept the input.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Valid single-word input with only Unicode letters, no spaces
        # When: Creating a GuessRequest
        # Then: Should succeed without raising an exception
        request = GuessRequest(session_id="test-session", guess=valid_input)
        
        # Verify the guess was sanitized properly (letters only)
        assert request.guess.isalpha()
        assert len(request.guess) > 0
        assert len(request.guess) <= 50
        # The sanitized guess should be derived from the original input
        assert len(request.guess) <= len(valid_input)  # Should not be longer than original
    
    @given(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', min_size=1, max_size=50))
    def test_property_5_input_validation_ascii_alphabetic_accepted(self, alphabetic_input):
        """
        Feature: synonym-seeker, Property 5: Input Validation
        For any input containing only ASCII alphabetic characters, the system SHALL accept it.
        **Validates: Requirements 2.5, 9.2, 9.3**
        """
        # Given: Input with only ASCII alphabetic characters
        # When: Creating a GuessRequest
        # Then: Should succeed
        request = GuessRequest(session_id="test-session", guess=alphabetic_input)
        
        # Verify sanitization
        assert request.guess.isalpha()
        assert request.guess.islower()
        assert len(request.guess) > 0
        assert len(request.guess) <= 50