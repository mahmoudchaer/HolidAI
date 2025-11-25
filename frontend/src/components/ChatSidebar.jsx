import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useChatStore, useSidebarStore } from '../store/store'

const ChatSidebar = ({
  conversations,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onRenameConversation,
  interactionLocked = false,
}) => {
  const currentConversation = useChatStore((state) => state.currentConversation)
  const leftSidebarOpen = useSidebarStore((state) => state.leftSidebarOpen)
  const [editingId, setEditingId] = useState(null)
  const [editValue, setEditValue] = useState('')

  const startEditing = (conversation) => {
    setEditingId(conversation.session_id)
    setEditValue(conversation.title)
  }

  const cancelEditing = () => {
    setEditingId(null)
    setEditValue('')
  }

  const handleRenameSubmit = async (sessionId) => {
    if (!onRenameConversation) return cancelEditing()
    const trimmed = editValue.trim()
    if (!trimmed) return
    await onRenameConversation(sessionId, trimmed)
    cancelEditing()
  }

  return (
    <AnimatePresence>
      {leftSidebarOpen && (
        <motion.div
          initial={{ x: -320, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -320, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          className="w-80 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col h-full shadow-lg relative"
        >
          <div className="p-4 border-b border-slate-200 dark:border-slate-800">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => {
                if (interactionLocked) return
                onNewChat()
              }}
              disabled={interactionLocked}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl font-semibold transition-all group ${
                interactionLocked ? 'opacity-50 cursor-not-allowed' : 'hover:shadow-lg'
              }`}
              title={interactionLocked ? 'Waiting for the current response' : 'Start a new conversation'}
            >
              <motion.span
                whileHover={{ rotate: 90 }}
                className="text-xl font-bold"
              >
                +
              </motion.span>
              <span>New Chat</span>
            </motion.button>
          </div>

          <div
            className={`flex-1 overflow-y-auto p-3 ${
              interactionLocked ? 'pointer-events-none select-none blur-[1px]' : ''
            }`}
            aria-disabled={interactionLocked}
          >
            {conversations.length === 0 ? (
              <div className="text-center text-slate-500 dark:text-slate-400 text-sm py-12 px-4">
                <div className="text-4xl mb-3">💬</div>
                <p className="font-medium mb-1">No conversations yet</p>
                <p className="text-xs">Start a new chat to begin!</p>
              </div>
            ) : (
              <div className="space-y-2">
                {conversations.map((conv, idx) => (
                  <motion.div
                    key={conv.session_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className={`group relative p-4 rounded-xl transition-all ${
                      currentConversation?.session_id === conv.session_id
                        ? 'bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-slate-800/80 dark:to-slate-800 border-2 border-blue-200 dark:border-slate-700 shadow-md'
                        : `${
                            interactionLocked
                              ? 'border-2 border-transparent opacity-60 cursor-not-allowed pointer-events-none'
                              : 'hover:bg-slate-50 dark:hover:bg-slate-800/60 border-2 border-transparent'
                          }`
                    }`}
                    onClick={() => {
                      if (interactionLocked || editingId === conv.session_id) return
                      onSelectConversation(conv.session_id)
                    }}
                    title={
                      interactionLocked
                        ? 'Finish the current response before switching chats'
                        : `Open ${conv.title}`
                    }
                  >
                    {editingId === conv.session_id ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              handleRenameSubmit(conv.session_id)
                            } else if (e.key === 'Escape') {
                              cancelEditing()
                            }
                          }}
                          className="flex-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                        />
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRenameSubmit(conv.session_id)
                          }}
                          className="p-2 bg-emerald-500 text-white rounded-lg"
                        >
                          ✓
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={(e) => {
                            e.stopPropagation()
                            cancelEditing()
                          }}
                          className="p-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg"
                        >
                          ✕
                        </motion.button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0 pr-2">
                          <p className={`text-sm font-semibold truncate ${
                            currentConversation?.session_id === conv.session_id
                              ? 'text-blue-900 dark:text-blue-200'
                              : 'text-slate-900 dark:text-slate-100'
                          }`}>
                            {conv.title}
                          </p>
                          <p className={`text-xs mt-1 ${
                            currentConversation?.session_id === conv.session_id
                              ? 'text-blue-600 dark:text-blue-300'
                              : 'text-slate-500 dark:text-slate-400'
                          }`}>
                            {conv.message_count || 0} messages
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                          <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              startEditing(conv)
                            }}
                            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-all"
                            title="Rename chat"
                          >
                            <svg className="w-4 h-4 text-slate-600 dark:text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z" />
                            </svg>
                          </motion.button>
                          <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              onDeleteConversation(conv.session_id)
                            }}
                            className="p-1.5 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-all"
                            title="Delete chat"
                          >
                            <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </motion.button>
                        </div>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          {interactionLocked && (
            <div className="absolute inset-0 z-20 bg-white/70 dark:bg-slate-900/80 backdrop-blur-md flex flex-col items-center justify-center text-center px-6 text-sm font-semibold text-slate-600 dark:text-slate-300 pointer-events-auto">
              <div className="text-4xl mb-3 animate-pulse">✈️</div>
              <p>Hold tight—your agent is finishing the current plan.</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">Switching chats is temporarily locked.</p>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default ChatSidebar
