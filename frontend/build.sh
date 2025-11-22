#!/bin/bash

echo "🚀 Building HolidAI Frontend..."

# Install Node dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Build the React app
echo "🔨 Building React application..."
npm run build

echo "✅ Build complete! The production build is in the 'dist' folder."
echo ""
echo "To start the Flask server (which serves the React app):"
echo "  python app.py"

