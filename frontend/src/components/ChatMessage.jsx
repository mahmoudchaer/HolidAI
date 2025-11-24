import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getAirlineLogo, getPlaceholderImage } from '../utils/imageUtils'

// Professional Flight Card Component
const FlightCard = ({ flight, index }) => {
  const [logoError, setLogoError] = useState(false)
  
  const firstSegment = flight.flights?.[0] || {}
  const airlineLogo = firstSegment.airline_logo || flight.airline_logo || getAirlineLogo(firstSegment.airline || flight.airline || flight.airlineCode)
  const airlineName = firstSegment.airline || flight.airline || 'Airline'
  
  const formatDuration = (minutes) => {
    if (!minutes) return ''
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return `${hours}h ${mins}m`
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="card-professional mb-4 hover:border-blue-300 hover:shadow-lg group"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-4">
          {!logoError && airlineLogo ? (
            <img
              src={airlineLogo}
              alt={airlineName}
              className="w-16 h-16 object-contain rounded-lg bg-slate-50 p-2"
              onError={() => setLogoError(true)}
            />
          ) : (
            <div className="w-16 h-16 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-2xl shadow-md">
              ✈️
            </div>
          )}
          <div>
            <div className="text-heading text-lg text-slate-900">{airlineName}</div>
            {flight.type && (
              <div className="text-sm font-semibold text-blue-600 mt-0.5">{flight.type}</div>
            )}
            {flight.flights && flight.flights.length > 0 && (
              <div className="text-xs text-slate-500 mt-1 font-medium">
                {flight.flights[0].departure_airport?.id} → {flight.flights[flight.flights.length - 1].arrival_airport?.id}
                {flight.direction === "return" && " (Return)"}
                {flight.direction === "outbound" && " (Outbound)"}
              </div>
            )}
          </div>
        </div>
        {flight.price && (
          <div className="text-right">
            <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              ${flight.price}
            </div>
            {flight.type === "Round trip" ? (
              <div className="text-xs text-slate-500 font-medium">Total for both ways</div>
            ) : (
              flight.type && <div className="text-xs text-slate-500 font-medium">{flight.type}</div>
            )}
          </div>
        )}
      </div>
      
      {/* Flight Segments */}
      {flight.flights && flight.flights.length > 0 && (
        <div className="space-y-4 mb-4">
          {flight.flights.map((segment, idx) => (
            <div key={idx} className="bg-gradient-to-r from-slate-50 to-blue-50/30 rounded-xl p-4 border border-slate-100">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="text-subheading text-slate-900 mb-1">
                    {segment.departure_airport?.name || segment.departure_airport?.id}
                  </div>
                  <div className="text-xl font-bold text-slate-800 mb-1">
                    {segment.departure_airport?.time}
                  </div>
                  <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                    {segment.departure_airport?.id}
                  </div>
                </div>
                
                <div className="flex-shrink-0 px-6 text-center">
                  <div className="text-xs text-slate-600 font-semibold mb-2">
                    {formatDuration(segment.duration)}
                  </div>
                  <div className="text-2xl text-blue-500 mb-2">→</div>
                  {segment.flight_number && (
                    <div className="text-xs text-slate-500 font-medium bg-white px-2 py-1 rounded">
                      {segment.flight_number}
                    </div>
                  )}
                </div>
                
                <div className="flex-1 text-right">
                  <div className="text-subheading text-slate-900 mb-1">
                    {segment.arrival_airport?.name || segment.arrival_airport?.id}
                  </div>
                  <div className="text-xl font-bold text-slate-800 mb-1">
                    {segment.arrival_airport?.time}
                  </div>
                  <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                    {segment.arrival_airport?.id}
                  </div>
                </div>
              </div>
              
              {/* Flight Details */}
              <div className="mt-4 pt-4 border-t border-slate-200 flex flex-wrap gap-3">
                {segment.airplane && (
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <span className="font-semibold">Aircraft:</span>
                    <span>{segment.airplane}</span>
                  </div>
                )}
                {segment.travel_class && (
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <span className="font-semibold">Class:</span>
                    <span>{segment.travel_class}</span>
                  </div>
                )}
                {segment.legroom && (
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <span className="font-semibold">Legroom:</span>
                    <span>{segment.legroom}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* Extensions */}
      {flight.extensions && flight.extensions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="flex flex-wrap gap-2">
            {flight.extensions.map((ext, idx) => (
              <span key={idx} className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full font-medium">
                {ext}
              </span>
            ))}
          </div>
        </div>
      )}
      
      {/* Booking Links */}
      {(flight.booking_link || flight.google_flights_url) && (
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="flex flex-wrap gap-3">
            {flight.booking_link && (
              <a
                href={flight.booking_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold rounded-lg hover:from-blue-700 hover:to-indigo-700 transition-all duration-200 shadow-md hover:shadow-lg"
              >
                <span>🔗</span>
                <span>Book Now{flight.book_with ? ` with ${flight.book_with}` : ''}</span>
              </a>
            )}
            {flight.google_flights_url && (
              <a
                href={flight.google_flights_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-white text-slate-700 text-sm font-semibold rounded-lg border-2 border-slate-300 hover:border-blue-500 hover:text-blue-600 transition-all duration-200 shadow-sm hover:shadow-md"
              >
                <span>✈️</span>
                <span>View on Google Flights</span>
              </a>
            )}
          </div>
          {flight.book_with && !flight.booking_link && (
            <div className="mt-2 text-xs text-slate-500">
              Book with: <span className="font-semibold text-slate-700">{flight.book_with}</span>
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

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
    
    // Find FLIGHT_DATA tag positions more efficiently
    const flightStartTag = '[FLIGHT_DATA]'
    const flightEndTag = '[/FLIGHT_DATA]'
    const flightStartIdx = content.indexOf(flightStartTag)
    
    if (flightStartIdx !== -1) {
      const flightDataStart = flightStartIdx + flightStartTag.length
      const flightEndIdx = content.indexOf(flightEndTag, flightDataStart)
      
      if (flightEndIdx !== -1) {
        try {
          const flightJson = content.substring(flightDataStart, flightEndIdx)
          const flightData = JSON.parse(flightJson)
          structuredData = { type: 'flights', data: flightData }
          // Remove the tag from content
          cleanedContent = (
            content.substring(0, flightStartIdx) + 
            content.substring(flightEndIdx + flightEndTag.length)
          ).trim()
        } catch (e) {
          console.error('Failed to parse flight data:', e)
          console.error('Flight JSON length:', flightEndIdx - flightDataStart, 'chars')
        }
      }
    }
    
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
              {structuredData?.type === 'flights' && (() => {
                const allFlights = structuredData.data
                const outboundFlights = allFlights.filter(f => 
                  f.direction === 'outbound' || (!f.direction && !f.type?.includes('Return'))
                )
                const returnFlights = allFlights.filter(f => 
                  f.direction === 'return' || f.type === 'Return flight'
                )
                
                return (
                  <div className="mb-4">
                    {outboundFlights.length > 0 && (
                      <div className="mb-6">
                        <h3 className="text-subheading text-lg text-slate-900 mb-4 flex items-center gap-2">
                          <span className="text-2xl">✈️</span>
                          <span>Outbound Flights</span>
                        </h3>
                        {outboundFlights.map((flight, idx) => (
                          <FlightCard key={`outbound-${idx}`} flight={flight} index={idx} />
                        ))}
                      </div>
                    )}
                    
                    {returnFlights.length > 0 && (
                      <div className="mb-6">
                        <h3 className="text-subheading text-lg text-slate-900 mb-4 flex items-center gap-2">
                          <span className="text-2xl">🔄</span>
                          <span>Return Flights</span>
                        </h3>
                        {returnFlights.map((flight, idx) => (
                          <FlightCard key={`return-${idx}`} flight={flight} index={idx} />
                        ))}
                      </div>
                    )}
                    
                    {outboundFlights.length === 0 && returnFlights.length === 0 && (
                      <div className="mb-4">
                        {allFlights.map((flight, idx) => (
                          <FlightCard key={idx} flight={flight} index={idx} />
                        ))}
                      </div>
                    )}
                  </div>
                )
              })()}
              
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
