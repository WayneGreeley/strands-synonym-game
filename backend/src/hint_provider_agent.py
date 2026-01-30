"""Hint Provider Agent for SynonymSeeker."""

import os
import json
import re
from typing import Dict, Any, Optional, List
from strands import Agent, tool
from src.models import HintRequest, HintResponse


class HintProviderAgent:
    """Secondary agent responsible for analyzing incorrect guesses and providing contextual feedback."""
    
    def __init__(self):
        """Initialize the Hint Provider Agent."""
        self.agent = Agent(
            tools=[
                self.analyze_guess_relationship,
                self.detect_misspelling,
                self.generate_contextual_hint
            ],
            system_prompt="""You are the Hint Provider Agent for SynonymSeeker, a word puzzle game.

Your responsibilities:
1. Analyze the relationship between incorrect guesses and target words
2. Detect close misspellings of valid synonyms
3. Generate helpful, contextual feedback to guide players
4. Provide educational hints that improve vocabulary understanding
5. Maintain encouraging tone while being informative

Analysis Guidelines:
- Classify guess relationships: unrelated, related concept, close misspelling, or wrong form
- For misspellings: identify the intended word and provide gentle correction
- For related concepts: explain the difference and guide toward synonyms
- For unrelated words: provide vocabulary building hints about the target word
- Always be encouraging and educational, never dismissive

Response Format:
- Keep hints concise but informative (1-2 sentences)
- Use positive language that encourages continued play
- Provide specific guidance when possible
- Include vocabulary insights when appropriate"""
        )
    
    @tool
    def analyze_guess_relationship(self, guess: str, target_word: str, previous_guesses: List[str] = None) -> dict:
        """Analyze the relationship between a guess and the target word.
        
        Args:
            guess: The player's incorrect guess
            target_word: The target word for this game
            previous_guesses: List of previous guesses for context
            
        Returns:
            dict: Analysis containing relationship type, confidence, and reasoning
        """
        guess_lower = guess.lower().strip()
        target_lower = target_word.lower().strip()
        
        # Prevent analysis of the target word itself
        if guess_lower == target_lower:
            return {
                "relationship_type": "target_word",
                "confidence": 1.0,
                "reasoning": "Player submitted the target word itself"
            }
        
        # Check for close misspellings of common synonyms
        common_synonyms = self._get_common_synonyms(target_word)
        for synonym in common_synonyms:
            if self._is_close_misspelling(guess_lower, synonym.lower()):
                return {
                    "relationship_type": "misspelling",
                    "confidence": 0.9,
                    "reasoning": f"Close misspelling of '{synonym}'",
                    "intended_word": synonym
                }
        
        # Check for related concepts (same category/domain)
        if self._is_related_concept(guess_lower, target_lower):
            return {
                "relationship_type": "related",
                "confidence": 0.7,
                "reasoning": "Related concept but not a synonym"
            }
        
        # Check for wrong word form (adjective vs noun, etc.)
        if self._is_wrong_form(guess_lower, target_lower):
            return {
                "relationship_type": "wrong_form",
                "confidence": 0.6,
                "reasoning": "Different word form or grammatical category"
            }
        
        # Default to unrelated
        return {
            "relationship_type": "unrelated",
            "confidence": 0.8,
            "reasoning": "No clear relationship to target word"
        }
    
    @tool
    def detect_misspelling(self, guess: str, target_word: str) -> dict:
        """Detect if guess is a misspelling of a valid synonym.
        
        Args:
            guess: The player's guess
            target_word: The target word
            
        Returns:
            dict: Misspelling detection results with intended word if found
        """
        guess_lower = guess.lower().strip()
        common_synonyms = self._get_common_synonyms(target_word)
        
        best_match = None
        best_distance = float('inf')
        
        for synonym in common_synonyms:
            distance = self._edit_distance(guess_lower, synonym.lower())
            # Consider it a misspelling if edit distance is small relative to word length
            max_distance = max(1, len(synonym) // 3)  # Allow 1 error per 3 characters
            
            if distance <= max_distance and distance < best_distance:
                best_distance = distance
                best_match = synonym
        
        if best_match:
            return {
                "is_misspelling": True,
                "intended_word": best_match,
                "edit_distance": best_distance,
                "confidence": 1.0 - (best_distance / len(best_match))
            }
        
        return {
            "is_misspelling": False,
            "intended_word": None,
            "edit_distance": None,
            "confidence": 0.0
        }
    
    @tool
    def generate_contextual_hint(self, guess: str, target_word: str, analysis: dict) -> str:
        """Generate contextual hint based on guess analysis.
        
        Args:
            guess: The player's guess
            target_word: The target word
            analysis: Analysis results from analyze_guess_relationship
            
        Returns:
            str: Contextual hint text
        """
        relationship_type = analysis.get("relationship_type", "unrelated")
        
        if relationship_type == "target_word":
            return f"You can't use the target word '{target_word}' as a guess! Try finding words that mean the same thing."
        
        elif relationship_type == "misspelling":
            intended_word = analysis.get("intended_word", "")
            return f"Close! Did you mean '{intended_word}'? That would be a great synonym for '{target_word}'."
        
        elif relationship_type == "related":
            return f"'{guess}' is related to '{target_word}' but not quite a synonym. Think of words that mean exactly the same thing."
        
        elif relationship_type == "wrong_form":
            return f"'{guess}' is in the right area but try a different form of the word. What's another way to say '{target_word}'?"
        
        else:  # unrelated
            hints = self._get_vocabulary_hints(target_word)
            return f"'{guess}' isn't related to '{target_word}'. {hints}"
    
    def _get_common_synonyms(self, target_word: str) -> List[str]:
        """Get common synonyms for the target word."""
        # Use the same curated word sets as the Game Builder Agent
        synonym_sets = {
            "happy": ["joyful", "cheerful", "glad", "pleased", "content", "delighted"],
            "fast": ["quick", "rapid", "swift", "speedy", "hasty", "brisk"],
            "big": ["large", "huge", "enormous", "massive", "giant", "vast"],
            "smart": ["clever", "bright", "wise", "brilliant", "intelligent", "sharp"],
            "cold": ["chilly", "freezing", "icy", "frigid", "frosty", "cool"],
            "loud": ["noisy", "booming", "thunderous", "deafening", "blaring", "roaring"],
            "small": ["tiny", "little", "miniature", "petite", "compact", "minute"],
            "beautiful": ["gorgeous", "stunning", "lovely", "attractive", "pretty", "elegant"]
        }
        
        return synonym_sets.get(target_word.lower(), [])
    
    def _is_close_misspelling(self, guess: str, target: str) -> bool:
        """Check if guess is a close misspelling of target."""
        if abs(len(guess) - len(target)) > 2:
            return False
        
        distance = self._edit_distance(guess, target)
        max_distance = max(1, len(target) // 3)
        return distance <= max_distance
    
    def _edit_distance(self, s1: str, s2: str) -> int:
        """Calculate edit distance between two strings."""
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _is_related_concept(self, guess: str, target: str) -> bool:
        """Check if guess is a related concept to target."""
        # Simple heuristic: check for common word patterns or categories
        emotion_words = ["happy", "sad", "angry", "excited", "calm", "worried"]
        size_words = ["big", "small", "large", "tiny", "huge", "little"]
        speed_words = ["fast", "slow", "quick", "rapid", "sluggish"]
        temperature_words = ["hot", "cold", "warm", "cool", "freezing", "boiling"]
        
        categories = [emotion_words, size_words, speed_words, temperature_words]
        
        for category in categories:
            if target in category and guess in category:
                return True
        
        return False
    
    def _is_wrong_form(self, guess: str, target: str) -> bool:
        """Check if guess is wrong grammatical form of target."""
        # Simple heuristic: check for common suffixes that change word form
        form_patterns = [
            (r'ly$', r''),  # adverb to adjective: quickly -> quick
            (r'ness$', r''),  # noun to adjective: happiness -> happy
            (r'ing$', r''),  # gerund to verb: running -> run
            (r'ed$', r''),  # past tense to present: walked -> walk
        ]
        
        for pattern, replacement in form_patterns:
            guess_root = re.sub(pattern, replacement, guess)
            target_root = re.sub(pattern, replacement, target)
            if guess_root == target_root or guess == target_root or guess_root == target:
                return True
        
        return False
    
    def _get_vocabulary_hints(self, target_word: str) -> str:
        """Get vocabulary building hints for the target word."""
        hints = {
            "happy": "Think of emotions that express joy or contentment.",
            "fast": "Consider words that describe quick movement or speed.",
            "big": "Look for words that describe large size or scale.",
            "smart": "Think of words that describe intelligence or cleverness.",
            "cold": "Consider words that describe low temperature or chilliness.",
            "loud": "Look for words that describe high volume or noise.",
            "small": "Think of words that describe tiny size or compactness.",
            "beautiful": "Consider words that describe attractiveness or elegance."
        }
        
        return hints.get(target_word.lower(), f"Think of words that have a similar meaning to '{target_word}'.")
    
    def analyze_hint_request(self, request: HintRequest) -> HintResponse:
        """Process a hint request and return structured response."""
        # Analyze the guess relationship
        analysis = self.analyze_guess_relationship(
            request.guess, 
            request.target_word, 
            request.previous_guesses
        )
        
        # Check for misspellings
        misspelling_result = self.detect_misspelling(request.guess, request.target_word)
        
        # Generate contextual hint
        if misspelling_result["is_misspelling"]:
            # Use misspelling analysis for hint generation
            analysis["relationship_type"] = "misspelling"
            analysis["intended_word"] = misspelling_result["intended_word"]
        
        hint_text = self.generate_contextual_hint(request.guess, request.target_word, analysis)
        
        return HintResponse(
            hint_text=hint_text,
            analysis_type=analysis["relationship_type"],
            confidence=analysis["confidence"]
        )


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda handler for Hint Provider Agent."""
    try:
        # Initialize agent
        hint_provider = HintProviderAgent()
        
        # Parse request
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        body = event.get('body', '{}')
        
        if isinstance(body, str):
            body = json.loads(body) if body else {}
        
        # Route requests
        if http_method == 'POST' and path == '/analyze-hint':
            # Create hint request from body
            request = HintRequest(
                guess=body.get('guess', ''),
                target_word=body.get('target_word', ''),
                previous_guesses=body.get('previous_guesses', [])
            )
            
            response = hint_provider.analyze_hint_request(request)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({
                    'hintText': response.hint_text,
                    'analysisType': response.analysis_type,
                    'confidence': response.confidence
                })
            }
        
        elif http_method == 'OPTIONS':
            # Handle CORS preflight
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': ''
            }
        
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Not found'})
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }