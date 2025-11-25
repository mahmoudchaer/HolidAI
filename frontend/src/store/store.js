import { create } from 'zustand'

const FAVORITES_STORAGE_KEY = 'holidAI-favorites'

const getInitialFavorites = () => {
  if (typeof window === 'undefined') return []
  try {
    const stored = localStorage.getItem(FAVORITES_STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    console.warn('Failed to read favorites from storage')
    return []
  }
}

const persistFavorites = (favorites) => {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites))
    } catch {
      console.warn('Failed to persist favorites')
    }
  }
}

export const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  logout: () => set({ user: null, isAuthenticated: false }),
}))

export const useChatStore = create((set, get) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  isLoading: false,
  
  setConversations: (conversations) => set({ conversations }),
  setCurrentConversation: (conversation) => {
    // Only update messages if the conversation object has messages
    // Otherwise, keep the existing messages in state
    if (conversation?.messages !== undefined) {
      set({ 
        currentConversation: conversation,
        messages: conversation.messages
      })
    } else {
      set({ currentConversation: conversation })
    }
  },
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  setMessages: (messages) => set({ messages }),
  setLoading: (isLoading) => set({ isLoading }),
  
  clearMessages: () => set({ messages: [] }),
}))

export const useActivityStore = create((set) => ({
  // Current agent status for the indicator
  currentStatus: null,
  isAgentActive: false,
  
  // Set the current agent status
  setCurrentStatus: (status) => set({ 
    currentStatus: status,
    isAgentActive: true
  }),
  
  // Clear the current status (when agent completes)
  clearCurrentStatus: () => set({ 
    currentStatus: null,
    isAgentActive: false
  }),
  
  // Legacy support (deprecated but kept for backwards compatibility)
  activities: [],
  addActivity: (activity) => set((state) => ({
    activities: [...state.activities, { 
      ...activity, 
      id: Date.now(),
      timestamp: new Date().toISOString()
    }]
  })),
  clearActivities: () => set({ activities: [] }),
}))

export const usePlanStore = create((set) => ({
  items: [],
  isLoading: false,
  error: null,
  sessionId: null,

  setItems: (items, sessionId) => set({ items, sessionId, error: null }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  clearPlan: () => set({ items: [], sessionId: null, error: null }),
}))

export const useFavoritesStore = create((set, get) => ({
  favorites: getInitialFavorites(),

  toggleFavoritePlan: (plan) => {
    const { favorites } = get()
    const exists = favorites.some((fav) => fav.sessionId === plan.sessionId)
    const updated = exists
      ? favorites.filter((fav) => fav.sessionId !== plan.sessionId)
      : [
          ...favorites,
          {
            ...plan,
            savedAt: new Date().toISOString(),
          },
        ]
    persistFavorites(updated)
    set({ favorites: updated })
  },

  removeFavorite: (sessionId) => {
    const updated = get().favorites.filter((fav) => fav.sessionId !== sessionId)
    persistFavorites(updated)
    set({ favorites: updated })
  },

  clearFavorites: () => {
    persistFavorites([])
    set({ favorites: [] })
  },
}))

export const useSidebarStore = create((set) => ({
  leftSidebarOpen: true,
  rightSidebarOpen: true,
  
  toggleLeftSidebar: () => set((state) => ({ 
    leftSidebarOpen: !state.leftSidebarOpen 
  })),
  toggleRightSidebar: () => set((state) => ({
    rightSidebarOpen: !state.rightSidebarOpen
  })),
  setLeftSidebarOpen: (open) => set({ leftSidebarOpen: open }),
  setRightSidebarOpen: (open) => set({ rightSidebarOpen: open }),
}))

const getInitialTheme = () => {
  if (typeof window === 'undefined') return 'light'
  return localStorage.getItem('holidAI-theme') || 'light'
}

export const useThemeStore = create((set) => ({
  theme: getInitialTheme(),
  setTheme: (theme) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('holidAI-theme', theme)
    }
    set({ theme })
  },
  toggleTheme: () => set((state) => {
    const nextTheme = state.theme === 'dark' ? 'light' : 'dark'
    if (typeof window !== 'undefined') {
      localStorage.setItem('holidAI-theme', nextTheme)
    }
    return { theme: nextTheme }
  }),
}))

