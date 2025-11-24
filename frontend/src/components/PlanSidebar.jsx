import { useMemo } from 'react'
import { usePlanStore } from '../store/store'

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
  return (
    <div className="text-sm text-slate-600">
      <div className="font-medium text-slate-800">
        {departure.name || departure.id || 'Origin'} → {arrival.name || arrival.id || 'Destination'}
      </div>
      <div>{formatDateTime(departure.time)}</div>
      <div className="text-xs text-slate-500 mt-1">
        {segments.length > 0 && segments[0].airline ? segments[0].airline : 'Flight'} · {details.price ? `$${details.price}` : 'Price TBD'}
      </div>
    </div>
  )
}

const HotelSummary = ({ details }) => {
  if (!details) return null
  return (
    <div className="text-sm text-slate-600">
      <div className="font-medium text-slate-800">{details.name || 'Hotel'}</div>
      {details.location && <div>{details.location}</div>}
      {details.date && <div>{formatDateTime(details.date)}</div>}
    </div>
  )
}

const RestaurantSummary = ({ details }) => {
  if (!details) return null
  return (
    <div className="text-sm text-slate-600">
      <div className="font-medium text-slate-800">{details.name || 'Restaurant'}</div>
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
        <div className="text-sm text-slate-600">
          <div className="font-medium text-slate-800">{item.title}</div>
        </div>
      )
  }
}

const PlanSection = ({ label, icon, items }) => (
  <div className="mb-6">
    <div className="flex items-center gap-2 text-slate-700 font-semibold mb-3">
      <span>{icon}</span>
      <span>{label}</span>
      <span className="text-xs text-slate-400">({items.length})</span>
    </div>
    <div className="space-y-3">
      {items.map((item, idx) => (
        <div key={`${item.title}-${idx}`} className="rounded-lg border border-slate-200 bg-white/90 p-3 shadow-sm">
          <SummaryByType item={item} />
        </div>
      ))}
    </div>
  </div>
)

const PlanSidebar = () => {
  const { items, isLoading, sessionId, error } = usePlanStore()

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

  return (
    <aside className="hidden xl:flex w-80 border-l border-slate-200 bg-white/80 backdrop-blur px-4 py-6 flex-col overflow-y-auto">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-800">My Plan</h2>
        {sessionId ? (
          <p className="text-xs text-slate-500 mt-1">Session: {sessionId.slice(0, 8)}...</p>
        ) : (
          <p className="text-xs text-slate-500 mt-1">Start chatting to build your plan</p>
        )}
      </div>

      {error && (
        <div className="text-sm text-rose-500">
          {error}
        </div>
      )}

      {isLoading && !error && (
        <div className="text-sm text-slate-500">Loading plan…</div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="text-sm text-slate-500">
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
            />
          ))}
        </div>
      )}
    </aside>
  )
}

export default PlanSidebar

