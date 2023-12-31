from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

from qaseio.models import BulkRequestCasesInner, TestStepCreate
from .attachments import Attachments

from typing import List, Optional, Union

from urllib.parse import quote
from datetime import datetime

class Cases:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings, config: Config) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.config = config
        self.logger = logger
        self.mappings = mappings
        self.attachments = Attachments(self.qase, self.testrail, self.logger)
        self.total = 0

    def import_cases(self, project: dict):
        self.project = project

        if self.project['suite_mode'] == 3:
            suites = self.testrail.get_suites(self.project['testrail_id'])
            for suite in suites:
                self.import_cases_for_suite(suite['id'])
        else:
            self.import_cases_for_suite(None)  # Assuming None is a valid suite_id when suite_mode is not 3

    def import_cases_for_suite(self, suite_id):
        offset = 0
        limit = 250
        while True:
            count = self.process_cases(suite_id, offset, limit)
            if count < limit:
                break
            offset += limit

    def process_cases(self, suite_id: int, offset: int, limit: int):
        try:
            if suite_id == None:
                suite_id = 0
            cases = self.testrail.get_cases(self.project['testrail_id'], suite_id, limit, offset)
            if cases:
                self.logger.print_status('['+self.project['code']+'] Importing test cases', self.total, self.total+cases['size'], 1)
                self.logger.log(f'Importing cases from {offset} to {offset + limit} for suite {suite_id}')
                self.qase.create_cases(self.project['code'], self._prepare_cases(cases))
                self.total = self.total + cases['size']
                self.logger.print_status('['+self.project['code']+'] Importing test cases', self.total, self.total, 1)
            return cases['size']
        except Exception as e:
            self.logger.log(f"Error processing cases for suite {suite_id}: {e}")
            return 0
    
    def _prepare_cases(self, cases: List) -> List:
        result = []
        for case in cases['cases']:
            data = {
                'id': int(case['id']),
                'title': case['title'],
                'created_at': str(datetime.fromtimestamp(case['created_on'])),
                'updated_at': str(datetime.fromtimestamp(case['updated_on'])),
                'author_id': self.mappings.get_user_id(case['created_by']),
                'steps': [],
                'is_flaky': 0,
                'custom_field': {},
            }

            # import custom fields
            data = self._import_custom_fields_for_case(case=case, data=data)

            data = self._set_priority(case=case, data=data)
            data = self._set_type(case=case, data=data)
            data = self._set_suite(case=case, data=data)
            data = self._set_refs(case=case, data=data)

            result.append(
                BulkRequestCasesInner(
                    **data
                )
            )
        return result
    
    # Done
    def _set_refs(self, case:dict, data: dict):
        if self.mappings.refs_id and case['refs'] and self.config.get('tests.refs.enable'):
            string = str(case['refs'])
            url = str(self.config.get('refs.url'))
            if string.startswith('http'):
                data['custom_field'][str(self.mappings.refs_id)] = quote(string, safe="/:")
            elif url != '':
                if not url.endswith('/'):
                    string = string + '/'
                string = url + string
                data['custom_field'][str(self.mappings.refs_id)] = quote(string, safe="/:")
        return data
    
    # Done
    def _import_custom_fields_for_case(self, case: dict, data: dict) -> dict:
        for field_name in case:
            if field_name.startswith('custom_') and field_name[len('custom_'):] in self.mappings.custom_fields and case[field_name]:
                name = field_name[len('custom_'):]
                custom_field = self.mappings.custom_fields[name]
                # Importing step
                
                if custom_field['type_id'] in (6, 12):
                    # Importing dropdown and multiselect values
                    value = self._validate_custom_field_values(custom_field, case[field_name])
                    if value:
                        if type(value) == str or type(value) == int:
                            data['custom_field'][str(custom_field['qase_id'])] = str(int(value)+1)
                        if type(value) == list:
                            data['custom_field'][str(custom_field['qase_id'])] = ','.join(str(int(v)+1) for v in value)
                else:
                    data['custom_field'][str(custom_field['qase_id'])] = str(self.attachments.check_and_replace_attachments(case[field_name], self.project['code']))
            if field_name[len('custom_'):] in self.mappings.step_fields and case[field_name]:
                steps = []
                i = 1
                for step in case[field_name]:
                    action = self.attachments.check_and_replace_attachments(step['content'], self.project['code'])
                    if (action and action != ''):
                        # Type casting for API validation
                        if step['expected'] == None:
                            step['expected'] = ''
                        steps.append(
                            TestStepCreate(
                                action=action,
                                expected_result=self.attachments.check_and_replace_attachments(step['expected'], self.project['code']),
                                position=i
                            )
                        )
                        i += 1
                    else:
                        self.logger.log(f'Case {case["title"]} has invalid step {step}')
                data['steps'] = steps
        return data
    
    # Done. Method validates if custom field value exists (skip)
    def _validate_custom_field_values(self, custom_field: dict, value: Union[str, List]) -> Optional[Union[str, list]]: 
        values = self.__split_values(custom_field['configs'][0]['options']['items'])
        if type(value) == str or type(value) == int:
            if str(value) not in values.keys():
                self.logger.log(f'Custom field {custom_field["name"]} has invalid value {value}')
                return None
        elif type(value) == list:
            filtered_values = []
            for item in value:
                if str(item) in values.keys():
                    filtered_values.append(item)
                else:
                    self.logger.log(f'Custom field {custom_field["name"]} has invalid value {value}')
            if len(filtered_values) == 0:
                return None
            else:
                return filtered_values
        return value
    
    def __split_values(self, string: str, delimiter: str = ',') -> dict:
        items = string.split('\n')  # split items into a list
        result = {}
        for item in items:
            key, value = item.split(delimiter)  # split each item into a key and a value
            result[key] = value
        return result
    
    # Done
    def _set_priority(self, case: dict, data: dict) -> dict:
        data['priority'] = self.mappings.priorities[case['priority_id']] if case['priority_id'] in self.mappings.priorities else 1
        return data
    
    # Done
    def _set_type(self, case: dict, data: dict) -> dict:
        data['type'] = self.mappings.types[case['type_id']] if case['type_id'] in self.mappings.types else 1
        return data
    
    # Done
    def _set_suite(self, case: dict, data: dict) -> dict:
        suite_id = self._get_suite_id(section_id = case['section_id'])
        if (suite_id):
            data['suite_id'] = suite_id
        return data
    
    # Done
    def _get_suite_id(self, section_id: Optional[int] = None) -> int:
        if (section_id and section_id in self.mappings.suites[self.project['code']]):
            return self.mappings.suites[self.project['code']][section_id]
        return None