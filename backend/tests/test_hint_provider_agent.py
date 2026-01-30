"""Tests for Hint Provider Agent."""

import pytest
from hypothesis import given, strategies as st
from src.hint_provider_agent import HintProviderAgent
from src.models import HintRequest, HintResponse


class TestHintProviderAgent:
    """Test Hint Provider Agent functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.agent = HintProviderAgent()
    
    def test_agent_initialization(self):
        """
        Given: HintProviderAgent initialization
        When: Creating a new agent instance
        Then: Agent should be properly configured with tools and system prompt
        """
        assert self.agent.agent is not None
        assert len(self.agent.agent.tool_names) == 3  # analyze_guess_relationship, detect_misspelling, generate_contextual_hint
    
    def test_analyze_guess_relationship_target_word(self):
        """
        Given: A guess that is the target word itself
        When: Analyzing the relationship
        Then: Should identify it as target_word type
        """
        result = self.agent.analyze_guess_relationship("happy", "happy")
        
        assert result["relationship_type"] == "target_word"
        assert result["confidence"] == 1.0
        assert "target word itself" in result["reasoning"]
    
    def test_analyze_guess_relationship_misspelling(self):
        """
        Given: A guess that is a close misspelling of a valid synonym
        When: Analyzing the relationship
        Then: Should identify it as misspelling with intended word
        """
        result = self.agent.analyze_guess_relationship("joyfull", "happy")  # Extra 'l'
        
        assert result["relationship_type"] == "misspelling"
        assert result["confidence"] == 0.9
        assert result["intended_word"] == "joyful"
    
    def test_analyze_guess_relationship_related(self):
        """
        Given: A guess that is related but not a synonym
        When: Analyzing the relationship
        Then: Should identify it as related concept
        """
        result = self.agent.analyze_guess_relationship("sad", "happy")  # Both emotions
        
        assert result["relationship_type"] == "related"
        assert result["confidence"] == 0.7
    
    def test_analyze_guess_relationship_unrelated(self):
        """
        Given: A guess that is completely unrelated
        When: Analyzing the relationship
        Then: Should identify it as unrelated
        """
        result = self.agent.analyze_guess_relationship("car", "happy")
        
        assert result["relationship_type"] == "unrelated"
        assert result["confidence"] == 0.8
    
    def test_detect_misspelling_positive(self):
        """
        Given: A misspelled synonym
        When: Detecting misspelling
        Then: Should identify the intended word
        """
        result = self.agent.detect_misspelling("enormus", "big")  # Missing 'o'
        
        assert result["is_misspelling"] is True
        assert result["intended_word"] == "enormous"
        assert result["edit_distance"] == 1
        assert result["confidence"] > 0.8
    
    def test_detect_misspelling_negative(self):
        """
        Given: A word that is not a misspelling
        When: Detecting misspelling
        Then: Should return no misspelling found
        """
        result = self.agent.detect_misspelling("car", "happy")
        
        assert result["is_misspelling"] is False
        assert result["intended_word"] is None
        assert result["confidence"] == 0.0
    
    def test_generate_contextual_hint_target_word(self):
        """
        Given: Analysis showing target word was guessed
        When: Generating hint
        Then: Should provide target word specific feedback
        """
        analysis = {"relationship_type": "target_word"}
        hint = self.agent.generate_contextual_hint("happy", "happy", analysis)
        
        assert "can't use the target word" in hint.lower()
        assert "happy" in hint
    
    def test_generate_contextual_hint_misspelling(self):
        """
        Given: Analysis showing misspelling
        When: Generating hint
        Then: Should provide correction suggestion
        """
        analysis = {
            "relationship_type": "misspelling",
            "intended_word": "joyful"
        }
        hint = self.agent.generate_contextual_hint("joyfull", "happy", analysis)
        
        assert "close!" in hint.lower()
        assert "joyful" in hint
        assert "synonym" in hint.lower()
    
    def test_generate_contextual_hint_related(self):
        """
        Given: Analysis showing related concept
        When: Generating hint
        Then: Should guide toward synonyms
        """
        analysis = {"relationship_type": "related"}
        hint = self.agent.generate_contextual_hint("sad", "happy", analysis)
        
        assert "related" in hint.lower()
        assert "synonym" in hint.lower()
    
    def test_generate_contextual_hint_unrelated(self):
        """
        Given: Analysis showing unrelated guess
        When: Generating hint
        Then: Should provide vocabulary guidance
        """
        analysis = {"relationship_type": "unrelated"}
        hint = self.agent.generate_contextual_hint("car", "happy", analysis)
        
        assert "isn't related" in hint.lower()
        assert len(hint) > 20  # Should include vocabulary hint
    
    def test_analyze_hint_request_complete_flow(self):
        """
        Given: A complete hint request
        When: Processing the request
        Then: Should return structured hint response
        """
        request = HintRequest(
            guess="joyfull",
            target_word="happy",
            previous_guesses=["sad", "angry"]
        )
        
        response = self.agent.analyze_hint_request(request)
        
        assert isinstance(response, HintResponse)
        assert response.hint_text is not None
        assert len(response.hint_text) > 0
        assert response.analysis_type in ["misspelling", "related", "unrelated", "wrong_form", "target_word"]
        assert 0.0 <= response.confidence <= 1.0
    
    def test_edit_distance_calculation(self):
        """
        Given: Two strings with known edit distance
        When: Calculating edit distance
        Then: Should return correct distance
        """
        # Test exact match
        assert self.agent._edit_distance("hello", "hello") == 0
        
        # Test single substitution
        assert self.agent._edit_distance("hello", "hallo") == 1
        
        # Test single insertion
        assert self.agent._edit_distance("hello", "helloo") == 1
        
        # Test single deletion
        assert self.agent._edit_distance("hello", "hell") == 1
        
        # Test multiple operations
        assert self.agent._edit_distance("kitten", "sitting") == 3
    
    def test_get_common_synonyms(self):
        """
        Given: A target word
        When: Getting common synonyms
        Then: Should return appropriate synonym list
        """
        synonyms = self.agent._get_common_synonyms("happy")
        
        assert isinstance(synonyms, list)
        assert len(synonyms) > 0
        assert "joyful" in synonyms
        assert "cheerful" in synonyms
        
        # Test unknown word
        unknown_synonyms = self.agent._get_common_synonyms("unknown")
        assert unknown_synonyms == []
    
    def test_is_related_concept(self):
        """
        Given: Words that may be related concepts
        When: Checking if they are related
        Then: Should correctly identify relationships
        """
        # Same category (emotions)
        assert self.agent._is_related_concept("sad", "happy") is True
        
        # Same category (sizes)
        assert self.agent._is_related_concept("tiny", "big") is True
        
        # Different categories
        assert self.agent._is_related_concept("happy", "big") is False
        
        # Unrelated words
        assert self.agent._is_related_concept("car", "tree") is False
    
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=20))
    def test_property_7_hint_generation_quality(self, guess):
        """
        Feature: synonym-seeker, Property 7: Hint Generation Quality
        For any incorrect guess analysis, the Hint Provider SHALL generate contextual 
        feedback that explains why the guess was incorrect and suggests alternative approaches.
        """
        # Given: Any incorrect guess
        target_word = "happy"
        
        # When: Analyzing and generating hint
        analysis = self.agent.analyze_guess_relationship(guess, target_word)
        hint = self.agent.generate_contextual_hint(guess, target_word, analysis)
        
        # Then: Should generate quality feedback
        assert isinstance(hint, str)
        assert len(hint) > 10  # Should be substantive
        assert len(hint) < 200  # Should be concise
        
        # Should contain the guess or target word for context
        assert guess.lower() in hint.lower() or target_word.lower() in hint.lower()
        
        # Should be encouraging (no negative words)
        negative_words = ["wrong", "bad", "stupid", "dumb", "terrible"]
        hint_lower = hint.lower()
        for word in negative_words:
            assert word not in hint_lower, f"Hint should not contain negative word: {word}"
    
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=3, max_size=15),
        st.sampled_from(["happy", "fast", "big", "smart", "cold", "loud", "small", "beautiful"])
    )
    def test_property_8_misspelling_detection(self, guess, target_word):
        """
        Feature: synonym-seeker, Property 8: Misspelling Detection
        For any guess that is a close misspelling of a valid synonym, the Hint Provider 
        SHALL identify the intended word and provide appropriate feedback.
        """
        # Given: Any guess and target word
        # When: Detecting misspellings
        result = self.agent.detect_misspelling(guess, target_word)
        
        # Then: Should provide consistent detection
        assert isinstance(result, dict)
        assert "is_misspelling" in result
        assert "intended_word" in result
        assert "confidence" in result
        
        # Confidence should be valid
        assert 0.0 <= result["confidence"] <= 1.0
        
        # If misspelling detected, should have intended word
        if result["is_misspelling"]:
            assert result["intended_word"] is not None
            assert isinstance(result["intended_word"], str)
            assert len(result["intended_word"]) > 0
        else:
            assert result["intended_word"] is None
    
    def test_lambda_handler_analyze_hint(self):
        """
        Given: A Lambda event for hint analysis
        When: Processing the event
        Then: Should return proper HTTP response
        """
        event = {
            'httpMethod': 'POST',
            'path': '/analyze-hint',
            'body': json.dumps({
                'guess': 'joyfull',
                'target_word': 'happy',
                'previous_guesses': ['sad']
            })
        }
        
        from src.hint_provider_agent import lambda_handler
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 200
        assert 'application/json' in response['headers']['Content-Type']
        
        body = json.loads(response['body'])
        assert 'hintText' in body
        assert 'analysisType' in body
        assert 'confidence' in body
    
    def test_lambda_handler_cors(self):
        """
        Given: A CORS preflight request
        When: Processing the event
        Then: Should return proper CORS headers
        """
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/analyze-hint'
        }
        
        from src.hint_provider_agent import lambda_handler
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 200
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        assert 'POST' in response['headers']['Access-Control-Allow-Methods']
    
    def test_lambda_handler_not_found(self):
        """
        Given: A request to unknown endpoint
        When: Processing the event
        Then: Should return 404
        """
        event = {
            'httpMethod': 'GET',
            'path': '/unknown'
        }
        
        from src.hint_provider_agent import lambda_handler
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 404
        
        body = json.loads(response['body'])
        assert 'error' in body


# Import json for lambda handler tests
import json