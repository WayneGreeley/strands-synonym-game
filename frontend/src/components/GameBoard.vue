<template>
  <div class="game-board">
    <!-- Target Word Display -->
    <div class="target-word-section">
      <h2 class="target-word-label">Find synonyms for:</h2>
      <div class="target-word">{{ targetWord }}</div>
    </div>

    <!-- Synonym Slots -->
    <div class="synonym-slots">
      <div 
        v-for="(slot, index) in synonymSlots" 
        :key="index"
        class="synonym-slot"
        :class="{ 'found': slot.found }"
      >
        <div class="slot-content">
          <span v-if="slot.found" class="found-word">{{ slot.word }}</span>
          <span v-else class="letter-count">{{ slot.letterCount }} letters</span>
        </div>
      </div>
    </div>

    <!-- Input Section -->
    <div class="input-section" v-if="gameStatus === 'active'">
      <div class="input-group">
        <input
          v-model="currentGuess"
          @keyup.enter="submitGuess"
          @input="validateInput"
          type="text"
          placeholder="Enter a synonym..."
          class="guess-input"
          :disabled="isSubmitting || isLoading"
          maxlength="50"
        />
        <button 
          @click="submitGuess"
          :disabled="!currentGuess.trim() || isSubmitting || isLoading"
          class="submit-btn"
        >
          {{ isSubmitting ? 'Submitting...' : 'Submit' }}
        </button>
      </div>
      
      <!-- Input validation message -->
      <div v-if="inputError" class="input-error">
        {{ inputError }}
      </div>
    </div>

    <!-- Game Actions -->
    <div class="game-actions" v-if="gameStatus === 'active'">
      <button @click="giveUp" class="give-up-btn" :disabled="isSubmitting || isLoading">
        Give Up
      </button>
    </div>

    <!-- Game Status Messages -->
    <div class="game-status">
      <div v-if="gameStatus === 'completed'" class="success-message">
        🎉 Congratulations! You found all synonyms in {{ guessCount }} guesses!
      </div>
      <div v-if="gameStatus === 'given-up'" class="give-up-message">
        Game ended. Better luck next time!
      </div>
    </div>

    <!-- Guess Counter -->
    <div class="guess-counter">
      Guesses: {{ guessCount }}
    </div>

    <!-- Hint Display -->
    <div v-if="currentHint" class="hint-section">
      <h3>Hint:</h3>
      <p class="hint-text">{{ currentHint }}</p>
    </div>

    <!-- Message Display -->
    <div v-if="lastMessage" class="message-section">
      <p class="game-message" :class="{ 'success': lastMessageSuccess, 'error': !lastMessageSuccess }">
        {{ lastMessage }}
      </p>
    </div>

    <!-- New Game Button -->
    <div class="new-game-section" v-if="gameStatus !== 'active'">
      <button @click="startNewGame" class="new-game-btn">
        Start New Game
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { GameState, SynonymSlot } from '../types/game'

// Props
interface Props {
  gameState?: GameState | null
  isLoading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  gameState: null,
  isLoading: false
})

// Emits
const emit = defineEmits<{
  submitGuess: [guess: string]
  giveUp: []
  startNewGame: []
}>()

// Reactive state
const currentGuess = ref('')
const inputError = ref('')
const isSubmitting = ref(false)

// Computed properties
const targetWord = computed(() => props.gameState?.targetWord || '')
const synonymSlots = computed(() => {
  if (!props.gameState?.synonyms) return []
  return props.gameState.synonyms.map(slot => ({
    word: slot.word,
    letterCount: slot.letterCount,
    found: slot.found
  }))
})
const gameStatus = computed(() => props.gameState?.status || 'active')
const guessCount = computed(() => props.gameState?.guessCount || 0)
const currentHint = ref('')
const lastMessage = ref('')
const lastMessageSuccess = ref(false)

