import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { Link, useNavigate } from 'react-router-dom'

const ChatMessage = ({ message, isUser }) => {
  const navigate = useNavigate()
  
  // No special handling for location cards - all data is in the conversational response
  const cleanedContent = message.content
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}
    >
      <div className={`max-w-[85%] sm:max-w-[75%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div
          className={`rounded-2xl px-5 py-4 ${
            isUser
              ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg'
              : 'bg-white text-slate-800 shadow-md border border-slate-200'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-body leading-relaxed">{message.content}</p>
          ) : (
            <div className="prose prose-slate max-w-none">
              <ReactMarkdown
                components={{
                  p: ({ children }) => <p className="mb-3 last:mb-0 text-body leading-relaxed">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc ml-6 mb-3 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal ml-6 mb-3 space-y-1">{children}</ol>,
                  li: ({ children }) => <li className="text-body">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
                  code: ({ children }) => (
                    <code className="bg-slate-100 text-slate-800 px-2 py-1 rounded text-sm font-mono">{children}</code>
                  ),
                  a: ({ children, href }) => {
                    // Check if it's an internal link (starts with /)
                    if (href && href.startsWith('/') && !href.startsWith('//')) {
                      return (
                        <Link
                          to={href}
                          className="text-blue-600 hover:text-blue-700 underline font-medium"
                          onClick={(e) => {
                            e.preventDefault()
                            navigate(href)
                          }}
                        >
                          {children}
                        </Link>
                      )
                    }
                    // External links open in new tab
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-700 underline font-medium"
                      >
                        {children}
                      </a>
                    )
                  },
                  img: ({ src, alt }) => (
                    <img
                      src={src}
                      alt={alt}
                      className="rounded-xl my-3 max-w-full shadow-md"
                      loading="lazy"
                    />
                  ),
                }}
              >
                {cleanedContent}
              </ReactMarkdown>
            </div>
          )}
          
          {!isUser && message.agents_called && message.agents_called.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-200">
              <p className="text-xs text-slate-500 font-medium">
                Powered by: {message.agents_called.join(', ')}
              </p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default ChatMessage
