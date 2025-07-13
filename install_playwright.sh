#\!/bin/bash
echo "Installing Playwright browsers..."
python -m playwright install chromium --with-deps || echo "Playwright install failed, will fallback to system browser"
