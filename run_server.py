#!/usr/bin/env python3
"""
Production server runner for JobSpy web application
"""
import os
from app import app

if __name__ == '__main__':
    # Get configuration from environment variables
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting JobSpy server on {host}:{port}")
    print(f"Debug mode: {debug}")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )
