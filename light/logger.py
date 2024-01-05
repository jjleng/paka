import logging

# Create a logger
logger = logging.getLogger(__name__)


# "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
def setup_logger(verbose: bool = False, format: str = "%(message)s") -> None:
    # Set the logging level based on the verbose flag
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in logger.handlers:
        logger.removeHandler(handler)

    # Create a console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Create a formatter
    formatter = logging.Formatter(format)

    # Add the formatter to the console handler
    ch.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(ch)


setup_logger()
