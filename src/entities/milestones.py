from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class Milestones:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings

        self.map = {}

    def import_milestones(self, project) -> Mappings:
        self.logger.log("Importing milestones")
        limit = 250
        offset = 0

        milestones = []
        while True:
            tr_milestones = self.testrail.get_milestones(project['testrail_id'], limit, offset)
            milestones += tr_milestones['milestones']
            if tr_milestones['size'] < limit:
                break
            offset += limit

        i = 0
        self.logger.print_status(f'[{project["code"]}] Importing milestones', i, len(milestones), 1)
        for milestone in milestones:
            self.logger.log(f"Importing milestone {milestone['name']}")
            
            id = self.qase.create_milestone(
                project['code'], 
                title=milestone['name'], 
                description=milestone['description'],
                status=milestone['is_completed'],
                due_date=milestone['due_on']
            )
            if id:
                self.map[milestone['id']] = id
            i += 1
            self.logger.print_status(f'[{project["code"]}] Importing milestones', i, len(milestones), 1)
            
        self.mappings.milestones[project['code']] = self.map
        
        return self.mappings