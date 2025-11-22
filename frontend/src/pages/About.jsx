import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'

const About = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="relative">
        {/* Hero Section */}
        <div className="relative h-96 bg-gradient-to-r from-primary to-primary-dark overflow-hidden">
          <img
            src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1920&q=80"
            alt="Travel"
            className="absolute inset-0 w-full h-full object-cover opacity-30"
          />
          <div className="relative z-10 h-full flex items-center justify-center text-white px-4">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center max-w-3xl"
            >
              <h1 className="text-5xl font-bold mb-4">About HolidAI</h1>
              <p className="text-xl opacity-90">
                Your intelligent travel companion, powered by cutting-edge multi-agent AI
              </p>
            </motion.div>
          </div>
        </div>

        {/* Content Section */}
        <div className="max-w-5xl mx-auto px-6 py-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-16"
          >
            <h2 className="text-3xl font-bold text-gray-800 mb-6">What is HolidAI?</h2>
            <p className="text-lg text-gray-600 leading-relaxed mb-4">
              HolidAI is an intelligent travel planning assistant that leverages the power of
              multi-agent artificial intelligence to help you plan the perfect holiday. Unlike
              traditional travel booking sites, HolidAI uses specialized AI agents that work
              together to provide comprehensive travel solutions.
            </p>
            <p className="text-lg text-gray-600 leading-relaxed">
              Whether you're looking for flights, hotels, visa information, or local attractions,
              our AI agents collaborate to give you the best recommendations tailored to your needs.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mb-16"
          >
            <h2 className="text-3xl font-bold text-gray-800 mb-6">Our Mission</h2>
            <p className="text-lg text-gray-600 leading-relaxed mb-4">
              We believe travel planning should be effortless and enjoyable. Our mission is to
              democratize access to intelligent travel planning tools, making it easy for anyone
              to plan amazing trips without the stress and confusion.
            </p>
            <p className="text-lg text-gray-600 leading-relaxed">
              By combining state-of-the-art AI technology with real-time travel data, we're
              creating a future where travel planning is as exciting as the journey itself.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <h2 className="text-3xl font-bold text-gray-800 mb-8">The Multi-Agent System</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[
                {
                  icon: '✈️',
                  title: 'Flight Agent',
                  description: 'Searches and compares flights across multiple airlines to find you the best deals.',
                },
                {
                  icon: '🏨',
                  title: 'Hotel Agent',
                  description: 'Discovers accommodations that match your preferences, budget, and location.',
                },
                {
                  icon: '📄',
                  title: 'Visa Agent',
                  description: 'Provides up-to-date visa requirements and documentation guidance.',
                },
                {
                  icon: '🎭',
                  title: 'Attractions Agent',
                  description: 'Recommends must-see places, restaurants, and activities at your destination.',
                },
                {
                  icon: '🧠',
                  title: 'Memory Agent',
                  description: 'Remembers your preferences and past conversations for personalized recommendations.',
                },
                {
                  icon: '🎯',
                  title: 'Main Coordinator',
                  description: 'Orchestrates all agents to provide comprehensive and coherent travel plans.',
                },
              ].map((agent, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 + idx * 0.1 }}
                  className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition border border-gray-100"
                >
                  <div className="text-4xl mb-3">{agent.icon}</div>
                  <h3 className="text-xl font-bold text-gray-800 mb-2">{agent.title}</h3>
                  <p className="text-gray-600">{agent.description}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.4 }}
            className="mt-16 bg-gradient-to-r from-primary to-primary-dark rounded-2xl p-8 text-white text-center"
          >
            <h2 className="text-3xl font-bold mb-4">Ready to Start Your Journey?</h2>
            <p className="text-lg mb-6 opacity-90">
              Join thousands of travelers who are planning smarter with HolidAI
            </p>
            <a
              href="/"
              className="inline-block bg-white text-primary font-semibold px-8 py-3 rounded-lg hover:shadow-lg transform hover:-translate-y-1 transition"
            >
              Start Planning
            </a>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default About

