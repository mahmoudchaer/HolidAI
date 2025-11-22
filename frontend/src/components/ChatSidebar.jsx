import { motion, AnimatePresence } from 'framer-motion'
import { useChatStore, useSidebarStore } from '../store/store'

const ChatSidebar = ({ conversations, onSelectConversation, onNewChat, onDeleteConversation }) => {
  const currentConversation = useChatStore((state) => state.currentConversation)
  const leftSidebarOpen = useSidebarStore((state) => state.leftSidebarOpen)

  return (
    <AnimatePresence>
      {leftSidebarOpen && (
        <motion.div
          initial={{ x: -320, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -320, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          className="w-80 bg-white border-r border-slate-200 flex flex-col h-full shadow-lg"
        >
          <div className="p-4 border-b border-slate-200">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onNewChat}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl font-semibold hover:shadow-lg transition-all group"
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

          <div className="flex-1 overflow-y-auto p-3">
            {conversations.length === 0 ? (
              <div className="text-center text-slate-500 text-sm py-12 px-4">
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
                    className={`group relative p-4 rounded-xl cursor-pointer transition-all ${
                      currentConversation?.session_id === conv.session_id
                        ? 'bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 shadow-md'
                        : 'hover:bg-slate-50 border-2 border-transparent'
                    }`}
                    onClick={() => onSelectConversation(conv.session_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0 pr-2">
                        <p className={`text-sm font-semibold truncate ${
                          currentConversation?.session_id === conv.session_id
                            ? 'text-blue-900'
                            : 'text-slate-900'
                        }`}>
                          {conv.title}
                        </p>
                        <p className={`text-xs mt-1 ${
                          currentConversation?.session_id === conv.session_id
                            ? 'text-blue-600'
                            : 'text-slate-500'
                        }`}>
                          {conv.message_count || 0} messages
                        </p>
                      </div>
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteConversation(conv.session_id)
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 rounded-lg transition-all"
                      >
                        <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </motion.button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default ChatSidebar
