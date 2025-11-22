@echo off
echo Building HolidAI Frontend...

echo Installing Node.js dependencies...
call npm install

echo Building React application...
call npm run build

echo Build complete! The production build is in the 'dist' folder.
echo.
echo To start the Flask server (which serves the React app):
echo   python app.py

