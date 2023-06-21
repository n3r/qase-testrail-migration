from importer import TestRailImporter
from testrail import TestRailAPIClient
from config_manager import ConfigManager
from qaseio.api_client import ApiClient
from qaseio.configuration import Configuration
import certifi

print('[Importer] Starting import...')

print('[Importer] Loading config...')
config = ConfigManager()
config.load_config()

print('[Importer] Connecting to TestRail...')
testrail_api = TestRailAPIClient(
    base_url = config.get('testrail_host'),
    user = config.get('testrail_user'),
    token = config.get('testrail_token')
)

print('[Importer] Connecting to Qase...')
configuration = Configuration()
configuration.api_key['TokenAuth'] = config.get('qase_token')
configuration.host = f'https://api.{config.get("qase_host")}/v1'
configuration.ssl_ca_cert = certifi.where()

qase_client = ApiClient(configuration)

# Init
importer = TestRailImporter(config, qase_client, testrail_api)

# Loading projects from test rail
importer.start()

print('[Importer] Import complete!')