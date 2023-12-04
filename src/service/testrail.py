from ..repository.testrail import TestrailApiRepository, TestrailDbRepository
from ..api.testrail import TestrailApiClient

class TestrailService:
    def __init__(self, config, logger):
        self.db_repository = None
        self.api_repository = TestrailApiRepository(
            TestrailApiClient(
                base_url = config.get('testrail.api.host'),
                user = config.get('testrail.api.user'),
                token = config.get('testrail.api.password'),
                max_retries = 3,
                backoff_factor = 1
            )
        )

        self.logger = logger

        if config.get('testrail_db_host'):
            self.db_repository = TestrailDbRepository(host=config.get('testrail.db.host'),
                             database=config.get('testrail.db.database'),
                             user=config.get('testrail.db.user'),
                             password=config.get('testrail.db.password'))
            self.db_repository.connect()

        if self.db_repository:
            self.repository = self.db_repository
            self.logger.log('Using TestRail DB repository')
        else:
            self.logger.log('Using TestRail API repository')
            self.repository = self.api_repository

    def get_all_users(self):
        return self.repository.get_all_users()
    
    def get_case_types(self):
        return self.repository.get_case_types()
    
    def get_priorities(self):
        return self.repository.get_priorities()
    
    def get_case_fields(self):
        return self.repository.get_case_fields()
    
    def get_projects(self):
        return self.repository.get_projects()
    
    def get_suites(self, project_id):
        return self.repository.get_suites(project_id)
    
    def get_sections(self, project_id: int, limit: int = 100, offset: int = 0, suite_id: int = 0):
        return self.repository.get_sections(project_id, limit, offset, suite_id)['sections']
    
    def get_cases(self, project_id: int, suite_id: int = 0, limit: int = 250, offset: int = 0):
        return self.repository.get_cases(project_id, suite_id, limit, offset)
    
    def get_runs(self, project_id: int, suite_id: int = 0, created_after: int = 0, limit: int = 250, offset: int = 0):
        return self.repository.get_runs(project_id, suite_id, created_after, limit, offset)

    def get_results(self, run_id: int, limit: int = 250, offset: int = 0):
        return self.repository.get_results(run_id, limit, offset)
    
    def get_attachment(self, attachment_id: int):
        return self.api_repository.get_attachment(attachment_id)
    
    def get_test(self, test_id: int):
        return self.repository.get_test(test_id)
    
    def get_tests(self, run_id: int, limit: int = 250, offset: int = 0):
        return self.repository.get_tests(run_id, limit, offset)
    
    def get_plans(self, project_id: int, limit: int = 250, offset: int = 0):
        return self.repository.get_plans(project_id, limit, offset)
    
    def get_plan(self, plan_id: int):
        return self.repository.get_plan(plan_id)
    
    def get_milestones(self, project_id: int):
        return self.repository.get_milestones(project_id)