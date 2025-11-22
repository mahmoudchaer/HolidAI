import { motion, AnimatePresence } from 'framer-motion'
import { useActivityStore } from '../store/store'

const AgentStatusIndicator = () => {
  const { currentStatus, isAgentActive } = useActivityStore()

  if (!isAgentActive || !currentStatus) return null

  const getStatusIcon = (type) => {
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
      case 'success':
        return '✅'
      default:
        return '⚡'
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2 }}
        className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-blue-100"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{getStatusIcon(currentStatus.type)}</span>
          <span className="text-sm text-gray-700 font-medium">
            {currentStatus.message}
          </span>
        </div>
        
        {/* Animated dots to show activity */}
        <div className="flex gap-1 ml-2">
          <motion.div
            className="w-1.5 h-1.5 bg-blue-500 rounded-full"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: 0 }}
          />
          <motion.div
            className="w-1.5 h-1.5 bg-blue-500 rounded-full"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
          />
          <motion.div
            className="w-1.5 h-1.5 bg-blue-500 rounded-full"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
          />
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

export default AgentStatusIndicator

