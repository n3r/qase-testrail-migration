from service.qase import QaseService
from service.testrail import TestrailService
from support.logger import Logger
from support.mappings import Mappings

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