// Methods
const validateInput = () => {
  const input = currentGuess.value
  const trimmed = input.trim()
  
  // Clear previous error
  inputError.value = ''
  
  if (!input) return
  
  // Check for empty input after trimming
  if (!trimmed) {
    inputError.value = 'Guess cannot be empty'
    return
  }
  
  // Check for multiple words
  if (trimmed.includes(' ')) {
    inputError.value = 'Please enter only one word'
    return
  }
  
  // Check for excessive length
  if (input.length > 50) {
    inputError.value = 'Input too long (maximum 50 characters)'
    return
  }
  
  // Check for non-alphabetic characters
  if (!/^[a-zA-Z\s]*$/.test(input)) {
    inputError.value = 'Please use only letters'
    return
  }
  
  // Check minimum length after removing spaces
  const lettersOnly = input.replace(/[^a-zA-Z]/g, '')
  if (lettersOnly.length < 1) {
    inputError.value = 'Word must contain at least one letter'
    return
  }
  
  // Check for suspicious patterns
  const suspiciousPatterns = [
    /[<>{}[\]\\]/,  // HTML/XML/JSON brackets
    /[;|&$`]/,      // Shell command separators
    /(script|javascript|eval|function)/i,  // Script-related keywords
    /(select|insert|update|delete|drop)/i,  // SQL keywords
  ]
  
  for (const pattern of suspiciousPatterns) {
    if (pattern.test(input)) {
      inputError.value = 'Invalid characters detected in input'
      return
    }
  }
}

const submitGuess = async () => {
  const guess = currentGuess.value.trim()
  
  if (!guess) return
  
  // Validate input one more time
  validateInput()
  if (inputError.value) return
  
  isSubmitting.value = true
  
  try {
    emit('submitGuess', guess)
    currentGuess.value = ''
    inputError.value = ''
  } finally {
    isSubmitting.value = false
  }
}

const giveUp = () => {
  if (confirm('Are you sure you want to give up and see all the answers?')) {
    emit('giveUp')
  }
}

const startNewGame = () => {
  currentHint.value = ''
  lastMessage.value = ''
  emit('startNewGame')
}

// Update hint and message when game state changes
const updateDisplayMessages = (hint?: string, message?: string, success?: boolean) => {
  if (hint) {
    currentHint.value = hint
  }
  if (message) {
    lastMessage.value = message
    lastMessageSuccess.value = success || false
    
    // Clear message after 5 seconds for non-error messages
    if (success) {
      setTimeout(() => {
        lastMessage.value = ''
      }, 5000)
    }
  }
}

// Expose method for parent component to update messages
defineExpose({
  updateDisplayMessages
})

// Initialize on mount
onMounted(() => {
  // Component is ready
})
</script>

<style scoped>
.game-board {
  max-width: 600px;
  margin: 0 auto;
  padding: 2rem;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.target-word-section {
  text-align: center;
  margin-bottom: 2rem;
}

.target-word-label {
  font-size: 1.2rem;
  color: #666;
  margin-bottom: 0.5rem;
  font-weight: normal;
}

.target-word {
  font-size: 2.5rem;
  font-weight: bold;
  color: #2c3e50;
  text-transform: uppercase;
  letter-spacing: 2px;
  padding: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.synonym-slots {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 2rem;
}

.synonym-slot {
  background: #f8f9fa;
  border: 2px solid #e9ecef;
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
  transition: all 0.3s ease;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.synonym-slot.found {
  background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
  border-color: #28a745;
  transform: scale(1.02);
  box-shadow: 0 4px 12px rgba(40, 167, 69, 0.2);
}

.slot-content {
  width: 100%;
}

.found-word {
  font-size: 1.4rem;
  font-weight: bold;
  color: #155724;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.letter-count {
  font-size: 1rem;
  color: #6c757d;
  font-style: italic;
}

.input-section {
  margin-bottom: 1.5rem;
}

.input-group {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.guess-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 2px solid #dee2e6;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.3s ease;
}

.guess-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.guess-input:disabled {
  background-color: #f8f9fa;
  cursor: not-allowed;
}

.submit-btn {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.submit-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.input-error {
  color: #dc3545;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.game-actions {
  text-align: center;
  margin-bottom: 1.5rem;
}

.give-up-btn {
  padding: 0.5rem 1rem;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.give-up-btn:hover:not(:disabled) {
  background: #c82333;
}

.give-up-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.game-status {
  text-align: center;
  margin-bottom: 1rem;
}

.success-message {
  color: #155724;
  background: #d4edda;
  border: 1px solid #c3e6cb;
  border-radius: 8px;
  padding: 1rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.give-up-message {
  color: #721c24;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 8px;
  padding: 1rem;
  font-size: 1.1rem;
}

.guess-counter {
  text-align: center;
  color: #6c757d;
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.hint-section {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.hint-section h3 {
  margin: 0 0 0.5rem 0;
  color: #856404;
  font-size: 1rem;
}

.hint-text {
  margin: 0;
  color: #856404;
  font-size: 0.95rem;
  line-height: 1.4;
}

.message-section {
  margin-bottom: 1rem;
}

.game-message {
  padding: 0.75rem;
  border-radius: 6px;
  margin: 0;
  font-size: 0.95rem;
}

.game-message.success {
  color: #155724;
  background: #d4edda;
  border: 1px solid #c3e6cb;
}

.game-message.error {
  color: #721c24;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
}

.new-game-section {
  text-align: center;
  margin-top: 2rem;
}

.new-game-btn {
  padding: 0.75rem 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.new-game-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

/* Responsive design */
@media (max-width: 768px) {
  .game-board {
    padding: 1rem;
  }
  
  .target-word {
    font-size: 2rem;
  }
  
  .synonym-slots {
    grid-template-columns: 1fr;
  }
  
  .input-group {
    flex-direction: column;
  }
  
  .submit-btn {
    margin-top: 0.5rem;
  }
}
</style>