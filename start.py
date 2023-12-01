from src import TestRailImporter
from src.support.config_manager import ConfigManager
from src.support.logger import Logger

config = ConfigManager()
try:
    config.load_config()
except Exception as e:
    config.build_config()

logger = Logger(config.get('debug'), config.get('logfile'))

# Init
importer = TestRailImporter(config, logger)

importer.start()