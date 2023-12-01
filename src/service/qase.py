from ..support import ConfigManager, Logger

import certifi
import json

from qaseio.api_client import ApiClient
from qaseio.configuration import Configuration
from qaseio.api.authors_api import AuthorsApi
from qaseio.api.custom_fields_api import CustomFieldsApi
from qaseio.api.projects_api import ProjectsApi
from qaseio.api.suites_api import SuitesApi
from qaseio.api.cases_api import CasesApi
from qaseio.api.runs_api import RunsApi
from qaseio.api.results_api import ResultsApi
from qaseio.api.attachments_api import AttachmentsApi

from qaseio.models import SuiteCreate, CustomFieldCreate, CustomFieldCreateValueInner, ProjectCreate, BulkRequest, RunCreate, ResultCreateBulk

from datetime import datetime

from qaseio.exceptions import ApiException
from ..exceptions import ImportException

class QaseService:
    def __init__(self, config: ConfigManager, logger: Logger):
        self.config = config
        self.logger = logger

        configuration = Configuration()
        configuration.api_key['TokenAuth'] = config.get('qase_token')
        configuration.host = f'https://api.{config.get("qase_host")}/v1'
        configuration.ssl_ca_cert = certifi.where()

        self.client = ApiClient(configuration)

    def _get_users(self, limit = 100, offset = 0):
        try:
            api_instance = AuthorsApi(self.client)
            # Get all authors.
            api_response = api_instance.get_authors(limit=limit, offset=offset, type="user")
            if (api_response.status and api_response.result.entities):
                return api_response.result.entities
        except ApiException as e:
            self.lo("Exception when calling AuthorsApi->get_authors: %s\n" % e)
    
    def get_all_users(self, batch_size = 100):
        flag = True
        limit = batch_size
        offset = 0
        users = []
        while flag:
            result = self._get_users(limit, offset)
            users += result
            offset += limit
            if (len(result) < limit):
                flag = False
        return users
    
    def get_case_custom_fields(self):
        try:
            api_instance = CustomFieldsApi(self.client)
            # Get all custom fields.
            api_response = api_instance.get_custom_fields(entity='case', limit=100)
            if (api_response.status and api_response.result.entities):
                return api_response.result.entities
        except ApiException as e:
            self.logger.log("Exception when calling CustomFieldsApi->get_custom_fields: %s\n" % e)

    def create_custom_field(self, data, field) -> int:
        try:
            api_instance = CustomFieldsApi(self.client)
            # Create a custom field.
            api_response = api_instance.create_custom_field(custom_field_create=CustomFieldCreate(**data))
            if (api_response.status == False):
                self.logger.log('Error creating custom field: ' + field['name'])
            else:
                self.logger.log('Custom field created: ' + field['name'])
                return api_response.result.id
        except ApiException as e:
            self.logger.log('Exception when calling CustomFieldsApi->create_custom_field: %s\n' % e)
        return 0
    
    def prepare_custom_field_data(self, field, mappings) -> dict:
        data = {
            'title': field['label'],
            'entity': 0, # 0 - case, 1 - run, 2 - defect,
            'type': mappings.custom_fields_type[field['type_id']],
            'value': [],
            'is_filterable': True,
            'is_visible': True,
            'is_required': False,
            'is_enabled_for_all_projects': True,
        }
        if (self.__get_default_value(field)):
            data['default_value'] = self.__get_default_value(field)
        if (field['type_id'] == 12 or field['type_id'] == 6):
            values = self.__split_values(field['configs'][0]['options']['items'])
            field['qase_values'] = {}
            for key, value in values.items():
                data['value'].append(
                    CustomFieldCreateValueInner(
                        id=int(key)+1, # hack as in testrail ids can start from 0
                        title=value,
                    ),
                )
                field['qase_values'][int(key)+1] = value
        return data
    
    def __get_default_value(self, field):
        if 'configs' in field:
            if len(field['configs']) > 0:
                if 'options' in field['configs'][0]:
                    if 'default_value' in field['configs'][0]['options']:
                        return field['configs'][0]['options']['default_value']
        return None

    def __split_values(self, string: str, delimiter: str = ',') -> dict:
        items = string.split('\n')  # split items into a list
        result = {}
        for item in items:
            key, value = item.split(delimiter)  # split each item into a key and a value
            result[key] = value
        return result
    
    def create_project(self, title, description, code):
        api_instance = ProjectsApi(self.client)

        self.logger.log(f'Creating project: {title} [{code}]')
        try:
            api_response = api_instance.create_project(
                project_create = ProjectCreate(
                    title = title,
                    code = code,
                    description = description if description else "",
                )
            )
            self.logger.log(f'Project was created: {api_response.result.code}')
            return True
        except ApiException as e:
            error = json.loads(e.body)
            if (error['status'] == False and error['errorFields'][0]['error'] == 'Project with the same code already exists.'):
                self.logger.log(f'Project with the same code already exists: {code}. Using existing project.')
                return True
            
            self.logger.log('Exception when calling ProjectsApi->create_project: %s\n' % e)
            return False
            raise ImportException(e)
        
    def create_suite(self, code: str, title: str, description: str, parent_id = None) -> int:
        api_instance = SuitesApi(self.client)
        api_response = api_instance.create_suite(
            code = code,
            suite_create=SuiteCreate(
                title = title,
                description = description if description else "",
                preconditions="",
                # parent_id = ID in Qase
                parent_id=parent_id
            )
        )
        return api_response.result.id
    
    def create_cases(self, code: str, cases: list) -> bool:
        api_instance = CasesApi(self.client)

        try:
            # Create a new test cases.
            api_response = api_instance.bulk(code, BulkRequest(cases))
            return api_response.status
        except ApiException as e:
            self.logger.log("Exception when calling CasesApi->bulk: %s\n" % e)
        return False
    
    def create_run(self, run: list, project_code: str, cases: list = []):
        api_instance = RunsApi(self.client)

        data = {
            'title': run['name'],
            'start_time': datetime.fromtimestamp(run['created_on']).strftime('%Y-%m-%d %H:%M:%S')
        }

        if (run['is_completed']):
            data['end_time'] = datetime.fromtimestamp(run['completed_on']).strftime('%Y-%m-%d %H:%M:%S')

        if (len(cases) > 0):
            data['cases'] = cases

        try:
            response = api_instance.create_run(code=project_code, run_create=RunCreate(**data))
            self.logger.log(f'Run was created: {response.result.id}')
            return response.result.id
        except Exception as e:
            self.logger.log(f'Exception when calling RunsApi->create_run: {e}')

    def send_bulk_results(self, tr_run, results, qase_run_id, qase_code, status_map, mappings, cases_map):
        res = []

        if (results):
            for result in results:
                if result['status_id'] != 3:
                    elapsed = 0
                    if ('elapsed' in result and result['elapsed']):
                        if type(result['elapsed']) == str:
                            elapsed = self.convert_to_seconds(result['elapsed'])
                        else:
                            elapsed = int(result['elapsed'])
                            
                    if 'tested_on' in result and result['tested_on']:
                        start_time = result['tested_on'] - elapsed
                    else:
                        start_time = tr_run['created_on'] - elapsed

                    data = {
                        "case_id": cases_map[result['test_id']],
                        "status": status_map.get(str(result["status_id"]), "skipped"),
                        "time_ms": elapsed*1000, # converting to miliseconds
                        "comment": str(result['comment'])
                    }

                    if (start_time):
                        data['start_time'] = start_time

                    #if (result['defects']):
                        #self.defects.append({"case_id": result["case_id"],"defects": result['defects'],"run_id": qase_run_id})

                    if result['created_by']:
                        data['author_id'] = mappings.get_user_id(result['created_by'])

                    res.append(data)

            if (len(res) > 0):
                api_results = ResultsApi(self.client)
                self.logger.log(f'Sending {len(res)} results to Qase')
                api_results.create_result_bulk(
                        code=qase_code,
                        id=int(qase_run_id),
                        result_create_bulk=ResultCreateBulk(
                            results=res
                        )
                    )
    def convert_to_seconds(self, time_str: str) -> int:
        total_seconds = 0
        components = time_str.split()

        for component in components:
            if component.endswith('d'):
                total_seconds += int(component[:-1]) * 86400  # 60 seconds * 60 minutes * 24 hours
            elif component.endswith('h'):
                total_seconds += int(component[:-1]) * 3600  # 60 seconds * 60 minutes
            elif component.endswith('m'):
                total_seconds += int(component[:-1]) * 60
            elif component.endswith('s'):
                total_seconds += int(component[:-1])

        return total_seconds
    
    def upload_attachment(self, code, attachment_data):
        api_attachments = AttachmentsApi(self.client)
        try:
            response = api_attachments.upload_attachment(
                    code, file=[attachment_data],
                ).result
            if response:
                return response[0]
        except Exception as e:
            self.logger.log(f'Exception when calling AttachmentsApi->upload_attachment: {e}')