from src.service import QaseService, TestrailService
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

def _get_all_projects(self, service):
        offset = 0
        limit = 250
        projects = []
        while True:
            result = service.get_projects(limit, offset)
            projects = projects + result['projects']
            if result['size'] < limit:
                break
            offset += limit
        
        return projects

qase_service = QaseService(config, logger)

testrail_service = TestrailService(config, logger)

testrail_projects = _get_all_projects(testrail_service)

for project in testrail_projects:
    print(f'Importing project: {project["name"]}. Is Completed: {project["is_completed"]}')
    if (True):
        data = {
            "testrail_id": project['id'],
            "name": project['name'],
            "suite_mode": project['suite_mode']
        }
        code = qase_service.create_project(project['name'], project['announcement'])
        if code:
            data['code'] = code
            print(f'Created project: {project["name"]}')
        else:
            print(f'Failed to create project: {project["name"]}')
    else:
        print(f'Skipping project: {project["name"]}')