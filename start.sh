#!/bin/bash
echo "🤖 InterPrep AI Bot - Railway Deployment"

# 1. Create necessary directories
mkdir -p data

# 2. Log environment
echo "📁 Current dir: $(pwd)"
echo "📂 Files: $(ls -la)"

# 3. Check for token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN not set!"
    exit 1
fi
echo "✅ Token is set"

# 4. Install dependencies
echo "📦 Installing dependencies from requirements.txt..."
pip install --no-cache-dir -r requirements.txt

# 5. Start the bot
echo "🚀 Starting bot..."
exec python main.py