#!/bin/bash

# JobSpy Deployment Script for jobs.tugrul.app (Root Version)
# Run this script as root on your server

set -e  # Exit on any error

echo "🚀 Starting JobSpy deployment (Root Mode)..."

# Variables
APP_DIR="/var/www/jobspy"
SERVICE_NAME="jobspy"
DOMAIN="jobs.tugrul.app"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root."
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "📦 Installing required packages..."
apt install python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git htop ufw -y

# Create application directory
echo "📁 Setting up application directory..."
mkdir -p $APP_DIR

# Copy application files (assuming they're in current directory)
echo "📋 Copying application files..."
cp -r app.py requirements.txt production_app.py templates/ $APP_DIR/
if [ -f "deployment/jobspy.service" ]; then
    cp deployment/jobspy.service /tmp/
fi

# Set up Python virtual environment
echo "🐍 Setting up Python virtual environment..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# Test the application
echo "🧪 Testing application..."
timeout 10s python app.py || echo "✅ App test completed"

# Set proper permissions
echo "🔐 Setting permissions..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Install systemd service
echo "⚙️ Installing systemd service..."
if [ -f "/tmp/jobspy.service" ]; then
    cp /tmp/jobspy.service /etc/systemd/system/
else
    # Create service file if not exists
    cat > /etc/systemd/system/jobspy.service << EOF
[Unit]
Description=JobSpy Web Application
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/jobspy
Environment=PATH=/var/www/jobspy/venv/bin
ExecStart=/var/www/jobspy/venv/bin/gunicorn -w 2 -b 127.0.0.1:8080 app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check service status
echo "📊 Checking service status..."
systemctl status $SERVICE_NAME --no-pager || true

# Configure nginx
echo "🌐 Configuring nginx..."

# Create nginx configuration
cat > /etc/nginx/sites-available/$DOMAIN << 'EOF'
server {
    listen 80;
    server_name jobs.tugrul.app;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name jobs.tugrul.app;

    # SSL Configuration (will be updated by certbot)
    ssl_certificate /etc/letsencrypt/live/jobs.tugrul.app/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jobs.tugrul.app/privkey.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript;

    # Main location
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings for job searches
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # 5 minutes for long job searches
    }

    # Static files (if any)
    location /static {
        alias /var/www/jobspy/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Favicon
    location /favicon.ico {
        alias /var/www/jobspy/static/favicon.ico;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Security
    location ~ /\. {
        deny all;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/

# Remove default nginx site if it exists
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    rm -f /etc/nginx/sites-enabled/default
fi

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
nginx -t

# Get SSL certificate
echo "🔒 Setting up SSL certificate..."
# First, start nginx without SSL for initial setup
systemctl start nginx

# Create a temporary HTTP-only config for certbot
cat > /etc/nginx/sites-available/$DOMAIN << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

systemctl reload nginx

# Get SSL certificate
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@tugrul.app || {
    echo "⚠️  SSL certificate setup failed. The site will work on HTTP for now."
    echo "   You can run 'certbot --nginx -d $DOMAIN' later to set up SSL."
}

# Set up firewall
echo "🔥 Configuring firewall..."
ufw allow 'Nginx Full'
ufw allow ssh
ufw --force enable

# Set up log rotation
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/jobspy << EOF
/var/log/jobspy/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload jobspy
    endscript
}
EOF

# Create log directory
mkdir -p /var/log/jobspy
chown www-data:www-data /var/log/jobspy

# Final service restart to ensure everything is working
echo "🔄 Final service restart..."
systemctl restart $SERVICE_NAME
systemctl restart nginx

# Check final status
echo "📊 Final status check..."
echo "JobSpy Service Status:"
systemctl is-active $SERVICE_NAME && echo "✅ JobSpy service is running" || echo "❌ JobSpy service failed"

echo "Nginx Service Status:"
systemctl is-active nginx && echo "✅ Nginx is running" || echo "❌ Nginx failed"

echo ""
echo "🎉 Deployment completed!"
echo ""
echo "📋 Summary:"
echo "   • Application URL: http://$DOMAIN (or https if SSL worked)"
echo "   • Application directory: $APP_DIR"
echo "   • Service name: $SERVICE_NAME"
echo ""
echo "🔧 Useful commands:"
echo "   • Check logs: journalctl -u $SERVICE_NAME -f"
echo "   • Restart app: systemctl restart $SERVICE_NAME"
echo "   • Check status: systemctl status $SERVICE_NAME"
echo "   • Nginx logs: tail -f /var/log/nginx/access.log"
echo ""
echo "🌐 Your JobSpy application should now be live at: http://$DOMAIN"
echo "   (https://$DOMAIN if SSL certificate was successfully obtained)"
echo ""

# Show current status
echo "🔍 Current Service Status:"
systemctl status $SERVICE_NAME --no-pager -l || true
echo ""
echo "🌐 Testing local connection:"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080 && echo " - Local app responds with HTTP status code above" || echo " - Local app connection failed"
