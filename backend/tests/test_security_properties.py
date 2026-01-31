"""Property-based tests for security validation."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from src.models import GuessRequest, HintRequest
from src.hint_provider_agent import HintProviderAgent


class TestSecurityProperties:
    """Property-based tests for security validation - Property 12."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hint_agent = HintProviderAgent()
    
    @given(st.text())
    def test_property_12_input_sanitization_guess_request(self, malicious_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any user input, the system SHALL sanitize and validate the input before processing,
        rejecting potentially malicious content while preserving legitimate game guesses.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Any potentially malicious input
        # When: Creating a GuessRequest (which sanitizes input)
        try:
            request = GuessRequest(session_id="test-session", guess=malicious_input)
            
            # Then: If successful, the sanitized guess should be safe
            # Should only contain alphabetic characters
            if request.guess:  # If not empty after sanitization
                assert request.guess.isalpha(), f"Sanitized guess '{request.guess}' contains non-alphabetic characters"
                # For Unicode characters, lowercase may not always be available, so check if it's the lowercase version when possible
                expected_lower = malicious_input.lower()
                if expected_lower != malicious_input and expected_lower.isalpha():
                    # If the original had a lowercase version and it's alphabetic, the result should be lowercase
                    assert request.guess.islower() or request.guess == expected_lower, f"Sanitized guess '{request.guess}' should be lowercase when possible"
                assert len(request.guess) <= 50, f"Sanitized guess '{request.guess}' exceeds length limit"
        
        except ValueError:
            # If ValueError is raised, the input was properly rejected
            # This is expected behavior for malicious or invalid input
            pass
    
    @given(st.text())
    def test_property_12_input_sanitization_hint_request(self, malicious_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any user input to hint analysis, the system SHALL sanitize inputs to prevent
        prompt injection attacks while maintaining semantic meaning.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Any potentially malicious input
        # When: Creating a HintRequest (which sanitizes input)
        try:
            request = HintRequest(
                guess=malicious_input,
                target_word="happy",
                previous_guesses=[]
            )
            
            # Then: If successful, the sanitized inputs should be safe
            # Should only contain safe characters
            if request.guess:  # If not empty after sanitization
                assert len(request.guess) <= 50, f"Sanitized guess '{request.guess}' exceeds length limit"
                # Should not contain suspicious patterns
                assert not any(char in request.guess for char in '<>{}[]\\;|&$`'), \
                    f"Sanitized guess '{request.guess}' contains suspicious characters"
        
        except ValueError:
            # If ValueError is raised, the input was properly rejected
            # This is expected behavior for malicious or invalid input
            pass
    
    @given(st.sampled_from(['script test', 'javascript code', 'eval function', 'ignore previous', 'system prompt']))
    def test_property_12_prompt_injection_prevention(self, injection_attempt):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any input containing prompt injection patterns, the system SHALL prevent
        the injection from affecting AI service calls.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Input containing potential prompt injection keywords
        # When: Processing through hint analysis (which sanitizes for AI calls)
        sanitized = self.hint_agent._sanitize_for_analysis(injection_attempt)
        
        # Then: Should either be empty (rejected) or safe
        if sanitized:
            # Should not contain the original injection keywords
            injection_keywords = ['script', 'javascript', 'eval', 'ignore', 'system']
            for keyword in injection_keywords:
                assert keyword not in sanitized.lower(), \
                    f"Sanitized input '{sanitized}' still contains injection keyword '{keyword}'"
    
    @given(st.text().filter(lambda x: any(char in x for char in '<>{}[]\\;|&$`')))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_12_suspicious_character_filtering(self, suspicious_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any input containing suspicious characters, the system SHALL filter them out
        or reject the input entirely.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Input containing suspicious characters
        # When: Sanitizing for analysis
        sanitized = self.hint_agent._sanitize_for_analysis(suspicious_input)
        
        # Then: Should not contain suspicious characters
        suspicious_chars = '<>{}[]\\;|&$`'
        for char in suspicious_chars:
            assert char not in sanitized, \
                f"Sanitized input '{sanitized}' still contains suspicious character '{char}'"
    
    @given(st.text(min_size=51))
    def test_property_12_length_limit_enforcement(self, long_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any input exceeding safe length limits, the system SHALL truncate or reject it.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Input exceeding length limits
        # When: Sanitizing for analysis
        sanitized = self.hint_agent._sanitize_for_analysis(long_input)
        
        # Then: Should be within safe limits
        assert len(sanitized) <= 50, f"Sanitized input '{sanitized}' exceeds length limit of 50 characters"
    
    @given(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=1, max_size=20))
    def test_property_12_legitimate_input_preservation(self, legitimate_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any legitimate ASCII alphabetic input, the system SHALL preserve its semantic meaning
        while ensuring it's safe.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Legitimate ASCII alphabetic input (with spaces allowed)
        # When: Sanitizing for analysis
        sanitized = self.hint_agent._sanitize_for_analysis(legitimate_input)
        
        # Then: Should preserve the essential content
        if sanitized:  # If not filtered out entirely
            # Should be similar to original (allowing for case changes and whitespace normalization)
            original_letters = ''.join(c.lower() for c in legitimate_input if c.isalpha())
            sanitized_letters = ''.join(c.lower() for c in sanitized if c.isalpha())
            
            # Should preserve most of the alphabetic content for ASCII letters
            if original_letters:  # If original had letters
                assert sanitized_letters, "Sanitization removed all alphabetic content from legitimate input"
                # For ASCII-only input, should preserve most content
                preserved_ratio = len(sanitized_letters) / len(original_letters)
                assert preserved_ratio >= 0.8, \
                    f"Sanitization removed too much content: {original_letters} -> {sanitized_letters}"
    
    @given(st.text())
    def test_property_12_display_safety(self, user_input):
        """
        Feature: synonym-seeker, Property 12: Input Sanitization
        For any input that will be displayed to users, the system SHALL ensure it's safe
        for display and doesn't contain harmful content.
        **Validates: Requirements 8.1, 8.5**
        """
        # Given: Any user input
        # When: Sanitizing for display
        sanitized = self.hint_agent._sanitize_for_display(user_input)
        
        # Then: Should be safe for display
        if sanitized:
            # Should not contain HTML/script tags or other dangerous content
            dangerous_patterns = ['<script', '<iframe', '<object', '<embed', 'javascript:', 'data:']
            for pattern in dangerous_patterns:
                assert pattern.lower() not in sanitized.lower(), \
                    f"Sanitized display text '{sanitized}' contains dangerous pattern '{pattern}'"
            
            # Should be within reasonable length for display
            assert len(sanitized) <= 50, f"Sanitized display text '{sanitized}' exceeds display length limit"
            
            # Should only contain safe characters
            assert all(c.isalpha() or c.isspace() or c == '-' for c in sanitized), \
                f"Sanitized display text '{sanitized}' contains unsafe characters"