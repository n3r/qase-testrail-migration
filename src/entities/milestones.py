from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class Milestones:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings

        self.map = {}

    def import_milestones(self, project: list) -> Mappings:
        self.logger.log("Importing milestones")
        
        return self.mappings