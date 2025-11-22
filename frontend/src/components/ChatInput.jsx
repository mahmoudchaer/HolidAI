import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'

const ChatInput = ({ onSend, disabled }) => {
  const [message, setMessage] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [message])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (message.trim() && !disabled) {
      onSend(message)
      setMessage('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white/80 backdrop-blur-sm">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <form onSubmit={handleSubmit} className="relative">
          <div className="flex gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about flights, hotels, visas, or attractions..."
                disabled={disabled}
                rows={1}
                className="input-professional w-full px-5 py-4 pr-24 resize-none overflow-hidden"
                style={{
                  minHeight: '56px',
                  maxHeight: '200px',
                }}
              />
              {message.trim() && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute right-4 bottom-4"
                >
                  <span className="text-xs text-slate-400 font-medium">{message.length}</span>
                </motion.div>
              )}
            </div>
            
            <motion.button
              type="submit"
              disabled={!message.trim() || disabled}
              whileHover={{ scale: disabled ? 1 : 1.02 }}
              whileTap={{ scale: disabled ? 1 : 0.98 }}
              className="btn-primary px-8 py-4 rounded-xl flex items-center gap-2 min-w-[120px] justify-center disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {disabled ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Sending...</span>
                </>
              ) : (
                <>
                  <span className="font-semibold">Send</span>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </>
              )}
            </motion.button>
          </div>
          
          <p className="text-xs text-slate-500 mt-3 text-center">
            Press <kbd className="px-2 py-1 bg-slate-100 rounded text-slate-600 font-mono text-xs">Enter</kbd> to send, 
            <kbd className="px-2 py-1 bg-slate-100 rounded text-slate-600 font-mono text-xs ml-1">Shift + Enter</kbd> for new line
          </p>
        </form>
      </div>
    </div>
  )
}

export default ChatInput
