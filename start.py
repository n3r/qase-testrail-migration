from src import TestRailImporter, TestRailImporterSync
from src.support.config_manager import ConfigManager
from src.support.logger import Logger

config = ConfigManager()
try:
    config.load_config()
except Exception as e:
    config.build_config()

prefix = config.get('prefix')
if prefix == None:
    prefix = ''

logger = Logger(config.get('debug'), prefix=prefix)

if config.get('sync'):
    importer = TestRailImporterSync(config, logger)
else:
    importer = TestRailImporter(config, logger)

importer.start()
