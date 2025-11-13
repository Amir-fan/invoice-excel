# Vercel expects a single ASGI handler named "handler"
# Keep this file MINIMAL - Vercel will crash if you do too much here

from app import app

handler = app
