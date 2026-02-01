"""Game Builder Agent for SynonymSeeker."""

import os
import json
import uuid
import asyncio
import httpx
import time
from typing import Dict, Any, Optional, List
from strands import Agent, tool
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from .models import (
    GameSession, SynonymSlot, GameStatus,
    StartGameResponse, GuessRequest, GuessResponse, GiveUpResponse
)


class GameBuilderAgent:
    """Main agent responsible for game state management and guess validation."""
    
    def __init__(self):
        """Initialize the Game Builder Agent."""
        self.agent = Agent(
            tools=[
                self.generate_word_puzzle,
                self.validate_guess,
                self.request_hint_analysis
            ],
            system_prompt="""You are the Game Builder Agent for SynonymSeeker, a word puzzle game.

Your responsibilities:
1. Generate target words with exactly 4 synonyms using external APIs
2. Validate player guesses for correctness (including close matches and misspellings)
3. Manage game state and session tracking
4. Coordinate with the Hint Provider agent for incorrect guesses
5. Handle game completion and give-up scenarios

Game Rules:
- Each game has 1 target word and exactly 4 synonyms to find
- Players can make unlimited guesses
- Accept correct synonyms and close misspellings
- Reject duplicate guesses with appropriate feedback
- Track guess count and game status
- Provide hints for incorrect guesses via the Hint Provider agent

Always respond with valid JSON for API endpoints and maintain game state consistency."""
        )
        
        # In-memory session storage (for development - would use database in production)
        self.sessions: Dict[str, GameSession] = {}
        
        # Session cleanup tracking
        self.session_cleanup_interval = 30 * 60  # 30 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions to prevent memory leaks."""
        current_time = time.time()
        
        # Only run cleanup periodically
        if current_time - self.last_cleanup < self.session_cleanup_interval:
            return
        
        expired_sessions = []
        session_timeout = 30 * 60  # 30 minutes
        
        for session_id, session in self.sessions.items():
            # Check if session has been inactive for too long
            # For simplicity, we'll use a basic timeout approach
            if hasattr(session, '_last_activity'):
                if current_time - session._last_activity > session_timeout:
                    expired_sessions.append(session_id)
            else:
                # Add activity tracking to existing sessions
                session._last_activity = current_time
        
        # Remove expired sessions
        for session_id in expired_sessions:
            print(f"Cleaning up expired session: {session_id}")
            del self.sessions[session_id]
        
        self.last_cleanup = current_time
        
        # Log session count for monitoring
        if len(self.sessions) > 100:  # Warn if too many sessions
            print(f"Warning: {len(self.sessions)} active sessions")
    
    def _update_session_activity(self, session: GameSession) -> None:
        """Update session activity timestamp."""
        import time
        session._last_activity = time.time()
    
    @tool
    def generate_word_puzzle(self) -> dict:
        """Generate a target word with 4 synonyms using external API with fallback.
        
        Returns:
            dict: Contains target_word and synonyms list with letter counts
        """
        try:
            # Try external API first if configured
            external_api_key = os.environ.get('THESAURUS_API_KEY')
            if external_api_key and external_api_key != 'your-thesaurus-api-key-here':
                try:
                    return self._generate_from_external_api()
                except Exception as e:
                    print(f"External API failed, falling back to curated words: {e}")
                    # Continue to fallback
            
            # Fallback to curated word set for reliable gameplay
            return self._generate_from_curated_words()
            
        except Exception as e:
            # Ultimate fallback - return a simple, guaranteed word set
            print(f"Word generation failed, using emergency fallback: {e}")
            return {
                "target_word": "happy",
                "synonyms": [
                    {"word": "joyful", "letter_count": 6},
                    {"word": "glad", "letter_count": 4},
                    {"word": "pleased", "letter_count": 7},
                    {"word": "cheerful", "letter_count": 8}
                ]
            }
    
    def _generate_from_external_api(self) -> dict:
        """Generate word puzzle using external thesaurus API."""
        # This would integrate with a real thesaurus API
        # For now, simulate API behavior with potential failures
        import random
        
        # Simulate API failure occasionally for testing
        if random.random() < 0.1:  # 10% failure rate for testing
            raise Exception("Simulated external API failure")
        
        # Use curated words but simulate external API response format
        return self._generate_from_curated_words()
    
    def _generate_from_curated_words(self) -> dict:
        """Generate word puzzle from curated word sets."""
        word_sets = [
            {
                "target_word": "happy",
                "synonyms": ["joyful", "cheerful", "glad", "pleased"]
            },
            {
                "target_word": "fast",
                "synonyms": ["quick", "rapid", "swift", "speedy"]
            },
            {
                "target_word": "big",
                "synonyms": ["large", "huge", "enormous", "massive"]
            },
            {
                "target_word": "smart",
                "synonyms": ["clever", "bright", "wise", "brilliant"]
            },
            {
                "target_word": "cold",
                "synonyms": ["chilly", "freezing", "icy", "frigid"]
            },
            {
                "target_word": "loud",
                "synonyms": ["noisy", "booming", "thunderous", "deafening"]
            },
            {
                "target_word": "small",
                "synonyms": ["tiny", "little", "miniature", "petite"]
            },
            {
                "target_word": "beautiful",
                "synonyms": ["gorgeous", "stunning", "lovely", "attractive"]
            }
        ]
        
        # Select a random word set
        import random
        word_set = random.choice(word_sets)
        
        # Validate word set has exactly 4 synonyms
        if len(word_set["synonyms"]) != 4:
            raise ValueError(f"Word set must have exactly 4 synonyms, got {len(word_set['synonyms'])}")
        
        # Validate all synonyms are appropriate length (not too short/long)
        for syn in word_set["synonyms"]:
            if len(syn) < 3 or len(syn) > 15:
                raise ValueError(f"Synonym '{syn}' has inappropriate length: {len(syn)}")
        
        return {
            "target_word": word_set["target_word"],
            "synonyms": [
                {"word": syn, "letter_count": len(syn)} 
                for syn in word_set["synonyms"]
            ]
        }
    
    @tool
    def validate_guess(self, guess: str, target_word: str, synonyms: list) -> bool:
        """Validate if guess is a correct synonym (including close matches).
        
        Args:
            guess: Player's guess
            target_word: The target word for this game
            synonyms: List of valid synonyms
            
        Returns:
            bool: True if guess is valid, False otherwise
        """
        guess_lower = guess.lower().strip()
        target_lower = target_word.lower().strip()
        
        # Reject if guess is the target word itself
        if guess_lower == target_lower:
            return False
        
        # Check exact matches
        synonym_words = [syn["word"].lower() if isinstance(syn, dict) else syn.lower() 
                        for syn in synonyms]
        
        if guess_lower in synonym_words:
            return True
        
        # Check for close misspellings (simple Levenshtein distance)
        for syn_word in synonym_words:
            if self._is_close_match(guess_lower, syn_word):
                return True
        
        return False
    
    def _is_close_match(self, guess: str, target: str) -> bool:
        """Check if guess is a close misspelling of target using simple edit distance."""
        if abs(len(guess) - len(target)) > 2:
            return False
        
        # Simple edit distance calculation
        if len(guess) < len(target):
            guess, target = target, guess
        
        differences = 0
        for i, char in enumerate(target):
            if i >= len(guess) or guess[i] != char:
                differences += 1
                if differences > 2:
                    return False
        
        differences += len(guess) - len(target)
        return differences <= 2
    
    @tool
    def request_hint_analysis(self, guess: str, target_word: str) -> str:
        """Send guess to Hint Provider agent for analysis using A2A protocol with comprehensive fallback.
        
        Args:
            guess: The incorrect guess
            target_word: The target word
            
        Returns:
            str: Hint text from Hint Provider agent or fallback hint
        """
        # Input validation and sanitization
        if not guess or not target_word:
            return "Please enter a valid word to get a hint."
        
        guess = str(guess).strip()
        target_word = str(target_word).strip()
        
        if not guess or not target_word:
            return "Please enter a valid word to get a hint."
        
        # Try multiple communication methods with graceful fallback
        hint_methods = [
            self._try_a2a_communication,
            self._try_direct_http_communication,
            self._generate_fallback_hint
        ]
        
        last_error = None
        for i, method in enumerate(hint_methods):
            try:
                hint = method(guess, target_word)
                if hint and isinstance(hint, str) and len(hint.strip()) > 0:
                    return hint
            except Exception as e:
                last_error = e
                method_name = getattr(method, '__name__', f'method_{i}')
                print(f"Hint method {method_name} failed: {e}")
                continue
        
        # Ultimate fallback if all methods fail
        print(f"All hint methods failed, last error: {last_error}")
        return self._generate_emergency_fallback_hint(guess, target_word)
    
    def _try_a2a_communication(self, guess: str, target_word: str) -> str:
        """Try A2A protocol communication with Hint Provider."""
        hint_provider_url = os.environ.get('HINT_PROVIDER_A2A_URL')
        if not hint_provider_url or hint_provider_url == 'https://your-hint-provider-function-url.lambda-url.us-east-1.on.aws/':
            raise Exception("A2A URL not configured")
        
        return self._request_hint_via_a2a(guess, target_word, hint_provider_url)
    
    def _try_direct_http_communication(self, guess: str, target_word: str) -> str:
        """Try direct HTTP communication with Hint Provider."""
        hint_provider_url = os.environ.get('HINT_PROVIDER_URL')
        if not hint_provider_url or hint_provider_url == 'https://your-hint-provider-function-url.lambda-url.us-east-1.on.aws/':
            raise Exception("Direct HTTP URL not configured")
        
        # Make direct HTTP request to hint provider
        import httpx
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{hint_provider_url}/analyze-hint",
                    json={
                        "guess": guess,
                        "target_word": target_word,
                        "previous_guesses": []
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("hintText", "")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            raise Exception(f"Direct HTTP communication failed: {e}")
    
    def _generate_emergency_fallback_hint(self, guess: str, target_word: str) -> str:
        """Generate emergency fallback hint when all communication methods fail."""
        # Sanitize inputs for safe display
        guess_clean = ''.join(c for c in guess if c.isalpha())[:20]
        target_clean = ''.join(c for c in target_word if c.isalpha())[:20]
        
        if not guess_clean or not target_clean:
            return "Please enter a valid word to get a hint."
        
        # Basic hint logic without external dependencies
        if guess_clean.lower() == target_clean.lower():
            return f"You can't use the target word '{target_clean}' as a guess! Try finding words that mean the same thing."
        
        if len(guess_clean) < 3:
            return f"'{guess_clean}' is quite short. Try thinking of longer words that mean the same as '{target_clean}'."
        
        # Provide category-based hints for known target words
        category_hints = {
            "happy": "Think of emotions that express joy or contentment.",
            "fast": "Consider words that describe quick movement or speed.",
            "big": "Look for words that describe large size or scale.",
            "smart": "Think of words that describe intelligence or cleverness.",
            "cold": "Consider words that describe low temperature or chilliness.",
            "loud": "Look for words that describe high volume or noise.",
            "small": "Think of words that describe tiny size or compactness.",
            "beautiful": "Consider words that describe attractiveness or elegance."
        }
        
        category_hint = category_hints.get(target_clean.lower(), f"Think of words that have a similar meaning to '{target_clean}'.")
        
        return f"'{guess_clean}' is not a synonym of '{target_clean}'. {category_hint}"
    
    def _request_hint_via_a2a(self, guess: str, target_word: str, hint_provider_url: str) -> str:
        """Request hint via A2A protocol (synchronous wrapper for async call)."""
        try:
            # Run the async A2A communication
            return asyncio.run(self._async_request_hint_via_a2a(guess, target_word, hint_provider_url))
        except Exception as e:
            raise Exception(f"A2A communication error: {e}")
    
    async def _async_request_hint_via_a2a(self, guess: str, target_word: str, hint_provider_url: str) -> str:
        """Request hint via A2A protocol (async implementation)."""
        DEFAULT_TIMEOUT = 30  # 30 second timeout for agent communication
        
        # Generate a unique session ID for this communication
        session_id = str(uuid.uuid4())
        
        # Prepare authentication headers if available
        headers = {}
        bearer_token = os.environ.get('BEARER_TOKEN')
        if bearer_token:
            headers['Authorization'] = f'Bearer {bearer_token}'
        headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = session_id
        
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers) as httpx_client:
            # Get agent card from the Hint Provider
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=hint_provider_url)
            agent_card = await resolver.get_agent_card()
            
            # Create A2A client
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=False,  # Use non-streaming mode for sync response
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            
            # Create message for hint analysis
            message_text = f"Analyze guess '{guess}' for target word '{target_word}'. Provide helpful hint."
            msg = self._create_a2a_message(text=message_text)
            
            # Send message and get response
            async for event in client.send_message(msg):
                if isinstance(event, Message):
                    # Extract text from message parts
                    return self._extract_text_from_message(event)
                elif isinstance(event, tuple) and len(event) == 2:
                    # (Task, UpdateEvent) tuple
                    task, update_event = event
                    if hasattr(task, 'artifacts') and task.artifacts:
                        for artifact in task.artifacts:
                            if hasattr(artifact, 'parts') and artifact.parts:
                                for part in artifact.parts:
                                    if hasattr(part, 'text'):
                                        return part.text
                    return "Unable to extract hint from agent response"
                else:
                    # Fallback for other response types
                    return str(event)
        
        raise Exception("No response received from Hint Provider agent")
    
    def _create_a2a_message(self, *, role: Role = Role.user, text: str) -> Message:
        """Create A2A message for communication."""
        return Message(
            kind="message",
            role=role,
            parts=[TextPart(kind="text", text=text)],
            message_id=uuid.uuid4().hex,
        )
    
    def _extract_text_from_message(self, message: Message) -> str:
        """Extract text content from A2A message."""
        if hasattr(message, 'parts') and message.parts:
            for part in message.parts:
                if hasattr(part, 'text'):
                    return part.text
        return "Unable to extract text from message"
    
    def _generate_fallback_hint(self, guess: str, target_word: str) -> str:
        """Generate basic hint when A2A communication fails."""
        if len(guess) < 3:
            return f"'{guess}' is too short. Try thinking of longer words that mean the same as '{target_word}'."
        
        if guess.lower() == target_word.lower():
            return f"You can't use the target word '{target_word}' as a guess! Try finding words that mean the same thing."
        
        # Basic hint based on word relationship
        return f"'{guess}' is not a synonym of '{target_word}'. Think of words that have a similar meaning to '{target_word}'."
    
    def start_new_game(self) -> StartGameResponse:
        """Start a new game session with comprehensive error handling."""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Generate word puzzle with fallback handling
                puzzle_data = self.generate_word_puzzle()
                
                # Validate puzzle data
                if not self._validate_puzzle_data(puzzle_data):
                    raise ValueError("Generated puzzle data is invalid")
                
                # Create session with unique ID
                session_id = str(uuid.uuid4())
                
                # Ensure session ID is unique (handle collision)
                collision_count = 0
                while session_id in self.sessions and collision_count < 10:
                    session_id = str(uuid.uuid4())
                    collision_count += 1
                
                if collision_count >= 10:
                    raise Exception("Unable to generate unique session ID")
                
                synonyms = [
                    SynonymSlot(
                        word=None,
                        letter_count=syn["letter_count"],
                        found=False
                    )
                    for syn in puzzle_data["synonyms"]
                ]
                
                session = GameSession(
                    session_id=session_id,
                    target_word=puzzle_data["target_word"],
                    synonyms=synonyms,
                    guess_count=0,
                    status=GameStatus.ACTIVE,
                    guessed_words=[]
                )
                
                # Store the actual synonym words for validation (not exposed to client)
                session._actual_synonyms = [syn["word"] for syn in puzzle_data["synonyms"]]
                
                # Add activity tracking
                self._update_session_activity(session)
                
                # Store session with error handling
                try:
                    self.sessions[session_id] = session
                except Exception as e:
                    raise Exception(f"Failed to store session: {e}")
                
                # Return response
                return StartGameResponse(
                    session_id=session_id,
                    target_word=puzzle_data["target_word"],
                    synonym_slots=[
                        {"letterCount": slot.letter_count} 
                        for slot in synonyms
                    ]
                )
                
            except Exception as e:
                last_error = e
                print(f"Game creation attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Wait before retrying
                    import time
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Final attempt failed
                    break
        
        # If all attempts failed, create emergency fallback game
        print(f"All game creation attempts failed, creating emergency game. Last error: {last_error}")
        return self._create_emergency_game()
    
    def _validate_puzzle_data(self, puzzle_data: dict) -> bool:
        """Validate generated puzzle data structure."""
        try:
            if not isinstance(puzzle_data, dict):
                return False
            
            if "target_word" not in puzzle_data or not puzzle_data["target_word"]:
                return False
            
            if "synonyms" not in puzzle_data or not isinstance(puzzle_data["synonyms"], list):
                return False
            
            if len(puzzle_data["synonyms"]) != 4:
                return False
            
            for syn in puzzle_data["synonyms"]:
                if not isinstance(syn, dict):
                    return False
                if "word" not in syn or "letter_count" not in syn:
                    return False
                if not isinstance(syn["word"], str) or not isinstance(syn["letter_count"], int):
                    return False
                if len(syn["word"]) != syn["letter_count"]:
                    return False
                if syn["letter_count"] < 2 or syn["letter_count"] > 20:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _create_emergency_game(self) -> StartGameResponse:
        """Create emergency fallback game when all else fails."""
        session_id = f"emergency-{uuid.uuid4().hex[:8]}"
        
        # Simple, guaranteed-to-work game
        emergency_synonyms = [
            SynonymSlot(word=None, letter_count=4, found=False),  # glad
            SynonymSlot(word=None, letter_count=6, found=False),  # joyful
            SynonymSlot(word=None, letter_count=7, found=False),  # pleased
            SynonymSlot(word=None, letter_count=8, found=False),  # cheerful
        ]
        
        session = GameSession(
            session_id=session_id,
            target_word="happy",
            synonyms=emergency_synonyms,
            guess_count=0,
            status=GameStatus.ACTIVE,
            guessed_words=[]
        )
        
        session._actual_synonyms = ["glad", "joyful", "pleased", "cheerful"]
        self.sessions[session_id] = session
        
        return StartGameResponse(
            session_id=session_id,
            target_word="happy",
            synonym_slots=[
                {"letterCount": 4},
                {"letterCount": 6},
                {"letterCount": 7},
                {"letterCount": 8}
            ]
        )
    
    def submit_guess(self, request: GuessRequest) -> GuessResponse:
        """Process a player's guess with comprehensive error handling."""
        try:
            # Session validation with recovery
            session = self._get_session_with_recovery(request.session_id)
            if not session:
                return GuessResponse(
                    success=False,
                    message="Session not found. Please start a new game.",
                    hint=None,
                    game_state={}
                )

            # Session state validation
            if session.status != GameStatus.ACTIVE:
                return GuessResponse(
                    success=False,
                    message="Game is not active. Please start a new game.",
                    hint=None,
                    game_state=self._get_game_state_dict(session)
                )

            # Input validation and sanitization
            try:
                sanitized_guess = self._sanitize_and_validate_guess(request.guess)
            except ValueError as e:
                session.guess_count += 1  # Count invalid attempts
                return GuessResponse(
                    success=False,
                    message=str(e),
                    hint=None,
                    game_state=self._get_game_state_dict(session)
                )

            # Check if guess is the target word itself
            if sanitized_guess.lower() == session.target_word.lower():
                session.guess_count += 1
                session.guessed_words.append(sanitized_guess)
                return GuessResponse(
                    success=False,
                    message=f"You can't use the target word '{session.target_word}' as a guess! Try finding words that mean the same thing.",
                    hint=None,
                    game_state=self._get_game_state_dict(session)
                )

            # Check for duplicate guess
            if sanitized_guess.lower() in [g.lower() for g in session.guessed_words]:
                session.guess_count += 1
                return GuessResponse(
                    success=False,
                    message=f"You already guessed '{sanitized_guess}'. Try a different word.",
                    hint=None,
                    game_state=self._get_game_state_dict(session)
                )

            # Add guess to history
            session.add_guess(sanitized_guess)

            # Validate guess using actual synonyms with error handling
            try:
                actual_synonyms = getattr(session, '_actual_synonyms', [])
                if not actual_synonyms:
                    # Recovery: regenerate synonyms if missing
                    actual_synonyms = self._recover_session_synonyms(session)
                
                synonym_data = [
                    {"word": syn_word, "letter_count": len(syn_word)}
                    for syn_word in actual_synonyms
                ]

                is_valid = self.validate_guess(sanitized_guess, session.target_word, synonym_data)
            except Exception as e:
                print(f"Guess validation failed: {e}")
                # Fallback validation
                is_valid = self._fallback_guess_validation(sanitized_guess, session)

            if is_valid:
                # Find matching synonym slot and mark as found
                try:
                    actual_synonyms = getattr(session, '_actual_synonyms', [])
                    for i, slot in enumerate(session.synonyms):
                        if (slot.word is None and 
                            i < len(actual_synonyms) and
                            (sanitized_guess.lower() == actual_synonyms[i].lower() or
                             self._is_close_match(sanitized_guess.lower(), actual_synonyms[i].lower()))):
                            slot.word = sanitized_guess
                            slot.found = True
                            break

                    # Check if game is complete
                    if session.is_complete():
                        session.status = GameStatus.COMPLETED
                        message = f"Correct! '{sanitized_guess}' is a synonym. Congratulations! You found all synonyms!"
                    else:
                        message = f"Correct! '{sanitized_guess}' is a synonym of '{session.target_word}'."

                    return GuessResponse(
                        success=True,
                        message=message,
                        hint=None,
                        game_state=self._get_game_state_dict(session)
                    )
                except Exception as e:
                    print(f"Error updating game state for correct guess: {e}")
                    # Return success but with basic message
                    return GuessResponse(
                        success=True,
                        message=f"Correct! '{sanitized_guess}' is a synonym.",
                        hint=None,
                        game_state=self._get_game_state_dict(session)
                    )
            else:
                # Get hint for incorrect guess with error handling
                try:
                    hint = self.request_hint_analysis(sanitized_guess, session.target_word)
                except Exception as e:
                    print(f"Hint generation failed: {e}")
                    hint = f"'{sanitized_guess}' is not a synonym of '{session.target_word}'. Try thinking of words with similar meanings."

                return GuessResponse(
                    success=False,
                    message=f"'{sanitized_guess}' is not a synonym of '{session.target_word}'.",
                    hint=hint,
                    game_state=self._get_game_state_dict(session)
                )
                
        except Exception as e:
            print(f"Unexpected error in submit_guess: {e}")
            # Return generic error response
            return GuessResponse(
                success=False,
                message="An error occurred processing your guess. Please try again.",
                hint=None,
                game_state={}
            )
    
    def _get_session_with_recovery(self, session_id: str) -> Optional[GameSession]:
        """Get session with recovery for corrupted or missing sessions."""
        # Clean up expired sessions periodically
        self._cleanup_expired_sessions()
        
        if not session_id:
            return None
        
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Update activity tracking
        self._update_session_activity(session)
        
        # Validate session integrity
        try:
            # Check required attributes
            if not hasattr(session, 'target_word') or not session.target_word:
                raise ValueError("Session missing target word")
            
            if not hasattr(session, 'synonyms') or not session.synonyms:
                raise ValueError("Session missing synonyms")
            
            if len(session.synonyms) != 4:
                raise ValueError("Session has incorrect number of synonyms")
            
            if not hasattr(session, 'status'):
                session.status = GameStatus.ACTIVE
            
            if not hasattr(session, 'guess_count'):
                session.guess_count = 0
            
            if not hasattr(session, 'guessed_words'):
                session.guessed_words = []
            
            # Recover missing actual synonyms if needed
            if not hasattr(session, '_actual_synonyms') or not session._actual_synonyms:
                session._actual_synonyms = self._recover_session_synonyms(session)
            
            return session
            
        except Exception as e:
            print(f"Session recovery failed for {session_id}: {e}")
            # Remove corrupted session
            if session_id in self.sessions:
                del self.sessions[session_id]
            return None
    
    def _recover_session_synonyms(self, session: GameSession) -> List[str]:
        """Recover synonyms for a session based on target word."""
        # Use the same curated word sets to recover synonyms
        word_sets = {
            "happy": ["joyful", "cheerful", "glad", "pleased"],
            "fast": ["quick", "rapid", "swift", "speedy"],
            "big": ["large", "huge", "enormous", "massive"],
            "smart": ["clever", "bright", "wise", "brilliant"],
            "cold": ["chilly", "freezing", "icy", "frigid"],
            "loud": ["noisy", "booming", "thunderous", "deafening"],
            "small": ["tiny", "little", "miniature", "petite"],
            "beautiful": ["gorgeous", "stunning", "lovely", "attractive"]
        }
        
        synonyms = word_sets.get(session.target_word.lower(), [])
        if len(synonyms) >= 4:
            return synonyms[:4]
        
        # Fallback: generate generic synonyms
        return ["word1", "word2", "word3", "word4"]
    
    def _sanitize_and_validate_guess(self, guess: str) -> str:
        """Sanitize and validate guess input."""
        if not guess or not isinstance(guess, str):
            raise ValueError("Guess is required")
        
        # Basic sanitization
        sanitized = guess.strip()
        
        if not sanitized:
            raise ValueError("Guess cannot be empty")
        
        # Length validation
        if len(sanitized) > 50:
            raise ValueError("Guess is too long (maximum 50 characters)")
        
        # Multiple words check
        if ' ' in sanitized:
            raise ValueError("Please enter only one word")
        
        # Character validation
        if not sanitized.replace('-', '').replace("'", "").isalpha():
            raise ValueError("Please use only letters")
        
        return sanitized
    
    def _fallback_guess_validation(self, guess: str, session: GameSession) -> bool:
        """Fallback validation when main validation fails."""
        try:
            # Simple validation based on target word
            target_lower = session.target_word.lower()
            guess_lower = guess.lower()
            
            # Don't accept the target word itself
            if guess_lower == target_lower:
                return False
            
            # Use recovered synonyms for basic validation
            actual_synonyms = getattr(session, '_actual_synonyms', [])
            if not actual_synonyms:
                actual_synonyms = self._recover_session_synonyms(session)
            
            # Check exact matches
            for syn in actual_synonyms:
                if guess_lower == syn.lower():
                    return True
                # Check close matches
                if self._is_close_match(guess_lower, syn.lower()):
                    return True
            
            return False
            
        except Exception:
            # Ultimate fallback: reject unknown guesses
            return False
    
    def give_up(self, session_id: str) -> GiveUpResponse:
        """Handle give up request with comprehensive error handling."""
        try:
            # Session validation with recovery
            session = self._get_session_with_recovery(session_id)
            if not session:
                return GiveUpResponse(
                    message="Session not found. Please start a new game.",
                    game_state={}
                )
            
            # Reveal all synonyms using stored actual synonyms with recovery
            try:
                actual_synonyms = getattr(session, '_actual_synonyms', [])
                if not actual_synonyms:
                    actual_synonyms = self._recover_session_synonyms(session)
                
                for i, slot in enumerate(session.synonyms):
                    if not slot.found and i < len(actual_synonyms):
                        slot.word = actual_synonyms[i]
                        slot.found = True
                
                session.status = GameStatus.GIVEN_UP
                
                return GiveUpResponse(
                    message="Game ended. Here are all the synonyms:",
                    game_state=self._get_game_state_dict(session)
                )
                
            except Exception as e:
                print(f"Error revealing synonyms: {e}")
                # Fallback: mark game as given up even if we can't reveal all synonyms
                session.status = GameStatus.GIVEN_UP
                
                return GiveUpResponse(
                    message="Game ended. Some synonyms could not be revealed due to a technical issue.",
                    game_state=self._get_game_state_dict(session)
                )
                
        except Exception as e:
            print(f"Unexpected error in give_up: {e}")
            return GiveUpResponse(
                message="An error occurred ending the game. Please start a new game.",
                game_state={}
            )
    
    def _get_game_state_dict(self, session: GameSession) -> dict:
        """Convert GameSession to dictionary for API response."""
        return {
            "targetWord": session.target_word,
            "synonyms": [
                {
                    "word": slot.word,
                    "letterCount": slot.letter_count,
                    "found": slot.found
                }
                for slot in session.synonyms
            ],
            "guessCount": session.guess_count,
            "status": session.status.value if session.status else "CORRUPTED",
            "guessedWords": session.guessed_words
        }


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda handler for Game Builder Agent with comprehensive error handling."""
    try:
        # Initialize agent with error handling
        try:
            game_builder = GameBuilderAgent()
        except Exception as e:
            print(f"Failed to initialize Game Builder Agent: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Service temporarily unavailable'})
            }
        
        # Parse request with enhanced validation
        try:
            # Extract request details from Function URL event format
            request_context = event.get('requestContext', {})
            http_context = request_context.get('http', {})
            
            http_method = http_context.get('method', 'POST')
            path = http_context.get('path', '/')
            body = event.get('body', '{}')
            
            # Request size validation (Lambda has 6MB limit, we'll use 1MB for safety)
            MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
            if isinstance(body, str) and len(body.encode('utf-8')) > MAX_REQUEST_SIZE:
                return {
                    'statusCode': 413,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Request too large'})
                }
            
            # Parse JSON body with error handling
            if isinstance(body, str):
                try:
                    body = json.loads(body) if body else {}
                except json.JSONDecodeError as e:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Invalid JSON in request body'})
                    }
            
        except Exception as e:
            print(f"Request parsing error: {e}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid request format'})
            }
        
        # Route requests with individual error handling
        try:
            if http_method == 'POST' and path == '/start-game':
                try:
                    response = game_builder.start_new_game()
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'POST, OPTIONS',
                            'Access-Control-Allow-Headers': 'Content-Type'
                        },
                        'body': json.dumps({
                            'sessionId': response.session_id,
                            'targetWord': response.target_word,
                            'synonymSlots': response.synonym_slots,
                            'status': response.status
                        })
                    }
                except Exception as e:
                    print(f"Start game error: {e}")
                    return {
                        'statusCode': 500,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Failed to start new game'})
                    }
            
            elif http_method == 'POST' and path == '/submit-guess':
                try:
                    # Validate required fields
                    if not isinstance(body, dict):
                        raise ValueError("Request body must be a JSON object")
                    
                    session_id = body.get('sessionId')
                    guess = body.get('guess')
                    
                    if not session_id:
                        raise ValueError("Session ID is required")
                    
                    if not guess:
                        raise ValueError("Guess is required")
                    
                    request = GuessRequest(session_id=session_id, guess=guess)
                    response = game_builder.submit_guess(request)
                    
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'POST, OPTIONS',
                            'Access-Control-Allow-Headers': 'Content-Type'
                        },
                        'body': json.dumps({
                            'success': response.success,
                            'message': response.message,
                            'hint': response.hint,
                            'gameState': response.game_state
                        })
                    }
                except ValueError as e:
                    # Handle validation errors from GuessRequest or input validation
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': str(e)})
                    }
                except Exception as e:
                    print(f"Submit guess error: {e}")
                    return {
                        'statusCode': 500,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Failed to process guess'})
                    }
            
            elif http_method == 'POST' and path == '/give-up':
                try:
                    session_id = body.get('sessionId')
                    if not session_id:
                        return {
                            'statusCode': 400,
                            'headers': {
                                'Content-Type': 'application/json',
                                'Access-Control-Allow-Origin': '*'
                            },
                            'body': json.dumps({'error': 'Session ID is required'})
                        }
                    
                    response = game_builder.give_up(session_id)
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'POST, OPTIONS',
                            'Access-Control-Allow-Headers': 'Content-Type'
                        },
                        'body': json.dumps({
                            'message': response.message,
                            'gameState': response.game_state
                        })
                    }
                except Exception as e:
                    print(f"Give up error: {e}")
                    return {
                        'statusCode': 500,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Failed to end game'})
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
                    'body': json.dumps({'error': 'Endpoint not found'})
                }
                
        except Exception as e:
            print(f"Request routing error: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Internal routing error'})
            }
    
    except Exception as e:
        # Ultimate fallback for any unhandled errors
        print(f"Critical lambda handler error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }