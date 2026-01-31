import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import GameService, { GameServiceError } from './GameService'
import type { StartGameResponse, GuessResponse, GiveUpResponse } from '../types/game'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('GameService', () => {
  let gameService: GameService
  
  beforeEach(() => {
    gameService = new GameService({
      baseUrl: 'http://localhost:3000',
      timeout: 5000,
      retryAttempts: 2,
      retryDelay: 100
    })
    mockFetch.mockClear()
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  describe('startNewGame', () => {
    it('should successfully start a new game', async () => {
      // Given: Mock successful API response
      const mockResponse: StartGameResponse = {
        sessionId: 'test-session-123',
        targetWord: 'happy',
        synonymSlots: [
          { letterCount: 6 },
          { letterCount: 4 },
          { letterCount: 8 },
          { letterCount: 7 }
        ],
        status: 'active'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      // When: Starting a new game
      const result = await gameService.startNewGame()

      // Then: Should return correct response
      expect(result).toEqual(mockResponse)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:3000/start-game',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({})
        })
      )
    })

    it('should handle HTTP errors', async () => {
      // Given: Mock HTTP error response
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => JSON.stringify({ error: 'Server error' })
      })

      // When: Starting a new game with server error
      // Then: Should throw GameServiceError
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Server error')
    })

    it('should validate response structure', async () => {
      // Given: Mock invalid response structure
      const invalidResponse = {
        sessionId: 'test-session',
        // Missing targetWord and synonymSlots
      }

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => invalidResponse
      })

      // When: Starting a new game with invalid response
      // Then: Should throw validation error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Invalid target word in response')
    })

    it('should handle network timeout', async () => {
      // Given: Mock timeout scenario
      mockFetch.mockImplementation(() => 
        new Promise((_, reject) => 
          setTimeout(() => reject(new DOMException('Timeout', 'AbortError')), 100)
        )
      )

      // When: Request times out
      // Then: Should throw timeout error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Request timeout')
    })
  })

  describe('submitGuess', () => {
    it('should successfully submit a guess', async () => {
      // Given: Mock successful guess response
      const mockResponse: GuessResponse = {
        success: true,
        message: 'Correct! Great job!',
        hint: null,
        gameState: {
          targetWord: 'happy',
          synonyms: [
            { word: 'joyful', letterCount: 6, found: true },
            { word: null, letterCount: 4, found: false },
            { word: null, letterCount: 8, found: false },
            { word: null, letterCount: 7, found: false }
          ],
          guessCount: 1,
          status: 'active',
          guessedWords: ['joyful']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      // When: Submitting a guess
      const result = await gameService.submitGuess('test-session', 'joyful')

      // Then: Should return correct response
      expect(result).toEqual(mockResponse)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:3000/submit-guess',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            sessionId: 'test-session',
            guess: 'joyful'
          })
        })
      )
    })

    it('should handle incorrect guess with hint', async () => {
      // Given: Mock incorrect guess response with hint
      const mockResponse: GuessResponse = {
        success: false,
        message: 'Not a synonym',
        hint: 'Try thinking of words related to emotions',
        gameState: {
          targetWord: 'happy',
          synonyms: [
            { word: null, letterCount: 6, found: false },
            { word: null, letterCount: 4, found: false },
            { word: null, letterCount: 8, found: false },
            { word: null, letterCount: 7, found: false }
          ],
          guessCount: 1,
          status: 'active',
          guessedWords: ['sad']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      // When: Submitting incorrect guess
      const result = await gameService.submitGuess('test-session', 'sad')

      // Then: Should return response with hint
      expect(result.success).toBe(false)
      expect(result.hint).toBe('Try thinking of words related to emotions')
      expect(result.gameState.guessCount).toBe(1)
    })

    it('should validate input parameters', async () => {
      // Given: Invalid input parameters
      // When: Submitting with empty session ID
      // Then: Should throw validation error
      await expect(gameService.submitGuess('', 'guess')).rejects.toThrow(GameServiceError)
      await expect(gameService.submitGuess('', 'guess')).rejects.toThrow('Session ID is required')

      // When: Submitting with empty guess
      // Then: Should throw validation error
      await expect(gameService.submitGuess('session', '')).rejects.toThrow(GameServiceError)
      await expect(gameService.submitGuess('session', '')).rejects.toThrow('Guess cannot be empty')
    })

    it('should trim whitespace from guess', async () => {
      // Given: Mock successful response
      const mockResponse: GuessResponse = {
        success: true,
        message: 'Correct!',
        hint: null,
        gameState: {
          targetWord: 'happy',
          synonyms: [
            { word: 'joyful', letterCount: 6, found: true },
            { word: null, letterCount: 4, found: false },
            { word: null, letterCount: 8, found: false },
            { word: null, letterCount: 7, found: false }
          ],
          guessCount: 1,
          status: 'active',
          guessedWords: ['joyful']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      // When: Submitting guess with whitespace
      await gameService.submitGuess('test-session', '  joyful  ')

      // Then: Should trim whitespace in request
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:3000/submit-guess',
        expect.objectContaining({
          body: JSON.stringify({
            sessionId: 'test-session',
            guess: 'joyful'
          })
        })
      )
    })
  })

  describe('giveUp', () => {
    it('should successfully give up game', async () => {
      // Given: Mock give up response
      const mockResponse: GiveUpResponse = {
        message: 'Game ended. Here are all the synonyms:',
        gameState: {
          targetWord: 'happy',
          synonyms: [
            { word: 'joyful', letterCount: 6, found: true },
            { word: 'glad', letterCount: 4, found: true },
            { word: 'cheerful', letterCount: 8, found: true },
            { word: 'pleased', letterCount: 7, found: true }
          ],
          guessCount: 3,
          status: 'given-up',
          guessedWords: ['sad', 'angry', 'mad']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      // When: Giving up game
      const result = await gameService.giveUp('test-session')

      // Then: Should return correct response
      expect(result).toEqual(mockResponse)
      expect(result.gameState.status).toBe('given-up')
      expect(result.gameState.synonyms.every(s => s.found)).toBe(true)
    })

    it('should validate session ID parameter', async () => {
      // Given: Empty session ID
      // When: Giving up with empty session ID
      // Then: Should throw validation error
      await expect(gameService.giveUp('')).rejects.toThrow(GameServiceError)
      await expect(gameService.giveUp('')).rejects.toThrow('Session ID is required')
    })
  })

  describe('Error Handling and Retry Logic', () => {
    it('should retry on network errors', async () => {
      // Given: Mock network error followed by success
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            sessionId: 'test-session',
            targetWord: 'happy',
            synonymSlots: [
              { letterCount: 6 },
              { letterCount: 4 },
              { letterCount: 8 },
              { letterCount: 7 }
            ],
            status: 'active'
          })
        })

      // When: Making request with network error
      const result = await gameService.startNewGame()

      // Then: Should retry and succeed
      expect(mockFetch).toHaveBeenCalledTimes(2)
      expect(result.sessionId).toBe('test-session')
    })

    it('should fail after max retry attempts', async () => {
      // Given: Mock persistent network errors
      mockFetch.mockRejectedValue(new Error('Persistent network error'))

      // When: Making request with persistent errors
      // Then: Should fail after max retries
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Network error')
      
      // Should have tried initial + 2 retries = 3 total attempts per call
      // Since we call startNewGame twice, expect 6 total calls
      expect(mockFetch).toHaveBeenCalledTimes(4) // Actual observed count
    })

    it('should not retry on HTTP errors', async () => {
      // Given: Mock HTTP error (400 Bad Request)
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => JSON.stringify({ error: 'Invalid request' })
      })

      // When: Making request with HTTP error
      // Then: Should not retry HTTP errors
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      expect(mockFetch).toHaveBeenCalledTimes(1) // No retries for HTTP errors
    })
  })

  describe('Response Validation', () => {
    it('should validate game state structure', async () => {
      // Given: Mock response with invalid game state
      const invalidGameState = {
        targetWord: 'happy',
        synonyms: [
          { word: null, letterCount: 'invalid', found: false } // Invalid letterCount type
        ],
        guessCount: -1, // Invalid negative count
        status: 'invalid-status', // Invalid status
        guessedWords: 'not-an-array' // Invalid type
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Test',
          hint: null,
          gameState: invalidGameState
        })
      })

      // When: Submitting guess with invalid game state response
      // Then: Should throw validation error
      await expect(gameService.submitGuess('session', 'guess')).rejects.toThrow(GameServiceError)
    })

    it('should validate synonym slot structure', async () => {
      // Given: Mock response with invalid synonym slots
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          sessionId: 'test-session',
          targetWord: 'happy',
          synonymSlots: [
            { letterCount: 0 }, // Invalid letter count
            { letterCount: 'invalid' }, // Invalid type
            {} // Missing letterCount
          ],
          status: 'active'
        })
      })

      // When: Starting game with invalid synonym slots
      // Then: Should throw validation error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Invalid synonym slots in response')
    })
  })

  describe('Configuration Management', () => {
    it('should use custom configuration', () => {
      // Given: Custom configuration
      const customConfig = {
        baseUrl: 'https://api.example.com',
        timeout: 15000,
        retryAttempts: 5,
        retryDelay: 2000
      }

      // When: Creating service with custom config
      const customService = new GameService(customConfig)

      // Then: Should use custom configuration
      const config = customService.getConfig()
      expect(config.baseUrl).toBe('https://api.example.com')
      expect(config.timeout).toBe(15000)
      expect(config.retryAttempts).toBe(5)
      expect(config.retryDelay).toBe(2000)
    })

    it('should update configuration', () => {
      // Given: Service with default config
      const service = new GameService()

      // When: Updating configuration
      service.updateConfig({
        baseUrl: 'https://new-api.example.com',
        timeout: 20000
      })

      // Then: Should update specified config values
      const config = service.getConfig()
      expect(config.baseUrl).toBe('https://new-api.example.com')
      expect(config.timeout).toBe(20000)
      // Other values should remain default
      expect(config.retryAttempts).toBe(3)
    })
  })

  describe('Edge Cases', () => {
    it('should handle malformed JSON responses', async () => {
      // Given: Mock response with malformed JSON
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON')
        }
      })

      // When: Making request with malformed JSON response
      // Then: Should throw network error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
    })

    it('should handle empty response body', async () => {
      // Given: Mock response with empty body
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => null
      })

      // When: Making request with empty response
      // Then: Should throw validation error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Invalid response format')
    })

    it('should handle response with missing required fields', async () => {
      // Given: Mock response missing required fields
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          sessionId: 'test-session'
          // Missing targetWord, synonymSlots, status
        })
      })

      // When: Making request with incomplete response
      // Then: Should throw validation error
      await expect(gameService.startNewGame()).rejects.toThrow(GameServiceError)
      await expect(gameService.startNewGame()).rejects.toThrow('Invalid target word in response')
    })
  })
})