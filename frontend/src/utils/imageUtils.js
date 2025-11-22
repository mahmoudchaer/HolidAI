// Airline logo mapping - using a public airline logo API
export const getAirlineLogo = (airlineName) => {
  // Use Kiwi.com API for free airline logos
  if (!airlineName) return null
  
  // Common airline name to IATA code mapping
  const airlineCodeMap = {
    'emirates': 'EK',
    'qatar airways': 'QR',
    'etihad airways': 'EY',
    'turkish airlines': 'TK',
    'lufthansa': 'LH',
    'air france': 'AF',
    'british airways': 'BA',
    'delta': 'DL',
    'united': 'UA',
    'american airlines': 'AA',
    'southwest': 'WN',
    'jetblue': 'B6',
    'virgin atlantic': 'VS',
    'klm': 'KL',
    'singapore airlines': 'SQ',
    'cathay pacific': 'CX',
    'japan airlines': 'JL',
    'ana': 'NH',
    'korean air': 'KE',
    'air canada': 'AC',
    'qantas': 'QF',
    'saudia': 'SV',
    'middle east airlines': 'ME',
    'mea': 'ME',
    'royal jordanian': 'RJ',
    'egyptair': 'MS',
    'ethiopian airlines': 'ET',
    'kenya airways': 'KQ',
    'south african airways': 'SA',
  }
  
  // Try to find airline code in the mapping
  const lowerName = airlineName.trim().toLowerCase()
  const code = airlineCodeMap[lowerName]
  
  if (code) {
    return `https://images.kiwi.com/airlines/64/${code}.png`
  }
  
  // If it's already a 2-letter code, use it directly
  const trimmed = airlineName.trim().toUpperCase()
  if (trimmed.length === 2) {
    return `https://images.kiwi.com/airlines/64/${trimmed}.png`
  }
  
  // Try first two letters as fallback
  const firstTwo = trimmed.substring(0, 2)
  return `https://images.kiwi.com/airlines/64/${firstTwo}.png`
}

// Generate placeholder for missing images
export const getPlaceholderImage = (type = 'default') => {
  const colors = {
    flight: 'from-blue-400 to-blue-600',
    restaurant: 'from-orange-400 to-red-500',
    hotel: 'from-purple-400 to-pink-500',
    attraction: 'from-green-400 to-teal-500',
    default: 'from-gray-400 to-gray-600',
  }
  
  return colors[type] || colors.default
}

