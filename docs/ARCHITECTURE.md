# SynonymSeeker Architecture Documentation

## Overview

SynonymSeeker is designed as a multi-agent system using AWS Strands to demonstrate modern agent coordination patterns. This document provides detailed architectural insights for developers and learners.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐    HTTPS     ┌──────────────────┐
│   Vue.js SPA   │◄─────────────►│  CloudFront CDN  │
│   (Frontend)   │               │                  │
└─────────────────┘               └──────────────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │   S3 Bucket      │
                                  │ (Static Assets)  │
                                  └──────────────────┘

┌─────────────────┐    HTTPS     ┌──────────────────┐
│   Vue.js SPA   │◄─────────────►│ Game Builder     │
│   (Frontend)   │               │ Lambda Function  │
└─────────────────┘               └──────────────────┘
                                           │
                                           │ A2A Protocol
                                           ▼
                                  ┌──────────────────┐
                                  │ Hint Provider    │
                                  │ Lambda Function  │
                                  └──────────────────┘
```

### Component Breakdown

#### Frontend Layer
- **Technology**: Vue.js 3 with Composition API
- **Deployment**: S3 static website with CloudFront CDN
- **Responsibilities**:
  - User interface and interaction
  - Game state visualization
  - Input validation and sanitization
  - HTTP client for backend communication

#### Game Builder Agent
- **Technology**: Python 3.13 + AWS Strands SDK
- **Deployment**: AWS Lambda with Function URL
- **Responsibilities**:
  - Session management and state tracking
  - Word puzzle generation
  - Guess validation and misspelling detection
  - A2A communication coordination
  - Response formatting for frontend

#### Hint Provider Agent
- **Technology**: Python 3.13 + AWS Strands SDK
- **Deployment**: AWS Lambda with A2A Server
- **Responsibilities**:
  - Semantic analysis of incorrect guesses
  - Advanced misspelling detection
  - Contextual hint generation
  - Educational feedback creation

## Multi-Agent Communication

### A2A Protocol Implementation

The Agent-to-Agent protocol enables structured communication between the Game Builder and Hint Provider agents:

```python
# Game Builder Agent - A2A Client
async def request_hint_via_a2a(self, guess: str, target_word: str) -> str:
    async with httpx.AsyncClient() as client:
        resolver = A2ACardResolver(
            httpx_client=client, 
            base_url=self.hint_provider_url
        )
        agent_card = await resolver.get_agent_card()
        
        config = ClientConfig(httpx_client=client, streaming=False)
        factory = ClientFactory(config)
        a2a_client = factory.create(agent_card)
        
        message = create_message(
            text=f"Analyze guess '{guess}' for target word '{target_word}'"
        )
        
        async for event in a2a_client.send_message(message):
            if isinstance(event, Message):
                return extract_text_from_message(event)
```

```python
# Hint Provider Agent - A2A Server
def create_a2a_server(self) -> A2AServer:
    return A2AServer(
        agent=self.agent,
        title="Hint Provider Agent",
        description="Analyzes incorrect guesses and provides contextual feedback"
    )
```

### Communication Patterns

1. **Request-Response Pattern**: Game Builder initiates, Hint Provider responds
2. **Structured Messages**: JSON-formatted data exchange
3. **Error Handling**: Graceful fallbacks on communication failures
4. **Timeout Management**: 30-second timeout with fallback behavior

## Data Models

### Core Game Models

```python
@dataclass
class GameSession:
    session_id: str
    target_word: str
    synonyms: List[SynonymSlot]
    guess_count: int
    status: GameStatus
    guessed_words: List[str]
    _actual_synonyms: List[str]  # Internal synonym storage
```

```python
@dataclass
class SynonymSlot:
    word: Optional[str]
    letter_count: int
    found: bool = False
```

### API Models

```python
@dataclass
class GuessRequest:
    session_id: str
    guess: str
    
    def __post_init__(self):
        # Automatic sanitization and validation
        self.guess = self._sanitize_guess(self.guess)
        self._validate_input(self.guess)
```

```python
@dataclass
class GuessResponse:
    success: bool
    message: str
    hint: Optional[str]
    game_state: Dict[str, Any]
