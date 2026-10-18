"""
Entrypoint script for Smart LPG Leak Detection & Automatic Shut-Off System.

Usage:
    python run.py
"""

import sys
import uvicorn
from backend.config import settings

if __name__ == "__main__":
    print("=" * 70)
    print(" Smart LPG Leak Detection & Automatic Shut-Off System")
    print(" [ACADEMIC PROTOTYPE & SIMULATION]")
    print("=" * 70)
    print(f" * Dashboard URL : http://{settings.host}:{settings.port}")
    print(f" * Analytics URL : http://{settings.host}:{settings.port}/analytics.html")
    print(f" * API Docs (Swagger) : http://{settings.host}:{settings.port}/docs")
    print("=" * 70)
    
    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )

