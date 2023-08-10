from runs_importer import RunsImporter
from config_manager import ConfigManager
from qaseio.api_client import ApiClient
from qaseio.configuration import Configuration
from db import TestrailDbRepository
import certifi

print('[Importer] Starting import...')

print('[Importer] Loading config...')
config = ConfigManager("./runs.config.json")
config.load_config()

print('[Importer] Connecting to TestRail DB...')
repository = TestrailDbRepository(host=config.get('db_host'),
                             database=config.get('db_database'),
                             user=config.get('db_user'),
                             password=config.get('db_password'))

print('[Importer] Connecting to Qase...')
configuration = Configuration()
configuration.api_key['TokenAuth'] = config.get('qase_token')
configuration.host = f'https://api.{config.get("qase_host")}/v1'
configuration.ssl_ca_cert = certifi.where()

qase_client = ApiClient(configuration)

# Init
importer = RunsImporter(config, qase_client, repository)

# Loading projects from test rail
importer.start()

print('[Importer] Runs import complete!')