```

## Security Architecture

### Multi-Layer Security

1. **Input Validation**
   - Client-side: TypeScript type checking and form validation
   - Server-side: Python dataclass validation and sanitization
   - Protocol-level: A2A message structure validation

2. **Sanitization Pipeline**
   ```python
   def _sanitize_guess(self, guess: str) -> str:
       # Remove non-alphabetic characters
       sanitized = ''.join(c for c in guess.strip().lower() if c.isalpha())
       return sanitized
   ```

3. **Prompt Injection Prevention**
   ```python
   def _sanitize_for_analysis(self, text: str) -> str:
       # Check for injection patterns
       injection_patterns = [
           "ignore previous instructions",
           "system prompt",
           "act as",
           # ... more patterns
       ]
       
       for pattern in injection_patterns:
           if pattern in text.lower():
               return ""  # Return empty for suspicious input
       
       return text
   ```

### AWS Security Best Practices

- **IAM Least Privilege**: Each Lambda has minimal required permissions
- **Secrets Management**: API keys stored in AWS Secrets Manager
- **HTTPS Only**: All communications encrypted in transit
- **CORS Configuration**: Restrictive cross-origin policies

## Performance Considerations

### Scalability Design

1. **Stateless Agents**: No persistent state between requests
2. **Independent Scaling**: Each agent can scale independently
3. **Session Isolation**: Concurrent sessions don't interfere
4. **Efficient Communication**: Minimal A2A message overhead

### Optimization Strategies

1. **Frontend Optimization**
   - Bundle splitting and lazy loading
   - CloudFront caching for static assets
   - Optimized Vue.js build configuration

2. **Backend Optimization**
   - Lambda cold start mitigation
   - Efficient Python imports
   - Connection pooling for HTTP clients

3. **Communication Optimization**
   - A2A message compression
   - Timeout optimization
   - Fallback strategy implementation

## Error Handling Strategy

### Graceful Degradation

```python
async def request_hint_analysis(self, guess: str, target_word: str) -> str:
    # Try A2A communication first
    try:
        return await self._try_a2a_communication(guess, target_word)
    except Exception as e:
        print(f"A2A communication failed: {e}")
    
    # Fallback to direct HTTP
    try:
        return await self._try_direct_http_communication(guess, target_word)
    except Exception as e:
        print(f"Direct HTTP failed: {e}")
    
    # Final fallback to basic hint
    return self._generate_basic_hint(guess, target_word)
```

### Error Categories

1. **Communication Errors**: A2A protocol failures
2. **Validation Errors**: Invalid input data
3. **Service Errors**: External API failures
4. **System Errors**: Lambda timeouts or memory issues

## Testing Architecture

### Testing Pyramid

```
    ┌─────────────────┐
    │ Integration (15) │  ← End-to-end flows, A2A communication
    ├─────────────────┤
    │ Property (17)   │  ← Universal correctness properties
    ├─────────────────┤
    │ Unit Tests (69) │  ← Specific examples and edge cases
    └─────────────────┘
```

### Property-Based Testing

```python
@given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), 
               min_size=1, max_size=20))
def test_property_2_synonym_validation_consistency(self, guess):
    """
    For any guess and target word combination, validation should be 
    consistent and deterministic across multiple calls.
    """
    result1 = self.agent.validate_guess(guess, "happy", synonyms)
    result2 = self.agent.validate_guess(guess, "happy", synonyms)
    result3 = self.agent.validate_guess(guess, "happy", synonyms)
    
    assert result1 == result2 == result3
```

## Deployment Architecture

### Infrastructure as Code

```yaml
# SAM Template Structure
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  GameBuilderFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.13
      Handler: game_builder_agent.lambda_handler
      FunctionUrlConfig:
        AuthType: NONE
        Cors:
          AllowOrigins: ["*"]
          AllowMethods: ["GET", "POST", "OPTIONS"]
```

### Deployment Pipeline

1. **Build Phase**: SAM build compiles and packages functions
2. **Test Phase**: Comprehensive test suite execution
3. **Deploy Phase**: CloudFormation stack updates
4. **Verification Phase**: Health checks and integration tests

## Monitoring and Observability

### CloudWatch Integration

- **Metrics**: Lambda invocations, duration, errors
- **Logs**: Structured logging with correlation IDs
- **Alarms**: Error rate and latency thresholds
- **Dashboards**: Real-time system health visualization

### Logging Strategy

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def submit_guess(self, request: GuessRequest) -> GuessResponse:
    logger.info(f"Processing guess for session {request.session_id}")
    
    try:
        # Process guess
        result = self._process_guess(request)
        logger.info(f"Guess processed successfully: {result.success}")
        return result
    except Exception as e:
        logger.error(f"Error processing guess: {e}")
        raise
```

## Future Enhancements

### Potential Improvements

1. **Additional Agents**: Word difficulty analyzer, player progress tracker
2. **Enhanced A2A**: Streaming responses, batch processing
3. **Advanced Features**: Multiplayer support, leaderboards
4. **Performance**: Caching layers, database integration
5. **Analytics**: Player behavior tracking, game analytics

### Scalability Considerations

- **Database Integration**: For persistent game history
- **Caching Layer**: Redis for session management
- **Load Balancing**: Multiple agent instances
- **Geographic Distribution**: Multi-region deployment

---

This architecture demonstrates modern multi-agent system design principles while maintaining simplicity and educational value. The clear separation of concerns, robust error handling, and comprehensive testing make it an excellent reference for building scalable agent-based applications.