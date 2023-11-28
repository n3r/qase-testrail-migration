from service.qase import QaseService
from service.testrail import TestrailService
from support.logger import Logger
from support.mappings import Mappings
from support.config_manager import ConfigManager as Config

import json

class Runs:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings, config: Config) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.config = config
        self.logger = logger
        self.mappings = mappings

        self.created_after = self.config.get('runs_createdafter')

    def import_runs(self, project) -> None:
        suite_id = 0
        limit = 250
        offset = 0
        if ('suite_id' in project and project['suite_id'] > 0):
            suite_id = project['suite_id']

        process = True
            
        while process == True:
            runs = self.testrail.get_runs(
                project_id = project['testrail_id'],
                suite_id = suite_id,
                created_after = self.created_after,
                limit = 250,
                offset = offset
            )
            # Process the runs in the current batch
            for run in runs:
                self._import_run(project, run)

            if len(runs) < limit:
                process = False

            offset = offset + limit

    def _import_run(self, project: list, run: list) -> None:
        
        # Load testrail tests from the run ()
        cases_map = self.__get_cases_for_run(run)
        self.logger.log(f'Found {str(len(cases_map))} cases in the run {run["name"]} [{run["id"]}]')

        # Create a new test run in Qase
        qase_run_id = self.qase.create_run(run, project['code'], list(cases_map.values()))

        if (qase_run_id != None):
            self.logger.log(f'Created a new run in Qase: {qase_run_id}')

            # Import results for the run
            self._import_results_for_run(run, qase_run_id, project, cases_map)
        else:
            self.logger.log(f'Failed to create a new run in Qase for TestRail run {run["name"]} [{run["id"]}]')

    def _import_results_for_run(self, run: list, qase_run_id: str, project: list, cases_map: dict) -> None:
        limit = 250
        offset = 0

        process = True

        while process == True:
            process = self._import_results(run, qase_run_id, project['code'], cases_map, limit, offset)
            offset = offset + limit


    def _import_results(self, tr_run, qase_run_id, qase_code, cases_map, limit, offset) -> None:
        testrail_results = self.testrail.get_results(tr_run['id'], limit, offset)
        self.qase.send_bulk_results(
            tr_run,
            testrail_results,
            qase_run_id,
            qase_code,
            self.config.get('runs_statuses'),
            self.mappings,
            cases_map
        )
        if len(testrail_results) < limit:
            return False
        return True

    def import_plans(self, project: list) -> None:
        limit = 250
        offset = 0

        process = True

        while process == True:
            plans = self.testrail.get_plans(project['testrail_id'], limit, offset)
            for plan in plans['plans']:
                plan = self.testrail.get_plan(plan['id'])
                if 'entries' in plan and plan['entries'] and len(plan['entries']) > 0:
                    for entry in plan['entries']:
                        for run in entry['runs']:
                            self._import_run(project, run)
            if plans['size'] < limit:
                process = False
            offset = offset + limit
    
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