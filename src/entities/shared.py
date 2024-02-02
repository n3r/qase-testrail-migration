from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class SharedSteps:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings

        self.map = {}
        self.logger.divider()
        self.i = 0

    def import_shared_steps(self, project) -> Mappings:
        self.logger.log(f"[{project['code']}][Shared Steps] Importing shared steps")
        limit = 250
        offset = 0

        shared_steps = []
        while True:
            tr_shared = self.testrail.get_shared_steps(project['testrail_id'], limit, offset)
            shared_steps += tr_shared['shared_steps']
            if tr_shared['size'] < limit:
                break
            offset += limit

        self.mappings.stats.add_entity_count(project['code'], 'shared_steps', 'testrail', len(shared_steps))
            
        self.logger.log(f"[{project['code']}][Shared Steps] Found {len(shared_steps)} shared steps")

        self.logger.print_status(f'[{project["code"]}] Importing shared steps', self.i, len(shared_steps), 1)
        for step in shared_steps:
            id = self.qase.create_shared_step(project["code"], step['title'], step['custom_steps_separated'])
            if id:
                self.mappings.stats.add_entity_count(project['code'], 'shared_steps', 'qase')
                self.map[step['id']] = id
            self.i += 1
            self.logger.print_status(f'[{project["code"]}] Importing shared steps', self.i, len(shared_steps), 1)
            
        self.mappings.shared_steps[project["code"]] = self.map
        
        return self.mappings