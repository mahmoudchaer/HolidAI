import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import BackgroundSlideshow from '../components/BackgroundSlideshow'

const Booking = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  
  // Get booking details from URL params
  const hotelId = searchParams.get('hotel_id')
  const rateId = searchParams.get('rate_id')
  const hotelName = searchParams.get('hotel_name') || 'Selected Hotel'
  const checkin = searchParams.get('checkin')
  const checkout = searchParams.get('checkout')
  const price = searchParams.get('price')
  
  const [formData, setFormData] = useState({
    guest_first_name: '',
    guest_last_name: '',
    guest_email: '',
    guest_phone: '',
    card_number: '',
    card_expiry: '',
    card_cvv: '',
    card_holder_name: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [bookingSuccess, setBookingSuccess] = useState(false)
  const [bookingResult, setBookingResult] = useState(null)

  useEffect(() => {
    // Validate that we have required booking parameters
    if (!hotelId || !rateId || !checkin || !checkout) {
      setError('Missing booking information. Please return to chat and try booking again.')
    }
  }, [hotelId, rateId, checkin, checkout])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Call booking API through backend
      const response = await fetch('/api/book-hotel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hotel_id: hotelId,
          rate_id: rateId,
          checkin: checkin,
          checkout: checkout,
          occupancies: [{ adults: 1 }], // Default, can be made dynamic
          ...formData
        }),
      })

      const data = await response.json()

      if (response.ok && !data.error) {
        setBookingSuccess(true)
        setBookingResult(data)
      } else {
        setError(data.error_message || data.detail || 'Booking failed. Please try again.')
      }
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const formatCardNumber = (value) => {
    // Remove all non-digits
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '')
    // Add spaces every 4 digits
    const matches = v.match(/\d{4,16}/g)
    const match = matches && matches[0] || ''
    const parts = []
    for (let i = 0, len = match.length; i < len; i += 4) {
      parts.push(match.substring(i, i + 4))
    }
    if (parts.length) {
      return parts.join(' ')
    } else {
      return v
    }
  }

  const handleCardNumberChange = (e) => {
    const formatted = formatCardNumber(e.target.value)
    setFormData({ ...formData, card_number: formatted })
  }

  const handleExpiryChange = (e) => {
    let value = e.target.value.replace(/\D/g, '')
    if (value.length >= 2) {
      value = value.substring(0, 2) + '/' + value.substring(2, 4)
    }
    setFormData({ ...formData, card_expiry: value })
  }

  if (bookingSuccess) {
    return (
      <div className="relative min-h-screen flex items-center justify-center">
        <BackgroundSlideshow />
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="relative z-10 w-full max-w-2xl px-6"
        >
          <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-8">
            <div className="text-center">
              <div className="mb-6">
                <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h1 className="text-3xl font-bold text-gray-800 mb-2">Booking Confirmed!</h1>
                <p className="text-gray-600">Your hotel reservation has been successfully completed.</p>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-6 mb-6 text-left">
                <h2 className="font-semibold text-lg mb-4">Booking Details</h2>
                <div className="space-y-2">
                  <p><span className="font-medium">Hotel:</span> {hotelName}</p>
                  <p><span className="font-medium">Check-in:</span> {checkin}</p>
                  <p><span className="font-medium">Check-out:</span> {checkout}</p>
                  {bookingResult?.booking_id && (
                    <p><span className="font-medium">Booking ID:</span> {bookingResult.booking_id}</p>
                  )}
                  {bookingResult?.confirmation_code && (
                    <p><span className="font-medium">Confirmation Code:</span> {bookingResult.confirmation_code}</p>
                  )}
                </div>
              </div>
              
              <button
                onClick={() => navigate('/')}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Return to Chat
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center py-12">
      <BackgroundSlideshow />
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-2xl px-6"
      >
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Complete Your Booking</h1>
            <p className="text-gray-600">Please provide your details to complete the reservation</p>
            
            {hotelName && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <p className="text-sm text-gray-600">Hotel: <span className="font-semibold text-gray-800">{hotelName}</span></p>
                {checkin && checkout && (
                  <p className="text-sm text-gray-600">Dates: <span className="font-semibold text-gray-800">{checkin} to {checkout}</span></p>
                )}
                {price && (
                  <p className="text-sm text-gray-600">Price: <span className="font-semibold text-gray-800">${price}</span></p>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Guest Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    First Name *
                  </label>
                  <input
                    type="text"
                    name="guest_first_name"
                    value={formData.guest_first_name}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Last Name *
                  </label>
                  <input
                    type="text"
                    name="guest_last_name"
                    value={formData.guest_last_name}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email *
                  </label>
                  <input
                    type="email"
                    name="guest_email"
                    value={formData.guest_email}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Phone
                  </label>
                  <input
                    type="tel"
                    name="guest_phone"
                    value={formData.guest_phone}
                    onChange={handleChange}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>

            <div>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Payment Information</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Card Number *
                  </label>
                  <input
                    type="text"
                    name="card_number"
                    value={formData.card_number}
                    onChange={handleCardNumberChange}
                    placeholder="1234 5678 9012 3456"
                    maxLength={19}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Expiry Date *
                    </label>
                    <input
                      type="text"
                      name="card_expiry"
                      value={formData.card_expiry}
                      onChange={handleExpiryChange}
                      placeholder="MM/YY"
                      maxLength={5}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      CVV *
                    </label>
                    <input
                      type="text"
                      name="card_cvv"
                      value={formData.card_cvv}
                      onChange={handleChange}
                      placeholder="123"
                      maxLength={4}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Card Holder Name *
                  </label>
                  <input
                    type="text"
                    name="card_holder_name"
                    value={formData.card_holder_name}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => navigate('/')}
                className="flex-1 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {loading ? 'Processing...' : 'Complete Booking'}
              </button>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  )
}

export default Booking

