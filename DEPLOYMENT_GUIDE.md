# JobSpy Deployment Guide for jobs.tugrul.app

This guide will help you deploy the JobSpy web application to your server with nginx.

## Prerequisites

- Server with Ubuntu/Debian (or similar Linux distribution)
- Nginx installed and running
- Python 3.10+ installed
- Domain `jobs.tugrul.app` pointing to your server
- SSL certificate (Let's Encrypt recommended)

## Step 1: Server Setup

### 1.1 Connect to your server
```bash
ssh your-username@your-server-ip
```

### 1.2 Update system packages
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install required packages
```bash
sudo apt install python3 python3-pip python3-venv nginx supervisor git -y
```

## Step 2: Deploy Application Files

### 2.1 Create application directory
```bash
sudo mkdir -p /var/www/jobspy
sudo chown $USER:$USER /var/www/jobspy
cd /var/www/jobspy
```

### 2.2 Upload your application files
You can either:

**Option A: Git clone (if you have a repository)**
```bash
git clone your-repo-url .
```

**Option B: Manual upload using scp from your local machine**
```bash
# Run this from your local machine (JobSpy directory)
scp -r app.py requirements.txt run_server.py templates/ your-username@your-server-ip:/var/www/jobspy/
```

**Option C: Create files manually on server**
```bash
# Create the directory structure
mkdir -p /var/www/jobspy/templates
```

Then copy the contents of your files to the server.

### 2.3 Set up Python virtual environment
```bash
cd /var/www/jobspy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.4 Test the application
```bash
python app.py
```
Press Ctrl+C to stop after confirming it works.

## Step 3: Production Configuration

### 3.1 Create production app configuration
Create `/var/www/jobspy/production_app.py`:

```python
#!/usr/bin/env python3
import os
from app import app

# Production configuration
app.config['SECRET_KEY'] = 'your-very-secure-secret-key-change-this'
app.config['DEBUG'] = False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='127.0.0.1', port=port, debug=False)
```

### 3.2 Install Gunicorn for production
```bash
source venv/bin/activate
pip install gunicorn
```

### 3.3 Test Gunicorn
```bash
cd /var/www/jobspy
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8080 app:app
```
Press Ctrl+C to stop after testing.

## Step 4: Create Systemd Service

### 4.1 Create service file
```bash
sudo nano /etc/systemd/system/jobspy.service
```

Add the following content:

```ini
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
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 4.2 Set proper permissions
```bash
sudo chown -R www-data:www-data /var/www/jobspy
sudo chmod -R 755 /var/www/jobspy
```

### 4.3 Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable jobspy
sudo systemctl start jobspy
sudo systemctl status jobspy
```

## Step 5: Configure Nginx

### 5.1 Create nginx configuration
```bash
sudo nano /etc/nginx/sites-available/jobs.tugrul.app
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name jobs.tugrul.app;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name jobs.tugrul.app;

    # SSL Configuration (update paths to your SSL certificates)
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
```

### 5.2 Enable the site
```bash
sudo ln -s /etc/nginx/sites-available/jobs.tugrul.app /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

## Step 6: SSL Certificate (Let's Encrypt)

### 6.1 Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 6.2 Get SSL certificate
```bash
sudo certbot --nginx -d jobs.tugrul.app
```

### 6.3 Set up auto-renewal
```bash
sudo crontab -e
```

Add this line:
```
0 12 * * * /usr/bin/certbot renew --quiet
```

## Step 7: Firewall Configuration

### 7.1 Configure UFW (if using)
```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw enable
```

## Step 8: Monitoring and Logs

### 8.1 Check application logs
```bash
sudo journalctl -u jobspy -f  # Follow logs
sudo journalctl -u jobspy --since "1 hour ago"  # Recent logs
```

### 8.2 Check nginx logs
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 8.3 Monitor application status
```bash
sudo systemctl status jobspy
sudo systemctl status nginx
```

## Step 9: Maintenance Commands

### 9.1 Restart services
```bash
sudo systemctl restart jobspy
sudo systemctl restart nginx
```

### 9.2 Update application
```bash
cd /var/www/jobspy
source venv/bin/activate
git pull  # If using git
pip install -r requirements.txt
sudo systemctl restart jobspy
```

### 9.3 View resource usage
```bash
htop
df -h
free -h
```

## Troubleshooting

### Common Issues:

1. **Service won't start**
   ```bash
   sudo journalctl -u jobspy --no-pager
   ```

2. **Permission errors**
   ```bash
   sudo chown -R www-data:www-data /var/www/jobspy
   ```

3. **Port already in use**
   ```bash
   sudo netstat -tlnp | grep :8080
   ```

4. **SSL certificate issues**
   ```bash
   sudo certbot certificates
   sudo certbot renew --dry-run
   ```

5. **Nginx configuration errors**
   ```bash
   sudo nginx -t
   ```

## Performance Optimization

### 8.1 Increase Gunicorn workers for high traffic
Edit `/etc/systemd/system/jobspy.service`:
```ini
ExecStart=/var/www/jobspy/venv/bin/gunicorn -w 4 -b 127.0.0.1:8080 app:app
```

### 8.2 Add rate limiting to nginx
Add to server block:
```nginx
limit_req_zone $binary_remote_addr zone=jobspy:10m rate=10r/m;
limit_req zone=jobspy burst=5 nodelay;
```

## Security Checklist

- [ ] SSL certificate installed and working
- [ ] Firewall configured
- [ ] Application running as www-data user
- [ ] Secret key changed from default
- [ ] Debug mode disabled in production
- [ ] Regular backups configured
- [ ] Log rotation configured
- [ ] Security headers enabled in nginx

## Final Test

Visit `https://jobs.tugrul.app` and verify:
- [ ] Site loads over HTTPS
- [ ] Job search functionality works
- [ ] Downloads work (CSV/Excel)
- [ ] Mobile responsiveness
- [ ] No console errors

Your JobSpy application should now be live at `https://jobs.tugrul.app`!

