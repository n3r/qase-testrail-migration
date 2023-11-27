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
        
        qase_run_id = self.qase.create_run(run, project['code'])
        limit = 250
        offset = 0

        process = True

        while process == True:
            process = self._import_results(run, qase_run_id, project['code'], limit, offset)
            offset = offset + limit


    def _import_results(self, tr_run, qase_run_id, qase_code, limit, offset) -> None:
        testrail_results = self.testrail.get_results(tr_run['id'], limit, offset)
        self.qase.send_bulk_results(
            tr_run,
            testrail_results,
            qase_run_id,
            qase_code,
            self.config.get('runs_statuses'),
            self.mappings,
            self.testrail
        )
        if len(testrail_results) < limit:
            return False
        return True

    def import_plans(self, project: list) -> None:
        return