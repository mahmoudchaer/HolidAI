import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import ChatSidebar from '../components/ChatSidebar'
import ChatMessage from '../components/ChatMessage'
import ChatInput from '../components/ChatInput'
import PlanSidebar from '../components/PlanSidebar'
import { useChatStore, useActivityStore, usePlanStore, useSidebarStore } from '../store/store'
import { useWebSocket } from '../hooks/useWebSocket'

const Chat = () => {
  const {
    conversations,
    setConversations,
    currentConversation,
    setCurrentConversation,
    messages,
    setMessages,
    addMessage,
    isLoading,
    setLoading,
  } = useChatStore()

  // Get agent activity status
  const { currentStatus } = useActivityStore()

  const setPlanItemsState = usePlanStore((state) => state.setItems)
  const setPlanLoadingState = usePlanStore((state) => state.setLoading)
  const setPlanErrorState = usePlanStore((state) => state.setError)
  const clearPlan = usePlanStore((state) => state.clearPlan)
  const leftSidebarOpen = useSidebarStore((state) => state.leftSidebarOpen)
  const rightSidebarOpen = useSidebarStore((state) => state.rightSidebarOpen)
  const toggleLeftSidebar = useSidebarStore((state) => state.toggleLeftSidebar)
  const toggleRightSidebar = useSidebarStore((state) => state.toggleRightSidebar)

  const chatContainerRef = useRef(null)
  
  // WebSocket for real-time updates
  useWebSocket()

  // Helper function to get icon for agent activity type
  const getActivityIcon = (type) => {
    switch (type) {
      case 'flight':
        return '✈️'
      case 'hotel':
        return '🏨'
      case 'visa':
        return '📄'
      case 'attractions':
      case 'tripadvisor':
        return '🎭'
      case 'search':
        return '🔍'
      case 'analyzing':
      case 'thinking':
        return '🤔'
      case 'planning':
        return '📋'
      default:
        return null
    }
  }

  useEffect(() => {
    loadConversations()
  }, [])

  useEffect(() => {
    // Smooth scroll to bottom when new messages arrive
    if (chatContainerRef.current) {
      const scrollHeight = chatContainerRef.current.scrollHeight
      const height = chatContainerRef.current.clientHeight
      const maxScrollTop = scrollHeight - height
      chatContainerRef.current.scrollTo({
        top: maxScrollTop,
        behavior: 'smooth'
      })
    }
  }, [messages])

  const loadConversations = async () => {
    try {
      const response = await fetch('/api/conversations')
      const data = await response.json()
      if (data.success) {
        setConversations(data.conversations)
      }
    } catch (err) {
      console.error('Error loading conversations:', err)
    }
  }

  const fetchPlanItems = useCallback(async (targetSessionId, { silent = false, retry = false } = {}) => {
    if (!targetSessionId) {
      clearPlan()
      return
    }

    if (!silent) setPlanLoadingState(true)

    try {
      // Add a small delay if retrying to allow database commit to complete
      if (retry) {
        await new Promise(resolve => setTimeout(resolve, 300))
      }
      
      const response = await fetch(`/api/travel-plan?session_id=${targetSessionId}`)
      const data = await response.json()
      if (response.ok && data.success) {
        console.log(`[PLAN] Fetched ${data.items.length} plan items for session ${targetSessionId.slice(0, 8)}...`)
        setPlanItemsState(data.items, targetSessionId)
      } else {
        console.error(`[PLAN] Error fetching plan items:`, data.error)
        setPlanErrorState(data.error || 'Unable to load travel plan')
      }
    } catch (err) {
      setPlanErrorState(err.message)
    } finally {
      if (!silent) setPlanLoadingState(false)
    }
  }, [clearPlan, setPlanErrorState, setPlanItemsState, setPlanLoadingState])

  useEffect(() => {
    if (currentConversation?.session_id) {
      fetchPlanItems(currentConversation.session_id)
    } else {
      clearPlan()
    }
  }, [currentConversation?.session_id, clearPlan, fetchPlanItems])

  const handleNewChat = async () => {
    setCurrentConversation(null)
    setMessages([])
    clearPlan()
  }

  const handleSelectConversation = async (sessionId) => {
    try {
      const response = await fetch(`/api/conversations/${sessionId}`)
      const data = await response.json()
      if (data.success) {
        setCurrentConversation({
          session_id: data.session_id,
          title: data.title,
        })
        setMessages(data.messages || [])
        await loadConversations()
      }
    } catch (err) {
      console.error('Error loading conversation:', err)
    }
  }

  const handleDeleteConversation = async (sessionId) => {
    if (!confirm('Are you sure you want to delete this conversation?')) return

    try {
      const response = await fetch(`/api/conversations/${sessionId}`, {
        method: 'DELETE',
      })
      const data = await response.json()
      if (data.success) {
        if (currentConversation?.session_id === sessionId) {
          setCurrentConversation(null)
          setMessages([])
          clearPlan()
        }
        await loadConversations()
      }
    } catch (err) {
      console.error('Error deleting conversation:', err)
    }
  }

  const handleSendMessage = async (messageText) => {
    let sessionId = currentConversation?.session_id
    
    const userMessage = { role: 'user', content: messageText }
    addMessage(userMessage)
    setLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageText,
          session_id: sessionId,
        }),
      })

      // Check if response is ok before parsing
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }))
        addMessage({
          role: 'assistant',
          content: `Error: ${errorData.error || 'Something went wrong'}`,
        })
        return
      }
      
      // Parse response with error handling
      let data
      try {
        data = await response.json()
      } catch (e) {
        console.error('Failed to parse response JSON:', e)
        addMessage({
          role: 'assistant',
          content: `Error: Failed to parse server response. The response may be too large.`,
        })
        return
      }
      
      if (data.response) {
        const assistantMessage = {
          role: 'assistant',
          content: data.response,
          agents_called: data.agents_called,
        }
        addMessage(assistantMessage)
        
        // Update session_id if we got a new one, but preserve current conversation state
        const activeSessionId = data.session_id || sessionId
        if (data.session_id) {
          const newSessionId = data.session_id
          // Only update if it's actually different
          if (!currentConversation || currentConversation.session_id !== newSessionId) {
            // Preserve the current messages when updating conversation
            setCurrentConversation({ 
              session_id: newSessionId,
              title: currentConversation?.title // Preserve title if exists
            })
          }
        }

        if (activeSessionId) {
          // Fetch plan items with a delay to ensure database commit is complete
          // Retry multiple times to handle any timing issues with database commits
          setTimeout(() => {
            fetchPlanItems(activeSessionId, { silent: true, retry: true })
          }, 300)
          // Retry again after a longer delay to ensure we get the latest data
          setTimeout(() => {
            fetchPlanItems(activeSessionId, { silent: true, retry: true })
          }, 1000)
          // Final retry after 2 seconds
          setTimeout(() => {
            fetchPlanItems(activeSessionId, { silent: true, retry: true })
          }, 2000)
        }
        
        // Load conversations in background without affecting current state
        loadConversations().catch(err => console.error('Error loading conversations:', err))
      } else {
        addMessage({
          role: 'assistant',
          content: `Error: ${data.error || 'Something went wrong'}`,
        })
      }
    } catch (err) {
      addMessage({
        role: 'assistant',
        content: `Error: ${err.message}`,
      })
    } finally {
      setLoading(false)
      // Clear agent activity when loading is done
      const { clearCurrentStatus } = useActivityStore.getState()
      clearCurrentStatus()
    }
  }

  const handleRenameConversation = async (sessionId, newTitle) => {
    try {
      const response = await fetch(`/api/conversations/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      })
      const data = await response.json()
      if (response.ok && data.success) {
        await loadConversations()
        if (currentConversation?.session_id === sessionId) {
          setCurrentConversation({
            ...currentConversation,
            title: newTitle,
          })
        }
        return true
      }
    } catch (err) {
      console.error('Error renaming conversation:', err)
    }
    return false
  }

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      <Navbar />
      
      <div className="flex-1 flex overflow-hidden relative">
        <button
          onClick={toggleLeftSidebar}
          className="flex items-center justify-center w-10 h-10 rounded-full shadow-soft bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 absolute z-30"
          style={{ left: leftSidebarOpen ? '19rem' : '1rem', top: '1rem' }}
          title="Toggle chat history"
        >
          {leftSidebarOpen ? '⟨' : '⟩'}
        </button>
        <button
          onClick={toggleRightSidebar}
          className="hidden xl:flex items-center justify-center w-10 h-10 rounded-full shadow-soft bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 absolute z-30"
          style={{ right: rightSidebarOpen ? '19rem' : '1rem', top: '1rem' }}
          title="Toggle plan"
        >
          {rightSidebarOpen ? '⟩' : '⟨'}
        </button>

        <ChatSidebar
          conversations={conversations}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          interactionLocked={isLoading}
        />

        <div className="flex-1 flex flex-col relative">
          {/* Chat messages area */}
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-8"
          >
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="h-full flex items-center justify-center"
              >
                <div className="text-center max-w-3xl px-4">
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                    className="text-7xl mb-8"
                  >
                    ✈️
                  </motion.div>
                  <h2 className="text-4xl font-bold text-heading mb-4 bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                    Welcome to HolidAI
                  </h2>
                  <p className="text-lg text-text-secondary mb-12 max-w-2xl mx-auto">
                    Your intelligent travel assistant powered by multi-agent AI.
                    Ask me about flights, hotels, visas, or attractions and I'll help you plan your perfect trip.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left max-w-2xl mx-auto">
                    {[
                      { icon: '✈️', title: 'Flight Deals', text: 'Find the best flight deals and compare prices' },
                      { icon: '🏨', title: 'Hotels', text: 'Discover perfect accommodations for your stay' },
                      { icon: '📄', title: 'Visa Info', text: 'Get visa requirements and travel documents' },
                      { icon: '🎭', title: 'Attractions', text: 'Explore local attractions and restaurants' },
                    ].map((item, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + idx * 0.1 }}
                        className="card-professional group hover:border-blue-200"
                      >
                        <div className="flex items-start gap-4">
                          <div className="text-3xl group-hover:scale-110 transition-transform">
                            {item.icon}
                          </div>
                          <div>
                            <h3 className="text-subheading text-lg mb-1">{item.title}</h3>
                            <p className="text-caption">{item.text}</p>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.div>
            ) : (
              <div className="max-w-5xl mx-auto space-y-6">
                {messages.map((msg, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <ChatMessage
                      message={msg}
                      isUser={msg.role === 'user'}
                    />
                  </motion.div>
                ))}
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex justify-start mb-4"
                  >
                    <div className="card-professional">
                      <div className="flex gap-2 items-center">
                        {currentStatus?.type && currentStatus?.message ? (
                          <>
                            {getActivityIcon(currentStatus.type) && (
                              <span className="text-base">{getActivityIcon(currentStatus.type)}</span>
                            )}
                            <span className="text-caption">
                              {currentStatus.message}
                            </span>
                          </>
                        ) : (
                          <>
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            <span className="ml-2 text-caption">Thinking...</span>
                          </>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            )}
          </div>

          {/* Chat input */}
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
        </div>

        {rightSidebarOpen && <PlanSidebar />}
      </div>
    </div>
  )
}

export default Chat
