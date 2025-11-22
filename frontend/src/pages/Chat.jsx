import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import ChatSidebar from '../components/ChatSidebar'
import AgentStatusIndicator from '../components/AgentStatusIndicator'
import ChatMessage from '../components/ChatMessage'
import ChatInput from '../components/ChatInput'
import { useChatStore } from '../store/store'
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

  const chatContainerRef = useRef(null)
  
  // WebSocket for real-time updates
  useWebSocket()

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

  const handleNewChat = async () => {
    setCurrentConversation(null)
    setMessages([])
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

      const data = await response.json()
      
      if (response.ok) {
        const assistantMessage = {
          role: 'assistant',
          content: data.response,
          agents_called: data.agents_called,
        }
        addMessage(assistantMessage)
        
        if (data.session_id) {
          if (!currentConversation || currentConversation.session_id !== data.session_id) {
            setCurrentConversation({ session_id: data.session_id })
          }
        }
        
        await loadConversations()
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
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50">
      <Navbar />
      
      <div className="flex-1 flex overflow-hidden">
        <ChatSidebar
          conversations={conversations}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onDeleteConversation={handleDeleteConversation}
        />

        <div className="flex-1 flex flex-col relative">
          {/* Agent Status Indicator */}
          <AgentStatusIndicator />
          
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
                    className="flex justify-start mb-4"
                  >
                    <div className="card-professional">
                      <div className="flex gap-2 items-center">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        <span className="ml-2 text-caption">Thinking...</span>
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
      </div>
    </div>
  )
}

export default Chat
