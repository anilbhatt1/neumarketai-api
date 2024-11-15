import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_logging():
    logger.info("This is an info log")
    logger.debug("This is a debug log")  # This won't show unless the level is set to DEBUG
    logger.warning("This is a warning log")
    logger.error("This is an error log")
    logger.critical("This is a critical log")

if __name__ == "__main__":
    test_logging()