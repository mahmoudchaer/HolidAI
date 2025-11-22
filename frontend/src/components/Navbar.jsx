import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore, useSidebarStore } from '../store/store'

const Navbar = () => {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { toggleLeftSidebar } = useSidebarStore()

  const handleLogout = async () => {
    try {
      await fetch('/api/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    } catch (err) {
      console.error('Logout error:', err)
    }
    logout()
    navigate('/login')
  }

  return (
    <motion.nav
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 shadow-sm sticky top-0 z-50"
    >
      <div className="px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-3 group">
              <motion.div
                whileHover={{ rotate: 15, scale: 1.1 }}
                className="text-3xl"
              >
                ✈️
              </motion.div>
              <span className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                HolidAI
              </span>
            </Link>
            
            <div className="hidden md:flex items-center gap-8">
              <Link 
                to="/" 
                className="text-sm font-medium text-slate-700 hover:text-blue-600 transition-colors relative group"
              >
                Chat
                <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-blue-600 group-hover:w-full transition-all duration-300" />
              </Link>
              <Link 
                to="/about" 
                className="text-sm font-medium text-slate-700 hover:text-blue-600 transition-colors relative group"
              >
                About
                <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-blue-600 group-hover:w-full transition-all duration-300" />
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Sidebar toggle */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={toggleLeftSidebar}
              className="p-2.5 hover:bg-slate-100 rounded-xl transition-colors"
              title="Toggle conversations"
            >
              <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </motion.button>

            {user && (
              <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
                <Link
                  to="/profile"
                  className="flex items-center gap-3 hover:opacity-80 transition-opacity group"
                >
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center font-semibold text-white shadow-md group-hover:shadow-lg transition-shadow">
                    {user.email?.[0]?.toUpperCase() || '?'}
                  </div>
                  <span className="text-sm font-medium text-slate-700 hidden lg:inline">
                    {user.email}
                  </span>
                </Link>
                
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleLogout}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors text-sm font-medium text-slate-700"
                >
                  Logout
                </motion.button>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.nav>
  )
}

export default Navbar
