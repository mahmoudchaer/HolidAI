import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { usePlanStore, useFavoritesStore, useChatStore } from '../store/store'

const typeOrder = ['flight', 'hotel', 'restaurant', 'activity']

const typeLabels = {
  flight: 'Flights',
  hotel: 'Hotels',
  restaurant: 'Restaurants',
  activity: 'Activities',
}

const typeIcons = {
  flight: '✈️',
  hotel: '🏨',
  restaurant: '🍽️',
  activity: '🎟️',
}

const formatDateTime = (value) => {
  if (!value) return null
  try {
    const date = new Date(value.replace(' ', 'T'))
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

const FlightSummary = ({ details }) => {
  if (!details) return null
  const segments = details.flights || []
  const first = segments[0] || {}
  const last = segments[segments.length - 1] || first
  const departure = first.departure_airport || {}
  const arrival = last.arrival_airport || {}
  const bookingLink = details.booking_link
  const googleFlightsUrl = details.google_flights_url
  
  return (
    <div className="text-sm text-slate-600 dark:text-slate-300">
      <div className="font-medium text-slate-800 dark:text-slate-100">
        {departure.name || departure.id || 'Origin'} → {arrival.name || arrival.id || 'Destination'}
      </div>
      <div>{formatDateTime(departure.time)}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
        {segments.length > 0 && segments[0].airline ? segments[0].airline : 'Flight'} · {details.price ? `$${details.price}` : 'Price TBD'}
      </div>
      
      {/* Show booking links if available */}
      {(bookingLink || googleFlightsUrl) && (
        <div className="flex flex-wrap gap-2 mt-2">
          {bookingLink && (
            <a
              href={bookingLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
            >
              Book Now →
            </a>
          )}
          {googleFlightsUrl && (
            <a
              href={googleFlightsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-md transition-colors"
            >
              View on Google Flights →
            </a>
          )}
        </div>
      )}
    </div>
  )
}

const HotelSummary = ({ details }) => {
  if (!details) return null
  
  // Normalize field names - handle both checkin/checkout and check_in/check_out
  const checkIn = details.check_in || details.checkin
  const checkOut = details.check_out || details.checkout
  const price = details.price_total || details.price
  const roomType = details.room_type || details.roomType
  
  // Check if this hotel has room booking details
  const hasRoomDetails = checkIn && checkOut && price
  
  return (
    <div className="text-sm text-slate-600 dark:text-slate-300">
      <div className="font-medium text-slate-800 dark:text-slate-100">{details.name || details.hotel_name || 'Hotel'}</div>
      {(details.location || details.address) && <div className="text-xs text-slate-500 dark:text-slate-400">{details.location || details.address}</div>}
      
      {/* Show room type if available */}
      {roomType && (
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Room: {roomType}
            </div>
          )}
      
      {/* Show check-in/check-out dates if available */}
      {checkIn && checkOut && (
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          📅 {checkIn} → {checkOut}
            </div>
          )}
      
      {/* Show price if available */}
      {price && (
        <div className="text-xs text-slate-700 dark:text-slate-200 font-semibold mt-1">
          💰 {price}
              {details.currency && ` ${details.currency}`}
            </div>
          )}
      
      {/* Show booking link as a button if available */}
      {details.booking_link && (
        <a
          href={details.booking_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-2 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
        >
          Book Now →
        </a>
      )}
      
      {/* Show board/meal plan if available */}
          {details.board && (
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          🍽️ {details.board}
            </div>
      )}
      
      {/* Show date if no room details but date exists */}
      {!hasRoomDetails && (details.date || details.trip_month_year) && (
        <div className="mt-1">{formatDateTime(details.date || details.trip_month_year)}</div>
      )}
      
      {/* Show ratings */}
      {details.star_rating && <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">⭐ {details.star_rating} stars</div>}
      {details.rating && !details.star_rating && <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">⭐ {details.rating}/10</div>}
    </div>
  )
}

const RestaurantSummary = ({ details }) => {
  if (!details) return null
  return (
    <div className="text-sm text-slate-600 dark:text-slate-300">
      <div className="font-medium text-slate-800 dark:text-slate-100">{details.name || 'Restaurant'}</div>
      {details.location && <div>{details.location}</div>}
      {details.date && <div>{formatDateTime(details.date)}</div>}
    </div>
  )
}

const SummaryByType = ({ item }) => {
  switch (item.type) {
    case 'flight':
      return <FlightSummary details={item.details} />
    case 'hotel':
      return <HotelSummary details={item.details} />
    case 'restaurant':
    case 'activity':
      return <RestaurantSummary details={item.details} />
    default:
      return (
        <div className="text-sm text-slate-600 dark:text-slate-300">
          <div className="font-medium text-slate-800 dark:text-slate-100">{item.title}</div>
        </div>
      )
  }
}

const PlanSection = ({ label, icon, items, onRemoveItem }) => (
  <div className="mb-6">
    <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200 font-semibold mb-3">
      <span>{icon}</span>
      <span>{label}</span>
      <span className="text-xs text-slate-400 dark:text-slate-500">({items.length})</span>
    </div>
    <div className="space-y-3">
      {items.map((item, idx) => (
        <div key={`${item.title}-${idx}`} className="group rounded-lg border border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-800/80 p-3 shadow-sm relative">
          <SummaryByType item={item} />
          {onRemoveItem && (
            <button
              onClick={() => onRemoveItem(item.title)}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-rose-500 hover:text-rose-600 text-sm font-medium"
              title="Remove item"
            >
              ✕
            </button>
          )}
        </div>
      ))}
    </div>
  </div>
)

const PlanSidebar = () => {
  const { items, isLoading, sessionId, error, setItems } = usePlanStore()
  const currentConversation = useChatStore((state) => state.currentConversation)
  const favorites = useFavoritesStore((state) => state.favorites)
  const toggleFavoritePlan = useFavoritesStore((state) => state.toggleFavoritePlan)

  const groupedItems = useMemo(() => {
    const groups = {}
    items.forEach((item) => {
      const type = item.type || 'other'
      if (!groups[type]) groups[type] = []
      groups[type].push(item)
    })
    return groups
  }, [items])

  const orderedTypes = useMemo(() => {
    const presentTypes = Object.keys(groupedItems)
    const ordered = typeOrder.filter((t) => presentTypes.includes(t))
    const remaining = presentTypes.filter((t) => !typeOrder.includes(t))
    return [...ordered, ...remaining]
  }, [groupedItems])

  const isCurrentPlanFavorited = useMemo(() => {
    if (!sessionId) return false
    return favorites.some((fav) => fav.sessionId === sessionId)
  }, [favorites, sessionId])

  const handleToggleFavorite = () => {
    if (!sessionId || items.length === 0) return
    const snapshot = JSON.parse(JSON.stringify(items))
    toggleFavoritePlan({
      sessionId,
      title: currentConversation?.title || `Plan ${sessionId.slice(0, 6)}`,
      items: snapshot,
    })
  }

  const handleRemoveItem = async (title) => {
    if (!sessionId || !confirm(`Remove "${title}" from your plan?`)) return
    
    try {
      const response = await fetch('/api/travel-plan', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          title: title,
        }),
      })
      
      const data = await response.json()
      if (response.ok && data.success) {
        // Refresh plan items by fetching again
        const refreshResponse = await fetch(`/api/travel-plan?session_id=${sessionId}`)
        const refreshData = await refreshResponse.json()
        if (refreshResponse.ok && refreshData.success) {
          setItems(refreshData.items, sessionId)
        }
      } else {
        console.error('[PLAN] Error deleting item:', data.error)
        alert(data.error || 'Failed to remove item')
      }
    } catch (err) {
      console.error('[PLAN] Error deleting item:', err)
      alert('Failed to remove item')
    }
  }

  return (
    <aside className="hidden xl:flex w-80 border-l border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur px-4 py-6 flex-col overflow-y-auto">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">My Plan</h2>
          {sessionId ? (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Session: {sessionId.slice(0, 8)}...
            </p>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Start chatting to build your plan</p>
          )}
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleToggleFavorite}
          disabled={!sessionId || items.length === 0}
          className="p-2 rounded-full border border-transparent disabled:opacity-40 disabled:cursor-not-allowed bg-white/70 dark:bg-slate-800/80 hover:border-amber-300 transition-colors shadow-sm"
          title={isCurrentPlanFavorited ? 'Remove from favourites' : 'Save to favourites'}
        >
          <span className={`text-xl ${isCurrentPlanFavorited ? 'text-amber-400' : 'text-slate-400'}`}>
            {isCurrentPlanFavorited ? '★' : '☆'}
          </span>
        </motion.button>
      </div>

      {error && (
        <div className="text-sm text-rose-500">
          {error}
        </div>
      )}

      {isLoading && !error && (
        <div className="text-sm text-slate-500 dark:text-slate-400">Loading plan…</div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="text-sm text-slate-500 dark:text-slate-400">
          Your plan is empty. Ask me to save a flight, hotel, or restaurant and it will appear here.
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div>
          {orderedTypes.map((type) => (
            <PlanSection
              key={type}
              label={typeLabels[type] || type.charAt(0).toUpperCase() + type.slice(1)}
              icon={typeIcons[type] || '📝'}
              items={groupedItems[type]}
              onRemoveItem={handleRemoveItem}
            />
          ))}
        </div>
      )}
    </aside>
  )
}

export default PlanSidebar

