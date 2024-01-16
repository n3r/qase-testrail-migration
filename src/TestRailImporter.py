from .support import ConfigManager, Logger, Mappings
from .service import QaseService, TestrailService, QaseScimService
from .entities import Users, Fields, Projects, Suites, Cases, Runs, Milestones

class TestRailImporter:
    def __init__(self, config: ConfigManager, logger: Logger) -> None:
        self.logger = logger
        self.config = config
        self.qase_scim_service = None
        
        self.qase_service = QaseService(config, logger)
        if (config.get('qase.scim_token')):
            self.qase_scim_service = QaseScimService(config, logger)

        self.testrail_service = TestrailService(config, logger)

        self.active_project_code = None

        self.mappings = Mappings(self.config.get('users.default'))

    def start(self):
        # Step 1. Build users map
        self.mappings = Users(
            self.qase_service, 
            self.testrail_service, 
            self.logger, 
            self.mappings,
            self.config,
            self.qase_scim_service,
        ).import_users()

        # Step 2. Import project and build projects map
        self.mappings = Projects(
            self.qase_service, 
            self.testrail_service, 
            self.logger, 
            self.mappings,
            self.config
        ).import_projects()
        
        # Step 3. Import custom fields
        self.mappings = Fields(
            self.qase_service, 
            self.testrail_service, 
            self.logger, 
            self.mappings,
            self.config,
        ).import_fields()

        # Step 4. Import projects data
        for project in self.mappings.projects:
            self.logger.print_group(f'Importing project: {project["name"]}' 
                                    + (' (' 
                                    + project['suite_title'] 
                                    + ')' if 'suite_title' in project else ''))
            
            self.mappings = Milestones(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings,
            ).import_milestones(project)

            self.mappings = Suites(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings, 
                self.config
            ).import_suites(project)

            Cases(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings, 
                self.config
            ).import_cases(project)

            Runs(
                self.qase_service, 
                self.testrail_service, 
                self.logger, 
                self.mappings, 
                self.config,
                project
            ).import_runs()

        exit()