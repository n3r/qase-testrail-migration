from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

from .attachments import Attachments

from typing import List, Optional

class Suites:
    def __init__(
            self, 
            qase_service: QaseService, 
            testrail_service: TestrailService, 
            logger: Logger, 
            mappings: Mappings, 
            config: Config
        ) -> None:
        self.qase = qase_service
        self.testrail = testrail_service
        self.config = config
        self.logger = logger
        self.mappings = mappings
        self.attachments = Attachments(self.qase, self.testrail, self.logger)

        self.suites_map = {}
        self.logger.divider()

    def import_suites(self, project):
        self.logger.log(f'[{project["code"]}][Suites] Importing suites from TestRail project {project["name"]}')
        if (project['suite_mode'] == 3):
            # Suites in testrail should be saved as suites in Qase
            suites = self.testrail.get_suites(project['testrail_id'])
            i = 0
            for suite in suites:
                self.logger.print_status('['+project['code']+'] Importing suites', i, len(suites), 1)
                 # Hack to import into root suites
                id = 1000000
                # Creating parent suite (suite -> suite)
                description = self.attachments.check_and_replace_attachments(suite['description'], project['code'])
                self._create_suite(project['code'], suite['name'], description=description, testrail_suite_id=id)
                # Creating sections as suites (section -> suite)
                self._create_suites(project['code'], project['testrail_id'], suite['id'], parent_id=id)
                id += 1
                   
        else:
            self._create_suites(project['code'], project['testrail_id'], 0)

        self.mappings.suites[project['code']] = self.suites_map
        
        return self.mappings

        
    def _create_suites(
            self,
            qase_code: str, 
            testrail_project_id: int, 
            testrail_suite_id: Optional[int], 
            parent_id: Optional[int] = None
        ):
        sections = self._get_sections(testrail_project_id, testrail_suite_id)
        self.logger.log(f"[{qase_code}][Suites] Found {len(sections)} sections")

        i = 1
        for section in sections:
            self.logger.log(f"[{qase_code}][Suites] Creating suite in Qase: {section['name']} ({section['id']})")
            self.logger.print_status('['+qase_code+'] Importing sections', i, len(sections), 1)

            if (section['parent_id'] == None and parent_id != None):
                section['parent_id'] = parent_id

            self._create_suite(
                qase_code, 
                title=section['name'], 
                description=section['description'], 
                parent_id=section['parent_id'],
                testrail_suite_id=section['id']
            )
            i += 1

    def _create_suite(
            self, 
            qase_code: str, 
            title: str, 
            description: Optional[str], 
            parent_id: Optional[int] = None, 
            testrail_suite_id: Optional[int] = None
        ):
        description = description if description else ""
        description = self.attachments.check_and_replace_attachments(description, qase_code)
        parent_id=self.suites_map[parent_id] if parent_id and self.suites_map[parent_id] else None

        self.suites_map[testrail_suite_id] = self.qase.create_suite(qase_code.upper(), title, description, parent_id)
    
    # Recursively get all sections
    def _get_sections(self, project_id: int, suite_id: int = 0, offset: int = 0, limit: int = 100) -> List:
        sections = self.testrail.get_sections(project_id, limit, offset, suite_id)
        if (len(sections) > 0 and len(sections) == limit):
            sections += self._get_sections(project_id, suite_id, offset + limit, limit)
        return sections