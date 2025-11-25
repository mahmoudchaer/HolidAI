import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import { useFavoritesStore } from '../store/store'

const typeMeta = {
  flight: { icon: '✈️', label: 'Flights', accent: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-200' },
  hotel: { icon: '🏨', label: 'Hotels', accent: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-200' },
  restaurant: { icon: '🍽️', label: 'Food', accent: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-200' },
  activity: { icon: '🎟️', label: 'Activities', accent: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200' },
  other: { icon: '🗂️', label: 'Extras', accent: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
}

const formatDate = (value) => {
  if (!value) return 'Just now'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Just now'
  return date.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const PlanPreview = ({ items }) => {
  if (!items?.length) return null
  const previewItems = items.slice(0, 3)
  return (
    <div className="space-y-3">
      {previewItems.map((item, idx) => (
        <div
          key={`${item.title}-${idx}`}
          className="rounded-2xl border border-slate-100 dark:border-slate-800 bg-white/80 dark:bg-slate-900/70 p-3"
        >
          <div className="flex items-start gap-3">
            <span className="text-xl">{typeMeta[item.type]?.icon || typeMeta.other.icon}</span>
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {item.title || item.details?.name || 'Untitled'}
              </p>
              {item.details?.location && (
                <p className="text-xs text-slate-500 dark:text-slate-400">{item.details.location}</p>
              )}
              {item.details?.date && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {new Date(item.details.date).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                  })}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
      {items.length > 3 && (
        <p className="text-xs text-slate-500 dark:text-slate-400">+{items.length - 3} more highlights</p>
      )}
    </div>
  )
}

const FavouriteCard = ({ plan, index, onRemove }) => {
  const stats = useMemo(() => {
    return plan.items.reduce((acc, item) => {
      const type = item.type && typeMeta[item.type] ? item.type : 'other'
      acc[type] = (acc[type] || 0) + 1
      return acc
    }, {})
  }, [plan.items])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="rounded-3xl border border-slate-100 dark:border-slate-800 bg-white/90 dark:bg-slate-950/80 shadow-xl shadow-slate-200/40 dark:shadow-none p-6 flex flex-col gap-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500 mb-1">
            Curated itinerary
          </p>
          <h3 className="text-2xl font-semibold text-slate-900 dark:text-white">
            {plan.title || 'Favourite plan'}
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Saved {formatDate(plan.savedAt)}</p>
        </div>
        <button
          onClick={() => onRemove(plan.sessionId)}
          className="text-sm font-medium text-rose-500 hover:text-rose-600 transition-colors"
        >
          Remove
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        {Object.entries(stats).map(([type, count]) => (
          <span
            key={type}
            className={`px-3 py-1.5 rounded-full text-xs font-medium ${typeMeta[type]?.accent || typeMeta.other.accent}`}
          >
            {typeMeta[type]?.icon || typeMeta.other.icon} {typeMeta[type]?.label || typeMeta.other.label}{' '}
            <span className="opacity-70">• {count}</span>
          </span>
        ))}
      </div>

      <PlanPreview items={plan.items} />

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
        <span className="font-mono text-[0.7rem] tracking-wide bg-slate-100 dark:bg-slate-900 px-3 py-1 rounded-full">
          Session: {plan.sessionId}
        </span>
        <span>Saved itinerary • {plan.items.length} hand-picked details</span>
      </div>
    </motion.div>
  )
}

const Favourites = () => {
  const favorites = useFavoritesStore((state) => state.favorites)
  const removeFavorite = useFavoritesStore((state) => state.removeFavorite)

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <Navbar />
      <main className="flex-1 w-full">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-10">
          <header className="text-center space-y-4">
            <p className="text-sm uppercase tracking-[0.3em] text-blue-500">Curated by you</p>
            <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white">
              Favourite travel blueprints
            </h1>
            <p className="text-base text-slate-500 dark:text-slate-400 max-w-2xl mx-auto">
              Every starred plan becomes a polished inspiration board. Revisit your best itineraries, remix them for
              future adventures, or share them with your travel companions.
            </p>
          </header>

          {favorites.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-3xl border border-dashed border-slate-200 dark:border-slate-800 p-12 text-center bg-white/60 dark:bg-slate-900/60"
            >
              <div className="text-6xl mb-4">⭐</div>
              <h2 className="text-2xl font-semibold text-slate-900 dark:text-white mb-2">No favourites yet</h2>
              <p className="text-slate-500 dark:text-slate-400 mb-6">
                Star any plan from the chat workspace to build your personal collection of travel-ready itineraries.
              </p>
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold shadow-lg shadow-blue-500/30"
              >
                Start planning
                <span>→</span>
              </Link>
            </motion.div>
          ) : (
            <motion.div layout className="grid gap-6 md:grid-cols-2">
              {favorites.map((plan, idx) => (
                <FavouriteCard key={plan.sessionId} plan={plan} index={idx} onRemove={removeFavorite} />
              ))}
            </motion.div>
          )}
        </div>
      </main>
    </div>
  )
}

export default Favourites

