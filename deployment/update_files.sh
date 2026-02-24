#!/usr/bin/env bash
# Lokal makineden çalıştır: sadece app.py ve templates/index.html'i sunucuya atar, servisi restart eder.
# .env'de SERVER_KEY (ve isteğe bağlı SERVER) tanımlı olmalı.
# Kullanım: ./deployment/update_files.sh [user@host]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# .env'den SERVER_KEY ve isteğe bağlı SERVER yükle
if [ -f "$REPO_ROOT/.env" ]; then
    export $(grep -v '^#' "$REPO_ROOT/.env" | xargs)
fi

SERVER="${1:-${SERVER:-root@65.21.182.26}}"
REMOTE_DIR="/var/www/jobspy"
SERVICE="jobspy"

if [ -z "$SERVER_KEY" ]; then
    echo "❌ Error: SERVER_KEY not found in .env file"
    exit 1
fi

if ! command -v sshpass &> /dev/null; then
    echo "❌ Error: sshpass is not installed"
    echo "   Install: brew install hudochenkov/sshpass/sshpass (macOS) or apt-get install sshpass (Linux)"
    exit 1
fi

echo "🚀 Updating app.py and index.html on $SERVER..."

echo "📤 Copying files..."
sshpass -p "$SERVER_KEY" scp -o StrictHostKeyChecking=no app.py "$SERVER:$REMOTE_DIR/"
sshpass -p "$SERVER_KEY" scp -o StrictHostKeyChecking=no templates/index.html "$SERVER:$REMOTE_DIR/templates/"

echo "🔄 Fixing permissions and restarting $SERVICE..."
sshpass -p "$SERVER_KEY" ssh -o StrictHostKeyChecking=no "$SERVER" \
  "chown -R www-data:www-data $REMOTE_DIR && systemctl restart $SERVICE && systemctl is-active $SERVICE && echo '✅ Done.'"

echo "🎉 Update complete!"
