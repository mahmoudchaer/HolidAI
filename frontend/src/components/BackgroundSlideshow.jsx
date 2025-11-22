import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const images = [
  'https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1920&q=80', // Airplane wing
  'https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=1920&q=80', // Beach resort
  'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1920&q=80', // Mountain landscape
  'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1920&q=80', // Tropical beach
  'https://images.unsplash.com/photo-1464037866556-6812c9d1c72e?w=1920&q=80', // Desert dunes
]

const BackgroundSlideshow = () => {
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % images.length)
    }, 10000) // Change every 10 seconds

    return () => clearInterval(timer)
  }, [])

  return (
    <div className="fixed inset-0 w-full h-full overflow-hidden">
      <AnimatePresence mode="wait">
        <motion.div
          key={currentIndex}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.5 }}
          className="absolute inset-0 w-full h-full"
        >
          <img
            src={images[currentIndex]}
            alt="Background"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-primary/60 to-primary-dark/60" />
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

export default BackgroundSlideshow

