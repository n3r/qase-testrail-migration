from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class Milestones:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings, project) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings
        self.project = project

        self.map = {}

    def import_data(self) -> Mappings:
        self.logger.log("Importing milestones")

        testrail_milestones = self.testrail.get_milestones(self.project['testrail_id'])
        
        return self.mappings