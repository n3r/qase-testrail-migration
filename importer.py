from testrail import TestRailAPIClient
from config_manager import ConfigManager
from qaseio.api.projects_api import ProjectsApi
from qaseio.api.suites_api import SuitesApi
from qaseio.api.attachments_api import AttachmentsApi
from qaseio.api.cases_api import CasesApi
from qaseio.api.authors_api import AuthorsApi
from qaseio.api.custom_fields_api import CustomFieldsApi
from qaseio.models import ProjectCreate, SuiteCreate, BulkRequest, BulkRequestCasesInner, CustomFieldCreate, CustomFieldCreateValueInner, TestStepCreate
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
        self.types_map = {}
        self.priorities_map = {}
        self.active_project_code = None
        # A map of TestRail custom fields types to Qase custom fields types
        self.custom_fields_type_map = {
            1: 1,
            2: 0,
            3: 2,
            4: 7,
            5: 4,
            6: 3,
            7: 8,
            8: 9,
            12: 6,
        }
        self.qase_fields_type_map = {
            "number": 0,
            "string": 1,
            "text": 2,
            "selectbox": 3,
            "checkbox": 4,
            "radio": 5,
            "multiselect": 6,
            "url": 7,
            "user": 8,
            "datetime": 9,
        }
        self.custom_fields_map = {}
        # Step fields. Used to determine if a field is a step field or not during import
        self.step_fields = []

    def start(self):
        try:
            print('[Importer] Building users map...')
            self._build_users_map()

            print('[Importer] Loading projects from TestRail...')
            self.projects = self.testrail.send_get('get_projects')
            if self.projects:
                print('[Importer] Found projects: ' + str(len(self.projects)))
                for project in self.projects:
                    if (project['is_completed'] == False and self._check_import(project['name'])):
                        if (project['suite_mode'] == 3 and self.config.get('suitesasprojects') == True):
                            print('[Importer] Loading suites from TestRail...')
                            suites = self.testrail.send_get('get_suites/' + str(project['id']))
                            if suites:
                                print('[Importer] Found suites: ' + str(len(suites)))
                                project['suites'] = suites

                                suites_to_import = self._get_suites_to_import(project['name'])

                                for suite in suites:
                                    if (suite['name'] in suites_to_import):
                                        code = self._create_project(suite['name'], suite['description'])
                                        self.suites_map[code] = {}
                                        self._create_suites(code, project['id'], suite['id'])
                                
                        else:
                            code = self._create_project(project['title'], project['announcement'])
                            self._create_suites(code, project['id'], None)
                self._import_custom_fields()

                # Importing test cases
                for project in self.projects:
                    if (project['is_completed'] == False and self._check_import(project['name'])):
                        if (project['suite_mode'] == 3 and self.config.get('suitesasprojects') == True):
                            suites_to_import = self._get_suites_to_import(project['name'])
                            for suite in project['suites']:
                                if (suite['name'] in suites_to_import):
                                    self.active_project_code = self._short_code(suite['name'])
                                    self._import_test_cases(project['id'], suite['id'])
                                    if self.config.get('runs') == True:
                                        self._import_runs(project['id'], suite['id'])
                        else:
                            self.active_project_code = project['code']
                            self._import_test_cases(project['id'])
                            if self.config.get('runs') == True:
                                self._import_runs(project['id'])
                    self.active_project_code = None
        except ImportException as e:
            print('[Importer] Error: ' + str(e))
            print('[Importer] Import failed!')

    def _build_users_map(self):
        testrail_users = self.testrail.send_get('get_users')
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
            section['description'] = self._check_and_replace_attachments(section['description'], qase_code)

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
    def _short_code(self, s: str) -> str:
        s = re.sub('[!@#$%^&*()]', '', s)  # remove special characters
        words = s.split()

        if len(words) > 1:  # if the string contains multiple words
            code = ''.join(word[0] for word in words).upper()
        else:
            code = s.upper()

        return code[:10]  # truncate to 10 characters
    
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
                print('[Importer] Project with the same code already exists: ' + code + '. Using existing project.')
                return code
            
            print('[Importer] Exception when calling ProjectsApi->create_project: %s\n' % e)
            raise ImportException(e)
        print('[Importer] Project created: ' + str(api_response.result.code))

        return code
    
    def _check_attachments(self, string: str) -> List:
        if (string):
            return re.findall(r'\(index\.php\?\/attachments\/get\/(\d+)\)', str(string))
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
        print('[Importer] Importing system fields from TestRail...')
        self._create_types_map()
        self._create_priorities_map()

        api_instance = CustomFieldsApi(self.qase)
        qase_custom_fields = api_instance.get_custom_fields(entity='case', limit=100).result.entities

        custom_fields = self.testrail.send_get('get_case_fields')
        print(f'[Importer] Found {str(len(custom_fields))} custom fields')

        fields_to_import = self.config.get('fields')
        
        if len(fields_to_import) == 0 and not fields_to_import:
            for field in custom_fields:
                if field['system_name'].startswith('custom_'):
                    fields_to_import.append(field['name'])

        for field in custom_fields:
            if field['name'] in fields_to_import and field['is_active']:
                if (field['type_id'] in self.custom_fields_type_map):
                    print('[Importer] Creating custom field: ' + field['name'])
                    self._create_custom_field(field, api_instance, qase_custom_fields)
            else:
                print('[Importer] Skipping custom field: ' + field['name'])

            if (field['type_id'] == 10):
                self.step_fields.append(field['name'])

    def _create_custom_field(self, field, api_instance, qase_fields):

        if (qase_fields and len(qase_fields) > 0):
            for qase_field in qase_fields:
                if qase_field.title == field['label'] and self.custom_fields_type_map[field['type_id']] == self.qase_fields_type_map[qase_field.type.lower()]:
                    print('[Importer] Custom field already exists: ' + field['label'])
                    field['qase_id'] = qase_field.id
                    self.custom_fields_map[field['name']] = field
                    return

        data = {
            'title': field['label'],
            'entity': 0, # 0 - case, 1 - run, 2 - defect,
            'type': self.custom_fields_type_map[field['type_id']],
            'value': [],
            'is_filterable': True,
            'is_visible': True,
            'is_required': False,
            'is_enabled_for_all_projects': True,
        }
        if (self._get_default_value(field)):
            data['default_value'] = self._get_default_value(field)
        if (field['type_id'] == 12 or field['type_id'] == 6):
            values = self.__split_values(field['configs'][0]['options']['items'])
            for key, value in values.items():
                data['value'].append(
                    CustomFieldCreateValueInner(
                        id=int(key)+1, # hack as in testrail ids can start from 0
                        title=value,
                    ),
                )
        try:
            api_response = api_instance.create_custom_field(custom_field_create=CustomFieldCreate(**data))
            if (api_response.status == False):
                print('[Importer] Error creating custom field: ' + field['name'])
            else:
                field['qase_id'] = api_response.result.id
                self.custom_fields_map[field['name']] = field
                print('[Importer] Custom field created: ' + field['name'])
        except ApiException as e:
            print('[Importer] Exception when calling CustomFieldsApi->create_custom_field: %s\n' % e)

    def _get_default_value(self, field):
        if 'configs' in field:
            if len(field['configs']) > 0:
                if 'options' in field['configs'][0]:
                    if 'default_value' in field['configs'][0]['options']:
                        return field['configs'][0]['options']['default_value']
        return None

    def __split_values(self, string: str) -> dict:
        items = string.split('\n')  # split items into a list
        result = {}
        for item in items:
            key, value = item.split(', ')  # split each item into a key and a value
            result[key] = value
        return result

    def _create_types_map(self):
        tr_types = self.testrail.send_get('get_case_types')
        qase_types = self.config.get('types')

        for tr_type in tr_types:
            self.types_map[tr_type['id']] = 1
            for qase_type_id in qase_types:
                if tr_type['name'].lower() == qase_types[qase_type_id].lower():
                    self.types_map[tr_type['id']] = int(qase_type_id) - 1

    def _create_priorities_map(self):
        tr_priorities = self.testrail.send_get('get_priorities')
        qase_priorities = self.config.get('priorities')
        for tr_priority in tr_priorities:
            self.priorities_map[tr_priority['id']] = 1
            for qase_priority_id in qase_priorities:
                if tr_priority['name'].lower() == qase_priorities[qase_priority_id].lower():
                    self.priorities_map[tr_priority['id']] = int(qase_priority_id)

    def _import_test_cases(self, project_id: int, suite_id: Optional[int] = None):
        limit = 250
        offset = 0
        api_instance = CasesApi(self.qase)

        def process_cases(offset, limit):
            cases = self._get_cases(project_id, suite_id, offset, limit)
            if len(cases) > 0:
                bulk_request = BulkRequest(cases=self._prepare_cases(self.active_project_code, cases))
                try:
                    # Create a new test cases.
                    api_response = api_instance.bulk(self.active_project_code, bulk_request)
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
            data = {
                'id': case['id'],
                'title': case['title'],
                'created_at': datetime.fromtimestamp(case['created_on']),
                'updated_at': datetime.fromtimestamp(case['updated_on']),
                'author_id': self._get_user_id(case['created_by']),
                'steps': [],
                'custom_field': {},
            }

            # import custom fields
            data = self._import_custom_fields_for_case(case=case, data=data, project_code=project_code)

            data = self._set_priority(case=case, data=data)
            data = self._set_type(case=case, data=data)
            data = self._set_suite(case=case, data=data, project_code=project_code)

            result.append(
                BulkRequestCasesInner(
                    **data
                )
            )
        return result
    
    def _set_suite(self, case: dict, data: dict, project_code: str) -> dict:
        suite_id = self._get_suite_id(code = project_code, section_id = case['section_id'])
        if (suite_id):
            data['suite_id'] = suite_id
        return data
    
    def _import_custom_fields_for_case(self, case: dict, data: dict, project_code: str) -> dict:
        for field_name in case:
            if field_name.startswith('custom_') and field_name[len('custom_'):] in self.custom_fields_map and case[field_name]:
                name = field_name[len('custom_'):]
                custom_field = self.custom_fields_map[name]
                # Importing step
                
                if custom_field['type_id'] in (6, 12):
                    # Importing dropdown and multiselect values
                    if type(case[field_name]) == str:
                        data['custom_field'][str(custom_field['qase_id'])] = str(int(case[field_name])+1)
                    if type(case[field_name]) == list:
                        data['custom_field'][str(custom_field['qase_id'])] = ','.join(str(int(value)+1) for value in case[field_name])
                else:
                    data['custom_field'][str(custom_field['qase_id'])] = str(self._check_and_replace_attachments(case[field_name], project_code))
            if field_name[len('custom_'):] in self.step_fields and case[field_name]:
                steps = []
                i = 1
                for step in case[field_name]:
                    steps.append(
                        TestStepCreate(
                            action=self._check_and_replace_attachments(step['content'], project_code),
                            expected_result=self._check_and_replace_attachments(step['expected'], project_code),
                            position=i
                        )
                    )
                    i += 1
                data['steps'] = steps
        return data
    
    def _check_and_replace_attachments(self, string: str, project_code: str) -> str:
        if string:
            testrail_attachments = self._check_attachments(string)
            if (testrail_attachments):
                attachments_map = self._import_attachments(project_code, testrail_attachments)
                return self._replace_attachments(string=string, map=attachments_map)
        return string
    
    def _set_priority(self, case: dict, data: dict) -> dict:
        data['priority'] = self.priorities_map[case['priority_id']] if case['priority_id'] in self.priorities_map else 1
        return data
    
    def _set_type(self, case: dict, data: dict) -> dict:
        data['type'] = self.types_map[case['type_id']] if case['type_id'] in self.types_map else 1
        return data
    
    def _get_suite_id(self, code: str, section_id: Optional[int] = None) -> int:
        if (section_id and section_id in self.suites_map[code]):
            return self.suites_map[code][section_id]
        return None
    
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
        pass