import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Chat from './pages/Chat'
import About from './pages/About'
import Profile from './pages/Profile'
import { useAuthStore } from './store/store'

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return children
}

// Auth Route Component (redirect to home if already logged in)
const AuthRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  
  return children
}

function App() {
  const setUser = useAuthStore((state) => state.setUser)

  useEffect(() => {
    // Check if user is already logged in by fetching user info
    fetch('/api/user')
      .then((res) => {
        if (res.ok) {
          return res.json()
        }
        throw new Error('Not authenticated')
      })
      .then((data) => {
        if (data.success && data.user) {
          setUser(data.user)
        }
      })
      .catch(() => {
        // User is not authenticated, do nothing
      })
  }, [setUser])

  return (
    <Router>
      <Routes>
        {/* Auth Routes */}
        <Route
          path="/login"
          element={
            <AuthRoute>
              <Login />
            </AuthRoute>
          }
        />
        <Route
          path="/signup"
          element={
            <AuthRoute>
              <Signup />
            </AuthRoute>
          }
        />

        {/* Protected Routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/about"
          element={
            <ProtectedRoute>
              <About />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App

