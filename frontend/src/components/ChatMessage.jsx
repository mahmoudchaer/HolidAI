import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

// Professional Location Card Component
const LocationCard = ({ location, index }) => {
  const [imageErrors, setImageErrors] = useState([])
  const photos = location.photos || (location.photo ? [location.photo] : [])
  
  const handleImageError = (photoIndex) => {
    setImageErrors(prev => [...prev, photoIndex])
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="card-professional mb-4 hover:border-blue-300 hover:shadow-lg overflow-hidden"
    >
      <div className="p-5">
        <div className="text-heading text-xl text-slate-900 mb-3">{location.name || 'Location'}</div>
        
        <div className="flex items-center gap-4 mb-4">
          {location.rating && (
            <div className="flex items-center gap-1.5 bg-yellow-50 px-3 py-1.5 rounded-lg">
              <span className="text-yellow-500 text-lg">⭐</span>
              <span className="text-sm font-bold text-slate-900">{location.rating}</span>
            </div>
          )}
          
          {location.num_reviews && (
            <span className="text-sm text-slate-600 font-medium">
              ({location.num_reviews} reviews)
            </span>
          )}
        </div>
        
        {(location.address || location.address_obj?.address_string) && (
          <div className="flex items-start gap-2 text-sm text-slate-700 mb-4">
            <span className="text-slate-400 mt-0.5">📍</span>
            <span>{location.address || location.address_obj?.address_string}</span>
          </div>
        )}
        
        {location.cuisine && location.cuisine.length > 0 && (
          <div className="flex items-center gap-2 text-sm text-slate-600 mb-4">
            <span>🍽️</span>
            <span className="font-medium">{location.cuisine.map(c => c.name).join(', ')}</span>
          </div>
        )}
      </div>
      
      {/* Photos */}
      {photos && photos.length > 0 && (
        <div className={`grid ${photos.length === 1 ? 'grid-cols-1' : photos.length === 2 ? 'grid-cols-2' : 'grid-cols-3'} gap-2 px-5 pb-5`}>
          {photos.map((photoUrl, idx) => {
            return !imageErrors.includes(idx) && photoUrl ? (
              <motion.img
                key={idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.1 }}
                src={photoUrl}
                alt={`${location.name || 'Location'} - Photo ${idx + 1}`}
                className={`w-full ${photos.length === 1 ? 'h-64' : 'h-40'} object-cover rounded-xl shadow-md`}
                onError={() => handleImageError(idx)}
              />
            ) : null
          })}
        </div>
      )}
      
      {/* Description */}
      {location.description && (
        <div className="px-5 pb-5 pt-2">
          <div className="text-sm text-slate-700 line-clamp-2 leading-relaxed">{location.description}</div>
        </div>
      )}
    </motion.div>
  )
}

const ChatMessage = ({ message, isUser }) => {
  const navigate = useNavigate()
  
  const tryParseStructuredData = (content) => {
    let structuredData = null
    let cleanedContent = content
    
    // Find LOCATION_DATA tag positions more efficiently
    const locationStartTag = '[LOCATION_DATA]'
    const locationEndTag = '[/LOCATION_DATA]'
    const locationStartIdx = cleanedContent.indexOf(locationStartTag)
    
    if (locationStartIdx !== -1) {
      const locationDataStart = locationStartIdx + locationStartTag.length
      const locationEndIdx = cleanedContent.indexOf(locationEndTag, locationDataStart)
      
      if (locationEndIdx !== -1) {
        try {
          const locationJson = cleanedContent.substring(locationDataStart, locationEndIdx)
          const locationData = JSON.parse(locationJson)
          structuredData = { type: 'locations', data: locationData }
          // Remove the tag from content
          cleanedContent = (
            cleanedContent.substring(0, locationStartIdx) + 
            cleanedContent.substring(locationEndIdx + locationEndTag.length)
          ).trim()
        } catch (e) {
          console.error('Failed to parse location data:', e)
        }
      }
    }
    
    return { structuredData, cleanedContent }
  }
  
  const parseResult = !isUser ? tryParseStructuredData(message.content) : { structuredData: null, cleanedContent: message.content }
  const structuredData = parseResult.structuredData
  const cleanedContent = parseResult.cleanedContent
  
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
            <>
              {/* Structured Data Display */}
              {structuredData?.type === 'locations' && (
                <div className="mb-4">
                  <h3 className="text-subheading text-lg text-slate-900 mb-4 flex items-center gap-2">
                    <span className="text-2xl">📍</span>
                    <span>Recommended Locations</span>
                  </h3>
                  <div className="grid grid-cols-1 gap-4">
                    {structuredData.data.map((location, idx) => (
                      <LocationCard key={idx} location={location} index={idx} />
                    ))}
                  </div>
                </div>
              )}
              
              {/* Regular markdown content */}
              {cleanedContent && (
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
            </>
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
