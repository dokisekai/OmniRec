import logging
import os
import sys

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("multimodal_recommender")

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from src.api.server import app

def main():
    logger.info("==================================================")
    logger.info("Starting Antigravity Multimodal Recommender Server...")
    logger.info("Dashboard UI: http://localhost:8000/")
    logger.info("==================================================")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
