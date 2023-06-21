from testrail import TestRailAPIClient
from config_manager import ConfigManager
from qaseio.api.projects_api import ProjectsApi
from qaseio.api.suites_api import SuitesApi
from qaseio.api.attachments_api import AttachmentsApi
from qaseio.api.cases_api import CasesApi
from qaseio.api.authors_api import AuthorsApi
from qaseio.models import ProjectCreate, SuiteCreate, BulkRequest, BulkRequestCasesInner
from qaseio.exceptions import ApiException
from io import BytesIO
import re
import json
from typing import List, Optional
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class ImportException(Exception):
    pass

class TestRailImporter:
    def __init__(self, config: ConfigManager, QaseClient, TestRailClient: TestRailAPIClient) -> None:
        self.qase = QaseClient
        self.testrail = TestRailClient
        self.config = config
        self.projects = []
        self.suites = {}
        self.suites_map = {}
        self.users_map = {}

    def start(self):
        try:
            print('[Importer] Building users map...')
            self._build_users_map()

            print('[Importer] Loading projects from TestRail...')
            self.projects = self.testrail.send_get('get_projects')
            if self.projects:
                print('[Importer] Found projects: ' + str(len(self.projects)))
                for project in self.projects:
                    if (project['is_completed'] == False):
                        if (project['suite_mode'] == 3 and self.config.get('suitesasprojects') == True):
                            print('[Importer] Loading suites from TestRail...')
                            suites = self.testrail.send_get('get_suites/' + str(project['id']))
                            if suites:
                                print('[Importer] Found suites: ' + str(len(suites)))
                                project['suites'] = suites
                                for suite in suites:
                                    code = self._create_project(suite['name'], suite['description'])
                                    self.suites_map[code] = {}
                                    self._create_suites(code, project['id'], suite['id'])
                                
                        else:
                            code = self._create_project(project['title'], project['announcement'])
                            self._create_suites(code, project['id'], None)
                self._import_custom_fields()

                # Importing test cases
                for project in self.projects:
                    if (project['is_completed'] == False):
                        if (project['suite_mode'] == 3 and self.config.get('suitesasprojects') == True):
                            for suite in project['suites']:
                                code = self._short_code(suite['name'])
                                self._import_test_cases(project['id'], code, suite['id'])
                        else:
                            self._import_test_cases(project['id'], project['code'])
        except ImportException as e:
            print('[Importer] Error: ' + str(e))
            print('[Importer] Import failed!')

    def _build_users_map(self):
        testrail_users = self._get_testrail_users()
        qase_users = self._get_qase_users()

        for testrail_user in testrail_users:
            for qase_user in qase_users:
                if (testrail_user['email'] == qase_user['email'] and testrail_user['is_active'] == True):
                    self.users_map[testrail_user['id']] = qase_user['id']
                    print(f"[Importer] User {testrail_user['email']} found in Qase as {qase_user['email']}")
                    break
            # Not found, using default user
            self.users_map[testrail_user['id']] = self.config.get('defaultuser')
            print(f"[Importer] User {testrail_user['email']} not found in Qase, using default user {self.config.get('defaultuser')}")

    def _get_testrail_users(self):
        return self.testrail.send_get('get_users')
    
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

    # Recursively get all suites
    def _get_suites(self, project_id, offset = 0, limit = 250) -> List:
        suites = self.testrail.send_get('get_suites/' + str(project_id) + f'&limit={limit}')
        if (suites and len(suites) == limit):
            suites += self.get_suites(project_id, offset + limit, limit)
        return suites
    
    def _create_suites(self, qase_code: str, testrail_project_id: int, suite_id: Optional[int]):
        sections = self._get_sections(testrail_project_id, suite_id)
        for section in sections:
            print(f"[Importer] Creating suite in Qase {qase_code} : {section['name']} ({section['id']})")
            testrail_attachments = self._check_attachments(section['description'])
            if (testrail_attachments):
                attachments_map = self._import_attachments(qase_code, testrail_attachments)
                section['description'] = self._replace_attachments(string=section['description'], map=attachments_map)

            api_instance = SuitesApi(self.qase)
            api_response = api_instance.create_suite(
                code = qase_code.upper(),
                suite_create=SuiteCreate(
                    title = section['name'],
                    description = section['description'] if section['description'] else "",
                    preconditions="",
                    parent_id=self.suites_map[qase_code][section['parent_id']] if section['parent_id'] and self.suites_map[qase_code][section['parent_id']] else None
                )
            )
            self.suites_map[qase_code][section['id']] = api_response.result.id
    
    # Recursively get all sections
    def _get_sections(self, project_id, suite_id = 0, offset = 0, limit = 3) -> List:
        if (suite_id == 0):
            sections = self.testrail.send_get('get_sections/' + str(project_id) + f'&limit={limit}&offset={offset}')
        else:
            sections = self.testrail.send_get('get_sections/' + str(project_id) + f'&suite_id={suite_id}&limit={limit}&offset={offset}')
        if (sections and len(sections) == limit):
            sections += self.get_sections(project_id, suite_id, offset + limit, limit)
        return sections

    # Method generates short code that will be used as a project code in from a string
    def _short_code(self, s):
        words = s.split()

        if len(words) > 1:  # if the string contains multiple words
            code = ''.join(word[0] for word in words)
        else:  # if the string is a single word
            code = s.upper()

        return code[:10].upper()  # truncate to 10 characters
    
    # Method creates project in Qase
    def _create_project(self, title: str, description: Optional[str]) -> str:
        api_instance = ProjectsApi(self.qase)

        print('[Importer] Creating project in Qase: ' + title)

        code = self._short_code(title)

        try:
            api_response = api_instance.create_project(
                project_create = ProjectCreate(
                    title = title,
                    code = code,
                    description = description if description else "",
                )
            )
        except ApiException as e:
            error = json.loads(e.body)
            if (error['status'] == False and error['errorFields'][0]['error'] == 'Project with the same code already exists.'):
                return code
            
            print('[Importer] Exception when calling ProjectsApi->create_project: %s\n' % e)
            raise ImportException(e)
        print('[Importer] Project created: ' + str(api_response.result.code))

        return code
    
    def _check_attachments(self, string: str) -> List:
        if (string):
            return re.findall(r'\(index\.php\?\/attachments\/get\/(\d+)\)', string)
        return []
    
    def _import_attachments(self, code, testrail_attachments: List) -> dict:
        attachments_map = {}
        for attachment in testrail_attachments:
            print('[Importer] Importing attachment: ' + attachment)
            attachment_data = self._get_attachment_meta(self.testrail.send_get('get_attachment/' + attachment))
            
            api_attachments = AttachmentsApi(self.qase)

            response = api_attachments.upload_attachment(
                    code, file=[attachment_data],
                ).result
            if response:
                attachments_map[attachment] = response[0]
        return attachments_map
    
    def _get_attachment_meta(self, data):
        content = BytesIO(data.content)
        content.mime = data.headers.get('Content-Type', '')
        content.name = "attachment"
        filename_header = data.headers.get('Content-Disposition', '')
        match = re.search(r"filename\*=UTF-8''(.+)", filename_header)
        if match:
            content.name = urllib.parse.unquote(match.group(1))

        return content

    def _replace_attachments(self, map: dict, string: str) -> str:
        new = re.sub(
            r'!\[\]\(index\.php\?\/attachments\/get\/(\d+)\)',
            lambda match: f'![{map[match.group(1)]["filename"]}]({map[match.group(1)]["url"]})',
            string
        )
        return new
    
    def _import_custom_fields(self):
        print('[Importer] Loading custom fields from TestRail...')
        custom_fields = self.testrail.send_get('get_case_fields')
        print('[Importer] Found custom fields: ' + str(len(custom_fields)))

    def _import_test_cases(self, project_id: int, project_code: str, suite_id: Optional[int] = None):
        limit = 250
        offset = 0
        api_instance = CasesApi(self.qase)

        def process_cases(offset, limit):
            cases = self._get_cases(project_id, suite_id, offset, limit)
            if len(cases) > 0:
                bulk_request = BulkRequest(cases=self._prepare_cases(project_code, cases))
                try:
                    # Create a new test cases.
                    api_response = api_instance.bulk(project_code.upper(), bulk_request)
                except ApiException as e:
                    print("Exception when calling CasesApi->bulk: %s\n" % e)

            return len(cases)

        threads = self.config.get('threads') if self.config.get('threads') else 5
        with ThreadPoolExecutor(max_workers=threads) as executor:
            while True:
                print('[Importer] Thread has started')
                future = executor.submit(process_cases, offset, limit)
                # Wait for the future to complete and get its result
                case_count = future.result()
                # Update the offset
                offset += limit
                # If the number of cases is less than the limit, break the loop
                if case_count < limit:
                    break

    def _get_cases(self, project_id: int, suite_id: Optional[int] = None, offset: int = 0, limit: int = 250) -> List:
        if (suite_id):
            cases = self.testrail.send_get('get_cases/' + str(project_id) + f'&suite_id={suite_id}&limit={limit}&offset={offset}')
        else:
            cases = self.testrail.send_get('get_cases/' + str(project_id) + f'&limit={limit}&offset={offset}')
        return cases
    
    def _prepare_cases(self, project_code: str, cases: List) -> List:
        result = []
        for case in cases:
            print(case)
            data = {
                'id': case['id'],
                'title': case['title'],
                'created_at': datetime.fromtimestamp(case['created_on']),
                'updated_at': datetime.fromtimestamp(case['updated_on']),
                'author_id': self._get_user_id(case['created_by']),
            }

            # import custom fields



            suite_id = self._get_suite_id(code = project_code, section_id = case['section_id'])
            if (suite_id):
                data['suite_id'] = suite_id

            result.append(
                BulkRequestCasesInner(
                    **data
                )
            )
        return result
    
    def _get_suite_id(self, code: str, section_id: Optional[int] = None) -> int:
        if (section_id and section_id in self.suites_map[code]):
            return self.suites_map[code][section_id]
        return None
    
    def _get_user_id(self, id: int) -> int:
        if (id in self.users_map):
            return self.users_map[id]
        return int(self.config.get('defaultuser'))