<template>
  <div id="app">
    <!-- Header -->
    <header class="app-header">
      <h1 class="app-title">SynonymSeeker</h1>
      <p class="app-subtitle">Multi-agent word puzzle game</p>
    </header>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading game...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <div class="error-message">
        <h3>Oops! Something went wrong</h3>
        <p>{{ error }}</p>
        <button @click="handleStartNewGame" class="retry-btn">
          Try Again
        </button>
      </div>
    </div>

    <!-- Game Board -->
    <GameBoard
      v-else
      ref="gameBoardRef"
      :game-state="gameState"
      :is-loading="isSubmitting"
      @submit-guess="handleSubmitGuess"
      @give-up="handleGiveUp"
      @start-new-game="handleStartNewGame"
    />

    <!-- Footer -->
    <footer class="app-footer">
      <p>Built with Vue.js and AWS Strands multi-agent system</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GameBoard from './components/GameBoard.vue'
import { gameService, GameServiceError } from './services/GameService'
import type { GameState } from './types/game'

// Reactive state
const gameState = ref<GameState | null>(null)
const isLoading = ref(false)
const isSubmitting = ref(false)
const error = ref<string>('')
const currentSessionId = ref<string>('')
const gameBoardRef = ref<InstanceType<typeof GameBoard> | null>(null)

// Game management methods
const handleStartNewGame = async () => {
  isLoading.value = true
  error.value = ''
  
  try {
    const response = await gameService.startNewGame()
    
    // Update session ID
    currentSessionId.value = response.sessionId
    
    // Create initial game state
    gameState.value = {
      targetWord: response.targetWord,
      synonyms: response.synonymSlots.map(slot => ({
        word: null,
        letterCount: slot.letterCount,
        found: false
      })),
      guessCount: 0,
      status: 'active',
      guessedWords: []
    }
    
    console.log('New game started:', response)
  } catch (err) {
    console.error('Failed to start new game:', err)
    if (err instanceof GameServiceError) {
      error.value = err.message
    } else {
      error.value = 'Failed to start new game. Please try again.'
    }
  } finally {
    isLoading.value = false
  }
}

const handleSubmitGuess = async (guess: string) => {
  if (!currentSessionId.value || !gameState.value) {
    error.value = 'No active game session'
    return
  }

  isSubmitting.value = true
  
  try {
    const response = await gameService.submitGuess(currentSessionId.value, guess)
    
    // Update game state with response
    gameState.value = {
      targetWord: response.gameState.targetWord,
      synonyms: response.gameState.synonyms.map(synonym => ({
        word: synonym.word,
        letterCount: synonym.letterCount,
        found: synonym.found
      })),
      guessCount: response.gameState.guessCount,
      status: response.gameState.status as 'active' | 'completed' | 'given-up',
      guessedWords: response.gameState.guessedWords
    }
    
    // Update display messages in GameBoard
    if (gameBoardRef.value) {
      gameBoardRef.value.updateDisplayMessages(
        response.hint || undefined,
        response.message,
        response.success
      )
    }
    
    console.log('Guess submitted:', response)
  } catch (err) {
    console.error('Failed to submit guess:', err)
    let errorMessage = 'Failed to submit guess. Please try again.'
    
    if (err instanceof GameServiceError) {
      errorMessage = err.message
    }
    
    // Show error message in GameBoard
    if (gameBoardRef.value) {
      gameBoardRef.value.updateDisplayMessages(
        undefined,
        errorMessage,
        false
      )
    }
  } finally {
    isSubmitting.value = false
  }
}

const handleGiveUp = async () => {
  if (!currentSessionId.value || !gameState.value) {
    error.value = 'No active game session'
    return
  }

  isSubmitting.value = true
  
  try {
    const response = await gameService.giveUp(currentSessionId.value)
    
    // Update game state with revealed synonyms
    gameState.value = {
      targetWord: response.gameState.targetWord,
      synonyms: response.gameState.synonyms.map(synonym => ({
        word: synonym.word,
        letterCount: synonym.letterCount,
        found: synonym.found
      })),
      guessCount: response.gameState.guessCount,
      status: response.gameState.status as 'active' | 'completed' | 'given-up',
      guessedWords: response.gameState.guessedWords
    }
    
    // Update display message in GameBoard
    if (gameBoardRef.value) {
      gameBoardRef.value.updateDisplayMessages(
        undefined,
        response.message,
        false
      )
    }
    
    console.log('Game given up:', response)
  } catch (err) {
    console.error('Failed to give up game:', err)
    let errorMessage = 'Failed to give up game. Please try again.'
    
    if (err instanceof GameServiceError) {
      errorMessage = err.message
    }
    
    // Show error message in GameBoard
    if (gameBoardRef.value) {
      gameBoardRef.value.updateDisplayMessages(
        undefined,
        errorMessage,
        false
      )
    }
  } finally {
    isSubmitting.value = false
  }
}

// Initialize game on mount
onMounted(() => {
  handleStartNewGame()
})
</script>

<style scoped>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
}

.app-header {
  text-align: center;
  padding: 2rem 1rem 1rem;
  color: white;
}

.app-title {
  font-size: 3rem;
  font-weight: bold;
  margin: 0 0 0.5rem 0;
  text-shadow: 0 2px 4px rgba(0,0,0,0.3);
  letter-spacing: 2px;
}

.app-subtitle {
  font-size: 1.2rem;
  margin: 0;
  opacity: 0.9;
  font-weight: 300;
}

.loading-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
  padding: 2rem;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top: 4px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.error-message {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 2rem;
  text-align: center;
  max-width: 400px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}

.error-message h3 {
  color: #dc3545;
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
}

.error-message p {
  color: #6c757d;
  margin: 0 0 1.5rem 0;
  line-height: 1.5;
}

.retry-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.retry-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.app-footer {
  text-align: center;
  padding: 1rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
}

.app-footer p {
  margin: 0;
}

/* Responsive design */
@media (max-width: 768px) {
  .app-title {
    font-size: 2.5rem;
  }
  
  .app-subtitle {
    font-size: 1rem;
  }
  
  .app-header {
    padding: 1.5rem 1rem 0.5rem;
  }
}
</style>