import json

from service.qase import QaseService
from service.testrail import TestrailService
from support.logger import Logger
from support.mappings import Mappings
from support.config_manager import ConfigManager as Config

class Fields:
    def __init__(
            self, 
        qase_service: QaseService, 
        testrail_service: TestrailService, 
        logger: Logger, 
        mappings: Mappings, 
        config: Config
    ):
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings
        self.config = config

        self.refs_id = None

        self.map = {}

    def import_fields(self):
        self.logger.log('Importing system fields from TestRail')
        
        self._create_types_map()

        self._create_priorities_map()

        qase_custom_fields = self.qase.get_case_custom_fields()
        testrail_custom_fields = self.testrail.get_case_fields()

        total = len(testrail_custom_fields)
        
        self.logger.log(f'Found {str(total)} custom fields')

        fields_to_import = self._get_fields_to_import(testrail_custom_fields)

        i = 0
        self.logger.print_status('Importing custom fields', i, total)
        for field in testrail_custom_fields:
            i += 1
            if field['name'] in fields_to_import and field['is_active']:
                if (field['type_id'] in self.mappings.custom_fields_type):
                    self._create_custom_field(field, qase_custom_fields)
            else:
                self.logger.log(f'Skipping custom field: {field["name"]}')

            if (field['type_id'] == 10):
                self.mappings.step_fields.append(field['name'])
            self.logger.print_status('Importing custom fields', i, total)

        self._create_refs_field(qase_custom_fields)
        return self.mappings

    def _get_fields_to_import(self, custom_fields):
        self.logger.log('Building a map for fields to import')
        fields_to_import = self.config.get('tests_fields')
        if fields_to_import is not None and len(fields_to_import) == 0 and not fields_to_import:
            for field in custom_fields:
                if field['system_name'].startswith('custom_'):
                    fields_to_import.append(field['name'])
        return fields_to_import

    def _create_custom_field(self, field, qase_fields):
        # Skip if field already exists
        if (qase_fields and len(qase_fields) > 0):
            for qase_field in qase_fields:
                if qase_field.title == field['label'] and self.mappings.custom_fields_type[field['type_id']] == self.mappings.qase_fields_type[qase_field.type.lower()]:
                    self.logger.log('Custom field already exists: ' + field['label'])
                    if (qase_field.type.lower() in ("selectbox", "multiselect", "radio")):
                        field['qase_values'] = {}
                        values = json.loads(qase_field.value)
                        for value in values:
                            field['qase_values'][value['id']] = value['title']
                    field['qase_id'] = qase_field.id
                    self.mappings.custom_fields[field['name']] = field
                    return

        data = self.qase.prepare_custom_field_data(field, self.mappings)
        self.qase.create_custom_field(data, field)
        
    def _create_refs_field(self, qase_custom_fields):
        if self.config.get('tests_refs_enable'):
            field = None
            if (qase_custom_fields and len(qase_custom_fields) > 0):
                for qase_field in qase_custom_fields:
                    if qase_field.title == 'Refs':
                        self.logger.log('Refs field found')
                        self.mappings.refs_id = qase_field.id
            
            if not self.mappings.refs_id and field is not None:
                self.logger.log('Refs field not found. Creating a new one')
                data = {
                    'title': 'Refs',
                    'entity': 0, # 0 - case, 1 - run, 2 - defect,
                    'type': 7,
                    'is_filterable': True,
                    'is_visible': True,
                    'is_required': False,
                    'is_enabled_for_all_projects': True,
                }
                self.mappings.refs_id = self.qase.create_custom_field(data, {})

    def _create_types_map(self):
        self.logger.log('Creating types map')

        tr_types = self.testrail.get_case_types()
        qase_types = self.config.get('tests_types')

        for tr_type in tr_types:
            self.mappings.types[tr_type['id']] = 1
            for qase_type_id in qase_types:
                if tr_type['name'].lower() == qase_types[qase_type_id].lower():
                    self.mappings.types[tr_type['id']] = int(qase_type_id)
        
        self.logger.log('Types map was created')

    def _create_priorities_map(self):
        self.logger.log('Creating priorities map')

        tr_priorities = self.testrail.get_priorities()
        qase_priorities = self.config.get('tests_priorities')
        for tr_priority in tr_priorities:
            self.mappings.priorities[tr_priority['id']] = 1
            for qase_priority_id in qase_priorities:
                if tr_priority['name'].lower() == qase_priorities[qase_priority_id].lower():
                    self.mappings.priorities[tr_priority['id']] = int(qase_priority_id)
        
        self.logger.log('Priorities map was created')
