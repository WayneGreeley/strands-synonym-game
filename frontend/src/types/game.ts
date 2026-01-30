export interface SynonymSlot {
  word: string | null;
  letterCount: number;
  found: boolean;
}

export interface GameState {
  targetWord: string;
  synonyms: SynonymSlot[];
  guessCount: number;
  status: 'active' | 'completed' | 'given-up';
  guessedWords: string[];
}

export interface StartGameRequest {
  // No parameters needed for starting a new game
}

export interface StartGameResponse {
  sessionId: string;
  targetWord: string;
  synonymSlots: Array<{
    letterCount: number;
  }>;
  status: 'active';
}

export interface GuessRequest {
  sessionId: string;
  guess: string;
}

export interface GuessResponse {
  success: boolean;
  message: string;
  hint?: string;
  gameState: GameState;
}

export interface GiveUpRequest {
  sessionId: string;
}

export interface GiveUpResponse {
  message: string;
  gameState: GameState;
}