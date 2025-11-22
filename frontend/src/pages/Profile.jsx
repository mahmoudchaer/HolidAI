import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import ProfileForm from '../components/ProfileForm'
import { useAuthStore } from '../store/store'

const Profile = () => {
  const { user, setUser } = useAuthStore()

  const handleSaveProfile = (updatedData) => {
    setUser({ ...user, ...updatedData })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-4xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Your Profile</h1>
          <p className="text-gray-600">
            Manage your account settings and preferences
          </p>
        </motion.div>

        <ProfileForm user={user} onSave={handleSaveProfile} />
      </div>
    </div>
  )
}

export default Profile

