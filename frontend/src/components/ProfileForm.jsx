import { useState } from 'react'
import { motion } from 'framer-motion'

const ProfileForm = ({ user, onSave }) => {
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    preferences: user?.preferences || '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage({ type: '', text: '' })

    try {
      // Simulate API call - replace with actual API endpoint
      await new Promise((resolve) => setTimeout(resolve, 1000))
      
      onSave(formData)
      setMessage({ type: 'success', text: 'Profile updated successfully!' })
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to update profile' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={handleSubmit}
      className="bg-white rounded-xl shadow-lg p-8 max-w-2xl mx-auto"
    >
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Profile Settings</h2>

      <div className="space-y-6">
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
            Full Name
          </label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary focus:outline-none transition"
            placeholder="Your full name"
          />
        </div>

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
            Email Address
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            disabled
            className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg bg-gray-50 cursor-not-allowed"
          />
          <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
        </div>

        <div>
          <label htmlFor="preferences" className="block text-sm font-medium text-gray-700 mb-2">
            Travel Preferences
          </label>
          <textarea
            id="preferences"
            name="preferences"
            value={formData.preferences}
            onChange={handleChange}
            rows={4}
            className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-primary focus:outline-none transition resize-none"
            placeholder="Tell us about your travel preferences (e.g., budget-friendly, luxury, adventure, etc.)"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Profile Picture
          </label>
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 bg-gradient-to-r from-primary to-primary-dark rounded-full flex items-center justify-center text-white text-3xl font-bold">
              {formData.email?.[0]?.toUpperCase() || '?'}
            </div>
            <button
              type="button"
              className="px-4 py-2 border-2 border-gray-200 rounded-lg hover:border-primary transition text-sm font-medium text-gray-700"
            >
              Upload Picture
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Recommended: Square image, at least 200x200 pixels
          </p>
        </div>

        {message.text && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className={`p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 border border-green-200 text-green-700'
                : 'bg-red-50 border border-red-200 text-red-700'
            }`}
          >
            {message.text}
          </motion.div>
        )}

        <div className="flex gap-4 pt-4">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 bg-gradient-to-r from-primary to-primary-dark text-white font-semibold py-3 rounded-lg hover:shadow-lg transform hover:-translate-y-0.5 transition disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            type="button"
            onClick={() => setFormData({
              name: user?.name || '',
              email: user?.email || '',
              preferences: user?.preferences || '',
            })}
            className="px-6 py-3 border-2 border-gray-200 rounded-lg hover:border-gray-300 transition font-medium text-gray-700"
          >
            Reset
          </button>
        </div>
      </div>
    </motion.form>
  )
}

export default ProfileForm

