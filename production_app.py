#!/usr/bin/env python3
"""
Production configuration for JobSpy web application
"""
import os
from app import app

# Production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key-in-production')
app.config['DEBUG'] = False

# Additional production settings
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='127.0.0.1', port=port, debug=False)
