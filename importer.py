from support.config_manager import ConfigManager
from support.logger import Logger
from support.mappings import Mappings

from service.qase import QaseService
from service.testrail import TestrailService

from entities.users import Users
from entities.fields import Fields
from entities.projects import Projects
from entities.suites import Suites
from entities.cases import Cases
from entities.runs import Runs
from entities.milestones import Milestones

class TestRailImporter:
    def __init__(self, config: ConfigManager, logger: Logger) -> None:
        self.logger = logger
        self.config = config
        
        self.qase_service = QaseService(config, logger)
        self.testrail_service = TestrailService(config, logger)

        self.active_project_code = None

        self.mappings = Mappings(self.config.get('defaultuser'))

    def start(self):
        #try:
            # Step 1. Build users map
            self.mappings = Users(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings
            ).import_users()
            
            # Step 2. Import custom fields
            self.mappings = Fields(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings,
                self.config,
            ).import_fields()

            # Step 3. Import project and build projects map
            self.mappings = Projects(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings,
                self.config
            ).import_projects()

            # Step 4. Import projects
            
            for project in self.mappings.projects:
                self.logger.print_group(f'Importing project: {project["name"]}' 
                                        + (' (' 
                                        + project['suite_title'] 
                                        + ')' if 'suite_title' in project else ''))
                self.mappings = Suites(
                    self.qase_service, 
                    self.testrail_service, 
                    self.logger, 
                    self.mappings, 
                    self.config
                ).import_suites(project)

                # Step 6. Import milestones
                #self.logger.print_status('Importing milestones', 1, 1, 1)
                self.mappings = Milestones(
                    self.qase_service, 
                    self.testrail_service, 
                    self.logger, 
                    self.mappings
                ).import_milestones(project)

                # Step 7. Import test cases
                Cases(
                    self.qase_service, 
                    self.testrail_service, 
                    self.logger, 
                    self.mappings, 
                    self.config
                ).import_cases(project)

                # Step 8. Import runs
                runs_importer = Runs(
                    self.qase_service, 
                    self.testrail_service, 
                    self.logger, 
                    self.mappings, 
                    self.config
                )

                runs_importer.import_runs(project)
                runs_importer.import_plans(project)

            exit()