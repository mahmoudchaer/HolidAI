import { useEffect } from 'react'
import { io } from 'socket.io-client'
import { useActivityStore } from '../store/store'

export const useWebSocket = () => {
  const setCurrentStatus = useActivityStore((state) => state.setCurrentStatus)
  const clearCurrentStatus = useActivityStore((state) => state.clearCurrentStatus)

  useEffect(() => {
    // Connect to WebSocket server
    const socket = io('/', {
      transports: ['websocket', 'polling'],
    })

    socket.on('connect', () => {
      console.log('WebSocket connected')
    })

    socket.on('agent_activity', (data) => {
      console.log('Agent activity:', data)
      
      // Map backend event types to user-friendly messages
      const statusMessage = data.message || 'Processing...'
      const statusType = data.type || 'default'
      
      // Detect if this is a completion event
      const isCompletionEvent = 
        statusMessage.toLowerCase().includes('completed') ||
        statusMessage.toLowerCase().includes('finished') ||
        statusMessage.toLowerCase().includes('done')
      
      if (isCompletionEvent) {
        // Clear status after a short delay to show completion
        setTimeout(() => {
          clearCurrentStatus()
        }, 2000)
      }
      
      // Update current status
      setCurrentStatus({
        type: statusType,
        message: statusMessage,
        details: data.details,
      })
    })

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected')
      clearCurrentStatus()
    })

    socket.on('error', (error) => {
      console.error('WebSocket error:', error)
    })

    return () => {
      socket.disconnect()
      clearCurrentStatus()
    }
  }, [setCurrentStatus, clearCurrentStatus])
}

