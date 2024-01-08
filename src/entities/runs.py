from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class Runs:
    def __init__(self, 
        qase_service: QaseService, 
        testrail_service: TestrailService, 
        logger: Logger, 
        mappings: Mappings, config: Config, 
        project: list
    ) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.config = config
        self.logger = logger
        self.mappings = mappings
        self.project = project

        self.created_after = self.config.get('runs.created_after')
        self.index = []

    def import_runs(self) -> None:
        self.logger.log(f'[{self.project["code"]}] Importing runs from TestRail project {self.project["name"]}')
        self._build_index()
        self.logger.log(f'[{self.project["code"]}] Found {str(len(self.index))} runs')
        self.index.sort(key=lambda x: x['created_on'])
        i = 0
        for run in self.index:
            i += 1
            self.logger.print_status(f'[{self.project["code"]}] Importing runs', i, len(self.index), 1)
            self._import_run(run)

    def _build_index(self) -> None:
        self.logger.log(f'[{self.project["code"]}] Building runs index')
        if self.project['suite_mode'] == 3:
            for suite_id in self.mappings.suites[self.project['code']]:
                self._build_runs_index_for_suite(suite_id)
        else:
            self._build_runs_index_for_suite(0)
        self._build_plans_index()

    def _build_runs_index_for_suite(self, suite_id: int) -> None:
        self.logger.log(f'[{self.project["code"]}] Building runs index for suite {suite_id}')
        limit = 250
        offset = 0

        while True:
            runs = self.testrail.get_runs(
                project_id = self.project['testrail_id'],
                suite_id = suite_id,
                created_after = self.created_after,
                limit = 250,
                offset = offset
            )
            # Process the runs in the current batch
            for run in runs['runs']:
                self.index.append({
                    'id': run['id'],
                    'name': run['name'],
                    'created_on': run['created_on'],
                    'completed_on': run['completed_on'],
                    'is_completed': run['is_completed'],
                    'milestone_id': run['milestone_id']
                })

            if runs['size'] < limit:
                break

            offset = offset + limit

    def _build_plans_index(self) -> None:
        self.logger.log(f'[{self.project["code"]}] Building plans index')
        limit = 250
        offset = 0

        while True:
            plans = self.testrail.get_plans(self.project['testrail_id'], limit, offset)
            for plan in plans['plans']:
                plan = self.testrail.get_plan(plan['id'])
                if 'entries' in plan and plan['entries'] and len(plan['entries']) > 0:
                    for entry in plan['entries']:
                        for run in entry['runs']:
                            self.index.append({
                                'id': run['id'],
                                'name': run['name'],
                                'created_on': run['created_on'],
                                'completed_on': run['completed_on'],
                                'plan_id': plan['id'],
                                'is_completed': run['is_completed'],
                                'milestone_id': run['milestone_id']
                            })
            if plans['size'] < limit:
                break

            offset = offset + limit

    def _import_run(self, run: list) -> None:
        # Load testrail tests from the run ()
        cases_map = self.__get_cases_for_run(run)
        self.logger.log(f'Found {str(len(cases_map))} cases in the run {run["name"]} [{run["id"]}]')

        milestone_id = self.mappings.milestones[self.project['code']][run['milestone_id']] if run['milestone_id'] in self.mappings.milestones[self.project['code']] else None

        # Create a new test run in Qase
        qase_run_id = self.qase.create_run(run, self.project['code'], list(cases_map.values()), milestone_id)

        if (qase_run_id != None):
            self.logger.log(f'Created a new run in Qase: {qase_run_id}')

            # Import results for the run
            self._import_results_for_run(run, qase_run_id, cases_map)
        else:
            self.logger.log(f'Failed to create a new run in Qase for TestRail run {run["name"]} [{run["id"]}]')

    def _import_results_for_run(self, run: list, qase_run_id: str, cases_map: dict) -> None:
        limit = 250
        offset = 0
        run_results = []

        while True:
            results = self.testrail.get_results(run['id'], limit, offset)
            run_results = run_results + results['results']
            offset = offset + limit
            if results['size'] < limit:
                break

        self.logger.log(f'Found {str(len(run_results))} results for the run {run["name"]} [{run["id"]}]')
        
        # TODO: Split into 1000 chunks if more that 1000
        self._import_results(run, qase_run_id, cases_map, run_results)

    def _import_results(self, tr_run, qase_run_id, cases_map, results) -> None:
        self.qase.send_bulk_results(
            tr_run,
            sorted(results, key=lambda x: x['created_on']),
            qase_run_id,
            self.project['code'],
            self.mappings,
            cases_map
        )

    def __get_cases_for_run(self, run: list) -> dict:
        cases_map = {}
        limit = 250
        offset = 0
        process = True

        while process == True:
            tests = self.testrail.get_tests(run['id'], limit, offset)
            if tests['size'] < limit:
                process = False
            offset = offset + limit
            for test in tests['tests']:
                cases_map[test['id']] = test['case_id']
        return cases_map