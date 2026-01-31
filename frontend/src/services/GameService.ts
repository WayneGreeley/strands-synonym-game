import type {
  StartGameRequest,
  StartGameResponse,
  GuessRequest,
  GuessResponse,
  GiveUpRequest,
  GiveUpResponse
} from '../types/game'

/**
 * Configuration for the Game Service
 */
interface GameServiceConfig {
  baseUrl: string
  timeout: number
  retryAttempts: number
  retryDelay: number
  rateLimitDelay: number
  maxRequestsPerMinute: number
}

/**
 * Default configuration for the Game Service
 */
const DEFAULT_CONFIG: GameServiceConfig = {
  baseUrl: import.meta.env.VITE_GAME_BUILDER_URL || 'http://localhost:3000',
  timeout: 10000, // 10 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
  rateLimitDelay: 1000, // 1 second delay between requests
  maxRequestsPerMinute: 60 // Maximum 60 requests per minute
}

/**
 * Custom error class for Game Service errors
 */
export class GameServiceError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: Error
  ) {
    super(message)
    this.name = 'GameServiceError'
  }
}

/**
 * Service class for communicating with the Game Builder Lambda function
 */
export class GameService {
  private config: GameServiceConfig
  private requestTimestamps: number[] = []
  private lastRequestTime: number = 0
  private currentSessionId: string | null = null
  private sessionStartTime: number | null = null
  private readonly SESSION_TIMEOUT_MS = 30 * 60 * 1000 // 30 minutes

  constructor(config: Partial<GameServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Start a new game session with session management
   */
  async startNewGame(): Promise<StartGameResponse> {
    const request: StartGameRequest = {}
    
    try {
      const response = await this.makeRequest<StartGameResponse>('/start-game', {
        method: 'POST',
        body: JSON.stringify(request)
      })
      
      // Validate response structure
      this.validateStartGameResponse(response)
      
      // Track session for timeout management
      this.currentSessionId = response.sessionId
      this.sessionStartTime = Date.now()
      
      return response
    } catch (error) {
      throw this.handleError('Failed to start new game', error)
    }
  }

  /**
   * Submit a player's guess with session validation
   */
  async submitGuess(sessionId: string, guess: string): Promise<GuessResponse> {
    // Check for session timeout
    if (this.isSessionExpired(sessionId)) {
      throw new GameServiceError('Session has expired. Please start a new game.')
    }

    // Comprehensive input validation
    this.validateGuessInput(sessionId, guess)

    const request: GuessRequest = {
      sessionId,
      guess: guess.trim()
    }

    try {
      const response = await this.makeRequest<GuessResponse>('/submit-guess', {
        method: 'POST',
        body: JSON.stringify(request)
      })
      
      // Validate response structure
      this.validateGuessResponse(response)
      
      // Handle session-related errors
      if (!response.success && this.isSessionError(response.message)) {
        this.clearSession()
        throw new GameServiceError('Session is no longer valid. Please start a new game.')
      }
      
      return response
    } catch (error) {
      // Handle session errors specifically
      if (error instanceof GameServiceError && error.message.includes('session')) {
        this.clearSession()
      }
      throw this.handleError('Failed to submit guess', error)
    }
  }

  /**
   * Validate guess input before sending to backend
   */
  private validateGuessInput(sessionId: string, guess: string): void {
    // Session ID validation
    if (!sessionId || typeof sessionId !== 'string') {
      throw new GameServiceError('Session ID is required')
    }
    
    if (sessionId.trim().length === 0) {
      throw new GameServiceError('Session ID cannot be empty')
    }

    // Guess validation
    if (guess === null || guess === undefined) {
      throw new GameServiceError('Guess is required')
    }
    
    if (typeof guess !== 'string') {
      throw new GameServiceError('Guess must be a string')
    }
    
    const trimmed = guess.trim()
    
    // Empty input check
    if (!trimmed) {
      throw new GameServiceError('Guess cannot be empty')
    }
    
    // Multiple words check
    if (trimmed.includes(' ')) {
      throw new GameServiceError('Please enter only one word')
    }
    
    // Length validation
    if (guess.length > 50) {
      throw new GameServiceError('Input too long (maximum 50 characters)')
    }
    
    // Character validation - allow only letters
    if (!/^[a-zA-Z\s]*$/.test(guess)) {
      throw new GameServiceError('Please use only letters')
    }
    
    // Minimum length after sanitization
    const lettersOnly = guess.replace(/[^a-zA-Z]/g, '')
    if (lettersOnly.length < 1) {
      throw new GameServiceError('Word must contain at least one letter')
    }
    
    // Check for suspicious patterns
    const suspiciousPatterns = [
      /[<>{}[\]\\]/,  // HTML/XML/JSON brackets
      /[;|&$`]/,      // Shell command separators
      /(script|javascript|eval|function)/i,  // Script-related keywords
      /(select|insert|update|delete|drop)/i,  // SQL keywords
    ]
    
    for (const pattern of suspiciousPatterns) {
      if (pattern.test(guess)) {
        throw new GameServiceError('Invalid characters detected in input')
      }
    }
  }

  /**
   * Give up the current game with session validation
   */
  async giveUp(sessionId: string): Promise<GiveUpResponse> {
    // Check for session timeout
    if (this.isSessionExpired(sessionId)) {
      throw new GameServiceError('Session has expired. Please start a new game.')
    }

    if (!sessionId) {
      throw new GameServiceError('Session ID is required')
    }

    const request: GiveUpRequest = {
      sessionId
    }

    try {
      const response = await this.makeRequest<GiveUpResponse>('/give-up', {
        method: 'POST',
        body: JSON.stringify(request)
      })
      
      // Validate response structure
      this.validateGiveUpResponse(response)
      
      // Clear session after giving up
      this.clearSession()
      
      return response
    } catch (error) {
      // Handle session errors specifically
      if (error instanceof GameServiceError && error.message.includes('session')) {
        this.clearSession()
      }
      throw this.handleError('Failed to give up game', error)
    }
  }

  /**
   * Check if current session has expired
   */
  private isSessionExpired(sessionId: string): boolean {
    if (!this.currentSessionId || !this.sessionStartTime) {
      return false // No session to expire
    }
    
    if (sessionId !== this.currentSessionId) {
      return false // Different session, let server handle it
    }
    
    const now = Date.now()
    return (now - this.sessionStartTime) > this.SESSION_TIMEOUT_MS
  }

  /**
   * Check if error message indicates a session problem
   */
  private isSessionError(message: string): boolean {
    const sessionErrorPatterns = [
      /session.*not.*found/i,
      /invalid.*session/i,
      /session.*expired/i,
      /session.*timeout/i,
      /session.*invalid/i
    ]
    
    return sessionErrorPatterns.some(pattern => pattern.test(message))
  }

  /**
   * Clear current session tracking
   */
  private clearSession(): void {
    this.currentSessionId = null
    this.sessionStartTime = null
  }

  /**
   * Get current session info for debugging
   */
  getCurrentSessionInfo(): { sessionId: string | null; startTime: number | null; isExpired: boolean } {
    return {
      sessionId: this.currentSessionId,
      startTime: this.sessionStartTime,
      isExpired: this.currentSessionId ? this.isSessionExpired(this.currentSessionId) : false
    }
  }

  /**
   * Handle browser refresh/navigation scenarios
   */
  handlePageRefresh(): void {
    // Clear session tracking on page refresh since server sessions are in-memory
    this.clearSession()
  }

  /**
   * Make HTTP request with retry logic and error handling
   */
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit,
    attempt: number = 1
  ): Promise<T> {
    // Apply rate limiting
    await this.applyRateLimit()
    
    const url = `${this.config.baseUrl}${endpoint}`
    
    // Set default headers
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }

    try {
      // Create AbortController for timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout)

      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      // Handle HTTP errors
      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`
        
        try {
          const errorData = JSON.parse(errorText)
          if (errorData.error) {
            errorMessage = errorData.error
          }
        } catch {
          // Use default error message if JSON parsing fails
        }

        throw new GameServiceError(errorMessage, response.status)
      }

      // Parse JSON response
      const data = await response.json()
      return data as T

    } catch (error) {
      // Handle timeout and network errors
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new GameServiceError('Request timeout', 408, error as Error)
      }

      if (error instanceof GameServiceError) {
        throw error
      }

      // Retry logic for network errors
      if (attempt < this.config.retryAttempts) {
        console.warn(`Request failed (attempt ${attempt}/${this.config.retryAttempts}), retrying...`, error)
        
        // Wait before retrying
        await this.delay(this.config.retryDelay * attempt)
        
        return this.makeRequest<T>(endpoint, options, attempt + 1)
      }

      throw new GameServiceError('Network error', undefined, error as Error)
    }
  }

  /**
   * Apply rate limiting to prevent abuse
   */
  private async applyRateLimit(): Promise<void> {
    const now = Date.now()
    
    // Clean old timestamps (older than 1 minute)
    this.requestTimestamps = this.requestTimestamps.filter(
      timestamp => now - timestamp < 60000
    )
    
    // Check if we've exceeded the rate limit
    if (this.requestTimestamps.length >= this.config.maxRequestsPerMinute) {
      const oldestRequest = this.requestTimestamps[0]
      const waitTime = 60000 - (now - oldestRequest)
      if (waitTime > 0) {
        await this.delay(waitTime)
      }
    }
    
    // Ensure minimum delay between requests
    const timeSinceLastRequest = now - this.lastRequestTime
    if (timeSinceLastRequest < this.config.rateLimitDelay) {
      await this.delay(this.config.rateLimitDelay - timeSinceLastRequest)
    }
    
    // Record this request
    this.requestTimestamps.push(Date.now())
    this.lastRequestTime = Date.now()
  }

  /**
   * Validate StartGameResponse structure
   */
  private validateStartGameResponse(response: any): asserts response is StartGameResponse {
    if (!response || typeof response !== 'object') {
      throw new GameServiceError('Invalid response format')
    }

    if (!response.sessionId || typeof response.sessionId !== 'string') {
      throw new GameServiceError('Invalid session ID in response')
    }

    if (!response.targetWord || typeof response.targetWord !== 'string') {
      throw new GameServiceError('Invalid target word in response')
    }

    if (!Array.isArray(response.synonymSlots) || response.synonymSlots.length !== 4) {
      throw new GameServiceError('Invalid synonym slots in response')
    }

    // Validate each synonym slot
    for (const slot of response.synonymSlots) {
      if (!slot || typeof slot.letterCount !== 'number' || slot.letterCount <= 0) {
        throw new GameServiceError('Invalid synonym slot structure')
      }
    }

    if (response.status !== 'active') {
      throw new GameServiceError('Invalid game status in response')
    }
  }

  /**
   * Validate GuessResponse structure
   */
  private validateGuessResponse(response: any): asserts response is GuessResponse {
    if (!response || typeof response !== 'object') {
      throw new GameServiceError('Invalid response format')
    }

    if (typeof response.success !== 'boolean') {
      throw new GameServiceError('Invalid success field in response')
    }

    if (!response.message || typeof response.message !== 'string') {
      throw new GameServiceError('Invalid message field in response')
    }

    if (response.hint !== undefined && response.hint !== null && typeof response.hint !== 'string') {
      throw new GameServiceError('Invalid hint field in response')
    }

    if (!response.gameState || typeof response.gameState !== 'object') {
      throw new GameServiceError('Invalid game state in response')
    }

    // Validate game state structure
    this.validateGameState(response.gameState)
  }

  /**
   * Validate GiveUpResponse structure
   */
  private validateGiveUpResponse(response: any): asserts response is GiveUpResponse {
    if (!response || typeof response !== 'object') {
      throw new GameServiceError('Invalid response format')
    }

    if (!response.message || typeof response.message !== 'string') {
      throw new GameServiceError('Invalid message field in response')
    }

    if (!response.gameState || typeof response.gameState !== 'object') {
      throw new GameServiceError('Invalid game state in response')
    }

    // Validate game state structure
    this.validateGameState(response.gameState)
  }

  /**
   * Validate game state structure
   */
  private validateGameState(gameState: any): void {
    if (!gameState.targetWord || typeof gameState.targetWord !== 'string') {
      throw new GameServiceError('Invalid target word in game state')
    }

    if (!Array.isArray(gameState.synonyms) || gameState.synonyms.length !== 4) {
      throw new GameServiceError('Invalid synonyms array in game state')
    }

    // Validate each synonym
    for (const synonym of gameState.synonyms) {
      if (!synonym || typeof synonym !== 'object') {
        throw new GameServiceError('Invalid synonym structure in game state')
      }

      if (typeof synonym.letterCount !== 'number' || synonym.letterCount <= 0) {
        throw new GameServiceError('Invalid letter count in synonym')
      }

      if (typeof synonym.found !== 'boolean') {
        throw new GameServiceError('Invalid found field in synonym')
      }

      if (synonym.word !== null && typeof synonym.word !== 'string') {
        throw new GameServiceError('Invalid word field in synonym')
      }
    }

    if (typeof gameState.guessCount !== 'number' || gameState.guessCount < 0) {
      throw new GameServiceError('Invalid guess count in game state')
    }

    if (!['active', 'completed', 'given-up'].includes(gameState.status)) {
      throw new GameServiceError('Invalid status in game state')
    }

    if (!Array.isArray(gameState.guessedWords)) {
      throw new GameServiceError('Invalid guessed words array in game state')
    }
  }

  /**
   * Handle and format errors
   */
  private handleError(message: string, error: unknown): GameServiceError {
    if (error instanceof GameServiceError) {
      return error
    }

    if (error instanceof Error) {
      return new GameServiceError(`${message}: ${error.message}`, undefined, error)
    }

    return new GameServiceError(`${message}: Unknown error`, undefined, undefined)
  }

  /**
   * Utility method to create delays for retry logic
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Update configuration
   */
  updateConfig(newConfig: Partial<GameServiceConfig>): void {
    this.config = { ...this.config, ...newConfig }
  }

  /**
   * Get current configuration
   */
  getConfig(): GameServiceConfig {
    return { ...this.config }
  }
}

// Export singleton instance
export const gameService = new GameService()

// Export class for testing and custom instances
export default GameService