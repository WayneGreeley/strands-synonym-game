import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import GameBoard from './GameBoard.vue'
import type { GameState } from '../types/game'

describe('GameBoard Component', () => {
  let wrapper: any
  
  const mockGameState: GameState = {
    targetWord: 'happy',
    synonyms: [
      { word: null, letterCount: 6, found: false },
      { word: 'glad', letterCount: 4, found: true },
      { word: null, letterCount: 8, found: false },
      { word: null, letterCount: 7, found: false }
    ],
    guessCount: 5,
    status: 'active',
    guessedWords: ['sad', 'glad', 'angry']
  }

  beforeEach(() => {
    wrapper = mount(GameBoard, {
      props: {
        gameState: mockGameState,
        isLoading: false
      }
    })
  })

  describe('Component Rendering', () => {
    it('should render target word correctly', () => {
      // Given: A game state with target word
      // When: Component is rendered
      // Then: Target word should be displayed
      const targetWordElement = wrapper.find('.target-word')
      expect(targetWordElement.exists()).toBe(true)
      expect(targetWordElement.text()).toBe('happy')
    })

    it('should render four synonym slots', () => {
      // Given: A game state with 4 synonym slots
      // When: Component is rendered
      // Then: Should display exactly 4 synonym slots
      const synonymSlots = wrapper.findAll('.synonym-slot')
      expect(synonymSlots).toHaveLength(4)
    })

    it('should display found synonyms correctly', () => {
      // Given: A game state with one found synonym
      // When: Component is rendered
      // Then: Found synonym should be displayed with correct styling
      const foundSlots = wrapper.findAll('.synonym-slot.found')
      expect(foundSlots).toHaveLength(1)
      
      const foundWord = wrapper.find('.found-word')
      expect(foundWord.exists()).toBe(true)
      expect(foundWord.text()).toBe('glad')
    })

    it('should display letter counts for unfound synonyms', () => {
      // Given: A game state with unfound synonyms
      // When: Component is rendered
      // Then: Should show letter counts for unfound slots
      const letterCounts = wrapper.findAll('.letter-count')
      expect(letterCounts).toHaveLength(3) // 3 unfound synonyms
      expect(letterCounts[0].text()).toBe('6 letters')
    })

    it('should display guess counter', () => {
      // Given: A game state with guess count
      // When: Component is rendered
      // Then: Should display current guess count
      const guessCounter = wrapper.find('.guess-counter')
      expect(guessCounter.exists()).toBe(true)
      expect(guessCounter.text()).toBe('Guesses: 5')
    })
  })

  describe('Input Validation', () => {
    it('should validate single word input', async () => {
      // Given: Component is rendered
      const input = wrapper.find('.guess-input')
      
      // When: User enters multiple words
      await input.setValue('hello world')
      await input.trigger('input')
      
      // Then: Should show validation error
      const errorMessage = wrapper.find('.input-error')
      expect(errorMessage.exists()).toBe(true)
      expect(errorMessage.text()).toBe('Please enter only one word')
    })

    it('should validate alphabetic characters only', async () => {
      // Given: Component is rendered
      const input = wrapper.find('.guess-input')
      
      // When: User enters non-alphabetic characters
      await input.setValue('hello123')
      await input.trigger('input')
      
      // Then: Should show validation error
      const errorMessage = wrapper.find('.input-error')
      expect(errorMessage.exists()).toBe(true)
      expect(errorMessage.text()).toBe('Please use only letters')
    })

    it('should validate input length', async () => {
      // Given: Component is rendered
      const input = wrapper.find('.guess-input')
      
      // When: User enters very long input
      const longInput = 'a'.repeat(51)
      await input.setValue(longInput)
      await input.trigger('input')
      
      // Then: Should show validation error
      const errorMessage = wrapper.find('.input-error')
      expect(errorMessage.exists()).toBe(true)
      expect(errorMessage.text()).toBe('Word is too long')
    })

    it('should clear validation error for valid input', async () => {
      // Given: Component has validation error
      const input = wrapper.find('.guess-input')
      await input.setValue('hello world')
      await input.trigger('input')
      expect(wrapper.find('.input-error').exists()).toBe(true)
      
      // When: User enters valid input
      await input.setValue('hello')
      await input.trigger('input')
      
      // Then: Validation error should be cleared
      expect(wrapper.find('.input-error').exists()).toBe(false)
    })
  })

  describe('User Interactions', () => {
    it('should emit submitGuess event when form is submitted', async () => {
      // Given: Component is rendered with valid input
      const input = wrapper.find('.guess-input')
      const submitBtn = wrapper.find('.submit-btn')
      
      await input.setValue('joyful')
      
      // When: User clicks submit button
      await submitBtn.trigger('click')
      
      // Then: Should emit submitGuess event with correct guess
      expect(wrapper.emitted('submitGuess')).toBeTruthy()
      expect(wrapper.emitted('submitGuess')[0]).toEqual(['joyful'])
    })

    it('should emit submitGuess event on Enter key press', async () => {
      // Given: Component is rendered with valid input
      const input = wrapper.find('.guess-input')
      
      await input.setValue('cheerful')
      
      // When: User presses Enter key
      await input.trigger('keyup.enter')
      
      // Then: Should emit submitGuess event
      expect(wrapper.emitted('submitGuess')).toBeTruthy()
      expect(wrapper.emitted('submitGuess')[0]).toEqual(['cheerful'])
    })

    it('should not submit empty or invalid guesses', async () => {
      // Given: Component is rendered
      const input = wrapper.find('.guess-input')
      const submitBtn = wrapper.find('.submit-btn')
      
      // When: User tries to submit empty guess
      await input.setValue('')
      await submitBtn.trigger('click')
      
      // Then: Should not emit submitGuess event
      expect(wrapper.emitted('submitGuess')).toBeFalsy()
      
      // When: User tries to submit invalid guess
      await input.setValue('hello world')
      await input.trigger('input')
      await submitBtn.trigger('click')
      
      // Then: Should still not emit submitGuess event
      expect(wrapper.emitted('submitGuess')).toBeFalsy()
    })

    it('should emit giveUp event when give up button is clicked', async () => {
      // Given: Component is rendered
      // Mock window.confirm to return true
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
      
      const giveUpBtn = wrapper.find('.give-up-btn')
      
      // When: User clicks give up button and confirms
      await giveUpBtn.trigger('click')
      
      // Then: Should emit giveUp event
      expect(wrapper.emitted('giveUp')).toBeTruthy()
      
      confirmSpy.mockRestore()
    })

    it('should not emit giveUp event when user cancels confirmation', async () => {
      // Given: Component is rendered
      // Mock window.confirm to return false
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
      
      const giveUpBtn = wrapper.find('.give-up-btn')
      
      // When: User clicks give up button but cancels
      await giveUpBtn.trigger('click')
      
      // Then: Should not emit giveUp event
      expect(wrapper.emitted('giveUp')).toBeFalsy()
      
      confirmSpy.mockRestore()
    })

    it('should emit startNewGame event when new game button is clicked', async () => {
      // Given: Component is rendered with completed game
      const completedGameState: GameState = {
        ...mockGameState,
        status: 'completed'
      }
      
      await wrapper.setProps({ gameState: completedGameState })
      
      const newGameBtn = wrapper.find('.new-game-btn')
      
      // When: User clicks new game button
      await newGameBtn.trigger('click')
      
      // Then: Should emit startNewGame event
      expect(wrapper.emitted('startNewGame')).toBeTruthy()
    })
  })

  describe('Game Status Display', () => {
    it('should show success message for completed game', async () => {
      // Given: A completed game state
      const completedGameState: GameState = {
        ...mockGameState,
        status: 'completed'
      }
      
      // When: Component is updated with completed state
      await wrapper.setProps({ gameState: completedGameState })
      
      // Then: Should display success message
      const successMessage = wrapper.find('.success-message')
      expect(successMessage.exists()).toBe(true)
      expect(successMessage.text()).toContain('Congratulations')
      expect(successMessage.text()).toContain('5 guesses')
    })

    it('should show give up message for given up game', async () => {
      // Given: A given up game state
      const givenUpGameState: GameState = {
        ...mockGameState,
        status: 'given-up'
      }
      
      // When: Component is updated with given up state
      await wrapper.setProps({ gameState: givenUpGameState })
      
      // Then: Should display give up message
      const giveUpMessage = wrapper.find('.give-up-message')
      expect(giveUpMessage.exists()).toBe(true)
      expect(giveUpMessage.text()).toBe('Game ended. Better luck next time!')
    })

    it('should hide input section for non-active games', async () => {
      // Given: A completed game state
      const completedGameState: GameState = {
        ...mockGameState,
        status: 'completed'
      }
      
      // When: Component is updated with completed state
      await wrapper.setProps({ gameState: completedGameState })
      
      // Then: Input section should be hidden
      const inputSection = wrapper.find('.input-section')
      expect(inputSection.exists()).toBe(false)
    })

    it('should show new game button for non-active games', async () => {
      // Given: A completed game state
      const completedGameState: GameState = {
        ...mockGameState,
        status: 'completed'
      }
      
      // When: Component is updated with completed state
      await wrapper.setProps({ gameState: completedGameState })
      
      // Then: New game button should be visible
      const newGameSection = wrapper.find('.new-game-section')
      expect(newGameSection.exists()).toBe(true)
    })
  })

  describe('Loading States', () => {
    it('should disable input and buttons when loading', async () => {
      // Given: Component is in loading state
      await wrapper.setProps({ isLoading: true })
      
      // When: Component is rendered
      // Then: Input and buttons should be disabled
      const input = wrapper.find('.guess-input')
      const submitBtn = wrapper.find('.submit-btn')
      const giveUpBtn = wrapper.find('.give-up-btn')
      
      expect(input.attributes('disabled')).not.toBeUndefined()
      expect(submitBtn.attributes('disabled')).not.toBeUndefined()
      expect(giveUpBtn.attributes('disabled')).not.toBeUndefined()
    })

    it('should show loading text on submit button when submitting', async () => {
      // Given: Component is in submitting state
      // Set isSubmitting via component's internal state
      const component = wrapper.vm
      component.isSubmitting = true
      await wrapper.vm.$nextTick()
      
      // When: Component is rendered
      // Then: Submit button should show loading text
      const submitBtn = wrapper.find('.submit-btn')
      expect(submitBtn.text()).toBe('Submitting...')
    })
  })

  describe('Message Display', () => {
    it('should display hint when provided', async () => {
      // Given: Component with updateDisplayMessages method
      const component = wrapper.vm
      
      // When: Hint is provided via updateDisplayMessages
      component.updateDisplayMessages('Try thinking of words related to emotions', undefined, false)
      await wrapper.vm.$nextTick()
      
      // Then: Hint should be displayed
      expect(wrapper.find('.hint-section').exists()).toBe(true)
      expect(wrapper.find('.hint-text').text()).toBe('Try thinking of words related to emotions')
    })

    it('should display success message', async () => {
      // Given: Component with updateDisplayMessages method
      const component = wrapper.vm
      
      // When: Success message is provided
      component.updateDisplayMessages(undefined, 'Correct! Great job!', true)
      await wrapper.vm.$nextTick()
      
      // Then: Success message should be displayed
      expect(wrapper.find('.game-message.success').exists()).toBe(true)
      expect(wrapper.find('.game-message').text()).toBe('Correct! Great job!')
    })

    it('should display error message', async () => {
      // Given: Component with updateDisplayMessages method
      const component = wrapper.vm
      
      // When: Error message is provided
      component.updateDisplayMessages(undefined, 'That is not a synonym', false)
      await wrapper.vm.$nextTick()
      
      // Then: Error message should be displayed
      expect(wrapper.find('.game-message.error').exists()).toBe(true)
      expect(wrapper.find('.game-message').text()).toBe('That is not a synonym')
    })
  })

  describe('Edge Cases', () => {
    it('should handle null game state gracefully', async () => {
      // Given: Component with null game state
      await wrapper.setProps({ gameState: null })
      
      // When: Component is rendered
      // Then: Should not crash and show empty state
      expect(wrapper.find('.target-word').text()).toBe('')
      expect(wrapper.findAll('.synonym-slot')).toHaveLength(0)
    })

    it('should handle empty synonym slots', async () => {
      // Given: Game state with empty synonyms array
      const emptyGameState: GameState = {
        ...mockGameState,
        synonyms: []
      }
      
      await wrapper.setProps({ gameState: emptyGameState })
      
      // When: Component is rendered
      // Then: Should handle empty synonyms gracefully
      expect(wrapper.findAll('.synonym-slot')).toHaveLength(0)
    })

    it('should clear input after successful submission', async () => {
      // Given: Component with input value
      const input = wrapper.find('.guess-input')
      await input.setValue('joyful')
      
      // When: Guess is submitted successfully
      await wrapper.find('.submit-btn').trigger('click')
      
      // Then: Input should be cleared
      expect(input.element.value).toBe('')
    })
  })
})