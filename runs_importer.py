from db import TestrailDbRepository
from config_manager import ConfigManager
from qaseio.api.projects_api import ProjectsApi
from qaseio.api.runs_api import RunsApi
from qaseio.api.authors_api import AuthorsApi
from qaseio.api.results_api import ResultsApi
from qaseio.models import RunCreate, ResultCreateBulk
from qaseio.exceptions import ApiException
import re
import json
from typing import List
from urllib.parse import quote, unquote
from datetime import datetime

class ImportException(Exception):
    pass

class RunsImporter:
    def __init__(self, config: ConfigManager, QaseClient, repository: TestrailDbRepository) -> None:
        self.qase = QaseClient
        self.db = repository
        self.config = config
        self.qase_projects = []
        self.projects = []
        self.users_map = {}
        self.active_project_code = None
        self.defects = []
        self.created_after = self.config.get('createdafter') if self.config.get('createdafter') else 0

    def start(self):
        try:
            self.db.connect()

            print('[Importer] Building users map...')
            self._build_users_map()

            print('[Importer] Loading projects from Qase')
            self._get_projects()

            print('[Importer] Loading projects from TestRail...')
            self.projects = self.db.get_projects()
            if self.projects:
                # Importing test cases
                for project in self.projects:
                    if (project['is_completed'] == False and self._check_import(project['name'])):
                        if (project['suite_mode'] == 3):
                            print('[Importer] Loading suites from TestRail...')
                            suites = self.db.get_suites(project['id'])
                            if suites:
                                print('[Importer] Found suites: ' + str(len(suites)))
                                project['suites'] = suites

                                if self.config.get('suitesasprojects') == False:
                                    project['code'] = self._short_code(project['name'])
                                else:
                                    project['code'] = self._short_code(project['name'])
                        else:
                            project['code'] = self._short_code(project['name'])

                # Importing test runs
                for project in self.projects:
                    if (project['is_completed'] == False and self._check_import(project['name'])):
                        if project['suite_mode'] == 3:
                            suites_to_import = self._get_suites_to_import(project['name'])
                            for suite in project['suites']:
                                if (suite['name'] in suites_to_import):
                                    if self.config.get('suitesasprojects') == True:
                                        self.active_project_code = self._short_code(suite['name'])
                                    else:
                                        self.active_project_code = project['code']
                                    self._import_runs(project['id'], suite['id'])
                        else:
                            self.active_project_code = project['code']
                            self._import_runs(project['id'], suite['id'])
                    self.active_project_code = None

            print('[Importer] Dumping defects to file defects.json')
            self._dump_defects()
        except ImportException as e:
            print('[Importer] Error: ' + str(e))
            print('[Importer] Import failed!')
        
    def _build_users_map(self):
        testrail_users = self.db.get_users()
        qase_users = self._get_qase_users()

        for testrail_user in testrail_users:
            flag = False
            for qase_user in qase_users:
                if (testrail_user['email'] == qase_user['email'] and testrail_user['is_active'] == True):
                    self.users_map[testrail_user['id']] = qase_user['id']
                    flag = True
                    print(f"[Importer] User {testrail_user['email']} found in Qase as {qase_user['email']}")
                    break
            if (flag == False):
                # Not found, using default user
                self.users_map[testrail_user['id']] = self.config.get('defaultuser')
                print(f"[Importer] User {testrail_user['email']} not found in Qase, using default user {self.config.get('defaultuser')}")
    
    def _get_qase_users(self):
        flag = True
        limit = 100
        offset = 0
        users = []
        while flag:
            try:
                api_instance = AuthorsApi(self.qase)
                # Get all authors.
                api_response = api_instance.get_authors(limit=limit, offset=offset, type="user")
                if (api_response.status and api_response.result.entities):
                    users += api_response.result.entities
            except ApiException as e:
                print("Exception when calling AuthorsApi->get_authors: %s\n" % e)
            if (len(api_response.result.entities) < limit):
                flag = False

        return users

    def _get_projects(self) -> str:
        try:
            api_response = ProjectsApi(self.qase).get_projects()
            projects = api_response.result.entities
            for project in projects:
                self.qase_projects.append(project.code)
        except ApiException as e:
            error = json.loads(e.body)
            if (error['status'] == False):
                print('[Importer] Unable to load Qase projects')
            raise ImportException(e)

    # Method generates short code that will be used as a project code in from a string
    def _short_code(self, s: str) -> str:
        s = re.sub('[!@#$%^&*().,1234567890]', '', s)  # remove special characters
        words = s.split()

        if len(words) > 1:  # if the string contains multiple words
            code = ''.join(word[0] for word in words).upper()
        else:
            code = s.upper()

        return code[:10]  # truncate to 10 characters
    
    def _get_user_id(self, id: int) -> int:
        if (id in self.users_map):
            return self.users_map[id]
        return int(self.config.get('defaultuser'))
    
    # Function checks if the project should be imported
    def _check_import(self, project_title: str) -> bool:
        projects = self.config.get('projects')
        if not projects:
            return True
        for project in projects:
            if isinstance(project, str) and project == project_title:
                return True
            elif isinstance(project, dict) and project['name'] == project_title:
                return True
        return False
    
    def _get_suites_to_import(self, project_title: str) -> List:
        suites = []
        projects = self.config.get('projects')
        if projects:
            for project in projects:
                if isinstance(project, dict) and project['name'] == project_title and project['suites']:
                    suites = project['suites']
        return suites

    def _import_runs(self, project_id, suite_id = None) -> None:
        created_after = self.config.get('createdafter')
        count = self.db.count_runs(project_id, created_after, suite_id)
        print('[Importer] Found ' + str(count) + ' test runs in project id: ' + str(project_id))
        batch_size = 100
        num_batches = (count + batch_size - 1) // batch_size

        for batch_number in range(num_batches):
            offset = batch_number * batch_size
            runs = self.db.get_runs(
                project_id = project_id,
                suite_id = suite_id,
                created_after = created_after,
                limit = batch_size,
                offset = offset
            )
            # Process the runs in the current batch
            for run in runs:
                results_count = self.db.count_results(run['id'])
                print('[Importer] Found ' + str(results_count) + ' test results in test run id: ' + str(run['id']))
                if not self.config.get('dry'):
                    qase_run_id = self._create_run(run, self.active_project_code)
                    result_batch_size = 1000

                    result_num_batches = (results_count + result_batch_size - 1) // result_batch_size

                    for result_batch_number in range(result_num_batches):
                        offset = result_batch_number * result_batch_size
                        self._import_results(run, qase_run_id, result_batch_size, offset)

                    
    def _import_results(self, tr_run, qase_run_id, limit, offset):
        self._send_bulk_results(
            tr_run,
            self.db.get_results(tr_run['id'], limit, offset), 
            qase_run_id
        )

    def _dump_defects(self):
        if (self.defects):
            with open('defects.json', 'w') as outfile:
                json.dump(self.defects, outfile)

    def _send_bulk_results(self, tr_run, results, qase_run_id):
        res = []

        if (results):
            status_map = self.config.get('statuses')
            for result in results:
                elapsed = int(result['elapsed']) if result["elapsed"] else 0
                if not result['tested_on']:
                    if (tr_run['completed_on']):
                        start_time = tr_run['completed_on']
                else:
                    start_time = result['tested_on'] - elapsed

                data = {
                    "case_id": result["case_id"],
                    "status": status_map.get(str(result["status_id"]), "skipped"),
                    "time_ms": elapsed*1000, # converting to miliseconds
                    "comment": str(result['comment'])
                }

                if (start_time):
                    data['start_time'] = start_time

                if (result['defects']):
                    self.defects.append(
                        {
                            "case_id": result["case_id"],
                            "defects": result['defects'],
                            "run_id": qase_run_id
                        }
                    )

                if result['tested_by']:
                    data['author_id'] = self._get_user_id(result['tested_by'])

                res.append(data)

            api_results = ResultsApi(self.qase)
            print(f"[Importer] Sending results to test run {qase_run_id}. ")
            api_results.create_result_bulk(
                    code=self.active_project_code,
                    id=int(qase_run_id),
                    result_create_bulk=ResultCreateBulk(
                        results=res
                    )
                )

    def _create_run(self, run, project_code):
        api_instance = RunsApi(self.qase)

        try:
            response = api_instance.create_run(code=project_code, run_create=RunCreate(
                title = run['name'],
                start_time = datetime.fromtimestamp(run['created_on']).strftime('%Y-%m-%d %H:%M:%S'),
                end_time = datetime.fromtimestamp(run['completed_on']).strftime('%Y-%m-%d %H:%M:%S'),
            ))
            print('[Importer] Test run ' + run['name'] + ' created: ' + str(response.result.id))
            return response.result.id
        except Exception as e:
            print('[Importer] Unable to create test run')
            print(e)
            