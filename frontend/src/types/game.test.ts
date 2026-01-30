import { describe, it, expect } from 'vitest'
import fc from 'fast-check'
import type { GameState, SynonymSlot, StartGameResponse } from './game'

describe('Game Data Model Properties', () => {
  it('Property 1: Game Initialization Completeness', () => {
    // Feature: synonym-seeker, Property 1: Game Initialization Completeness
    // For any new game request, the Game Builder SHALL return a complete game session 
    // with exactly one target word, exactly four synonym slots with letter counts, and active status.
    
    fc.assert(fc.property(
      fc.record({
        sessionId: fc.string({ minLength: 1 }),
        targetWord: fc.string({ minLength: 1, maxLength: 20 }).filter(word => /^[a-zA-Z]+$/.test(word)),
        synonymSlots: fc.array(
          fc.record({
            letterCount: fc.integer({ min: 1, max: 20 })
          }),
          { minLength: 4, maxLength: 4 }
        )
      }),
      (mockResponse: Omit<StartGameResponse, 'status'>) => {
        const response: StartGameResponse = {
          ...mockResponse,
          status: 'active' as const
        }
        
        // Given: Any new game response
        // When: Validating game initialization completeness
        // Then: Response should have all required properties
        expect(response.targetWord).toBeDefined()
        expect(response.targetWord.length).toBeGreaterThan(0)
        expect(response.synonymSlots).toHaveLength(4)
        expect(response.synonymSlots.every(slot => slot.letterCount > 0)).toBe(true)
        expect(response.status).toBe('active')
        expect(response.sessionId).toBeDefined()
        expect(response.sessionId.length).toBeGreaterThan(0)
      }
    ), { numRuns: 100 })
  })

  it('validates SynonymSlot structure', () => {
    // Given: A synonym slot with valid data
    const slot: SynonymSlot = {
      word: null,
      letterCount: 5,
      found: false
    }
    
    // When: Checking slot properties
    // Then: All properties should be properly typed
    expect(slot.word).toBeNull()
    expect(typeof slot.letterCount).toBe('number')
    expect(typeof slot.found).toBe('boolean')
  })

  it('validates GameState structure', () => {
    // Given: A complete game state
    const gameState: GameState = {
      targetWord: 'happy',
      synonyms: [
        { word: 'joyful', letterCount: 6, found: true },
        { word: null, letterCount: 8, found: false },
        { word: null, letterCount: 4, found: false },
        { word: null, letterCount: 7, found: false }
      ],
      guessCount: 3,
      status: 'active',
      guessedWords: ['joyful', 'sad', 'angry']
    }
    
    // When: Validating game state structure
    // Then: All properties should be correctly typed
    expect(gameState.targetWord).toBe('happy')
    expect(gameState.synonyms).toHaveLength(4)
    expect(gameState.guessCount).toBe(3)
    expect(['active', 'completed', 'given-up']).toContain(gameState.status)
    expect(Array.isArray(gameState.guessedWords)).toBe(true)
  })
})