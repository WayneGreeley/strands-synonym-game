"""Game Builder Agent for SynonymSeeker."""

import os
import json
import uuid
import asyncio
import httpx
from typing import Dict, Any, Optional
from strands import Agent, tool
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from src.models import (
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
    
    @tool
    def generate_word_puzzle(self) -> dict:
        """Generate a target word with 4 synonyms using external API.
        
        Returns:
            dict: Contains target_word and synonyms list with letter counts
        """
        # Use a curated word set for reliable gameplay
        # This ensures consistent, appropriate difficulty and avoids API failures
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
        """Send guess to Hint Provider agent for analysis using A2A protocol.
        
        Args:
            guess: The incorrect guess
            target_word: The target word
            
        Returns:
            str: Hint text from Hint Provider agent
        """
        try:
            # Try A2A communication first
            hint_provider_url = os.environ.get('HINT_PROVIDER_A2A_URL')
            if hint_provider_url:
                return self._request_hint_via_a2a(guess, target_word, hint_provider_url)
        except Exception as e:
            # Log the error but continue with fallback
            print(f"A2A communication failed: {e}")
        
        # Fallback to basic hint generation
        return self._generate_fallback_hint(guess, target_word)
    
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
        """Start a new game session."""
        # Generate word puzzle
        puzzle_data = self.generate_word_puzzle()
        
        # Create session
        session_id = str(uuid.uuid4())
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
        
        # Store session
        self.sessions[session_id] = session
        
        # Return response
        return StartGameResponse(
            session_id=session_id,
            target_word=puzzle_data["target_word"],
            synonym_slots=[
                {"letterCount": slot.letter_count} 
                for slot in synonyms
            ]
        )
    
    def submit_guess(self, request: GuessRequest) -> GuessResponse:
        """Process a player's guess."""
        session = self.sessions.get(request.session_id)
        if not session:
            return GuessResponse(
                success=False,
                message="Invalid session ID",
                hint=None,
                game_state={}
            )

        if session.status != GameStatus.ACTIVE:
            return GuessResponse(
                success=False,
                message="Game is not active",
                hint=None,
                game_state=self._get_game_state_dict(session)
            )

        # Check if guess is the target word itself
        if request.guess.lower() == session.target_word.lower():
            session.guess_count += 1
            session.guessed_words.append(request.guess)
            return GuessResponse(
                success=False,
                message=f"You can't use the target word '{session.target_word}' as a guess! Try finding words that mean the same thing.",
                hint=None,
                game_state=self._get_game_state_dict(session)
            )

        # Check for duplicate guess
        if request.guess.lower() in [g.lower() for g in session.guessed_words]:
            # Still increment guess count for duplicates
            session.guess_count += 1
            return GuessResponse(
                success=False,
                message=f"You already guessed '{request.guess}'. Try a different word.",
                hint=None,
                game_state=self._get_game_state_dict(session)
            )

        # Add guess to history
        session.add_guess(request.guess)

        # Validate guess using actual synonyms
        actual_synonyms = getattr(session, '_actual_synonyms', [])
        synonym_data = [
            {"word": syn_word, "letter_count": len(syn_word)}
            for syn_word in actual_synonyms
        ]

        is_valid = self.validate_guess(request.guess, session.target_word, synonym_data)

        if is_valid:
            # Find matching synonym slot and mark as found
            actual_synonyms = getattr(session, '_actual_synonyms', [])
            for i, slot in enumerate(session.synonyms):
                if (slot.word is None and 
                    i < len(actual_synonyms) and
                    (request.guess.lower() == actual_synonyms[i].lower() or
                     self._is_close_match(request.guess.lower(), actual_synonyms[i].lower()))):
                    slot.word = request.guess
                    slot.found = True
                    break

            # Check if game is complete
            if session.is_complete():
                session.status = GameStatus.COMPLETED
                message = f"Correct! '{request.guess}' is a synonym. Congratulations! You found all synonyms!"
            else:
                message = f"Correct! '{request.guess}' is a synonym of '{session.target_word}'."

            return GuessResponse(
                success=True,
                message=message,
                hint=None,
                game_state=self._get_game_state_dict(session)
            )
        else:
            # Get hint for incorrect guess
            hint = self.request_hint_analysis(request.guess, session.target_word)

            return GuessResponse(
                success=False,
                message=f"'{request.guess}' is not a synonym of '{session.target_word}'.",
                hint=hint,
                game_state=self._get_game_state_dict(session)
            )
    
    def give_up(self, session_id: str) -> GiveUpResponse:
        """Handle give up request."""
        session = self.sessions.get(session_id)
        if not session:
            return GiveUpResponse(
                message="Invalid session ID",
                game_state={}
            )
        
        # Reveal all synonyms using stored actual synonyms
        actual_synonyms = getattr(session, '_actual_synonyms', [])
        for i, slot in enumerate(session.synonyms):
            if not slot.found and i < len(actual_synonyms):
                slot.word = actual_synonyms[i]
                slot.found = True
        
        session.status = GameStatus.GIVEN_UP
        
        return GiveUpResponse(
            message="Game ended. Here are all the synonyms:",
            game_state=self._get_game_state_dict(session)
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
            "status": session.status.value,
            "guessedWords": session.guessed_words
        }


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda handler for Game Builder Agent."""
    try:
        # Initialize agent
        game_builder = GameBuilderAgent()
        
        # Parse request
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
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
        
        if isinstance(body, str):
            try:
                body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
        
        # Route requests
        if http_method == 'POST' and path == '/start-game':
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
        
        elif http_method == 'POST' and path == '/submit-guess':
            try:
                request = GuessRequest(**body)
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
                # Handle validation errors from GuessRequest
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': str(e)})
                }
        
        elif http_method == 'POST' and path == '/give-up':
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
        # Log error for debugging but don't expose internal details
        print(f"Internal error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }