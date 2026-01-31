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
}

/**
 * Default configuration for the Game Service
 */
const DEFAULT_CONFIG: GameServiceConfig = {
  baseUrl: import.meta.env.VITE_GAME_BUILDER_URL || 'http://localhost:3000',
  timeout: 10000, // 10 seconds
  retryAttempts: 3,
  retryDelay: 1000 // 1 second
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

  constructor(config: Partial<GameServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Start a new game session
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
      
      return response
    } catch (error) {
      throw this.handleError('Failed to start new game', error)
    }
  }

  /**
   * Submit a player's guess
   */
  async submitGuess(sessionId: string, guess: string): Promise<GuessResponse> {
    // Validate input
    if (!sessionId) {
      throw new GameServiceError('Session ID is required')
    }
    if (!guess || !guess.trim()) {
      throw new GameServiceError('Guess cannot be empty')
    }

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
      
      return response
    } catch (error) {
      throw this.handleError('Failed to submit guess', error)
    }
  }

  /**
   * Give up the current game
   */
  async giveUp(sessionId: string): Promise<GiveUpResponse> {
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
      
      return response
    } catch (error) {
      throw this.handleError('Failed to give up game', error)
    }
  }

  /**
   * Make HTTP request with retry logic and error handling
   */
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit,
    attempt: number = 1
  ): Promise<T> {
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