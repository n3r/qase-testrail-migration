from importer import TestRailImporter
from support.config_manager import ConfigManager
from support.logger import Logger

config = ConfigManager()
config.load_config()

logger = Logger(config.get('debug'), config.get('logfile'))

logger.log('Init importer')

# Init
importer = TestRailImporter(config, logger)

logger.log('Start import')

# Loading projects from test rail
importer.start()

logger.log('Import finished')