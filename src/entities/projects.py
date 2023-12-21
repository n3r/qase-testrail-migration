from ..service import QaseService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config
from typing import Optional, Union

import re

class Projects:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings, config: Config) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.config = config
        self.logger = logger
        self.mappings = mappings
        self.existing_codes = set()

    def import_projects(self):
        self.logger.log('Importing projects from TestRail')

        testrail_projects = self.testrail.get_projects()
        if testrail_projects:
            total = len(testrail_projects['projects'])
            self.logger.log(f'Found {str(total)} projects')
            i = 0
            self.logger.print_status('Importing projects', i, total)

            for project in testrail_projects['projects']:
                self.logger.log(f'Importing project: {project["name"]}')
                if (self._check_import(project['name'], project['is_completed'])):
                    data = {
                        "testrail_id": project['id'],
                        "name": project['name'],
                        "suite_mode": project['suite_mode']
                    }
                    data['code'] = self._create_project(project['name'], project['announcement'])
                    self.mappings.projects.append(data)
                else:
                    self.logger.log(f'Skipping project: {project["name"]}')
                i += 1
                self.logger.print_status('Importing projects', i, total)
        else:
            self.logger.log('No projects found in TestRail')
        return self.mappings
    
    # Function checks if the project should be imported
    def _check_import(self, title: str, is_completed: bool) -> bool:

        # If the project is completed and import_completed is False, skip the project
        if is_completed and not self.config.get('projects.completed'):
            return False

        # If project name is in the list of projects to import, return True
        projects = self.config.get('projects.import')
        if not projects:
            return True
        for project in projects:
            if isinstance(project, str) and project == title:
                return True
            elif isinstance(project, dict) and project['name'] == title:
                return True
        return False
    
    # Method generates short code that will be used as a project code in from a string
    def _old_short_code(self, s: str) -> str:
        s = re.sub('[!@#$%^&*().,1234567890]', '', s)  # remove special characters
        words = s.split()

        if len(words) > 1:  # if the string contains multiple words
            code = ''.join(word[0] for word in words).upper()
        else:
            code = s.upper()

        return code[:10]  # truncate to 10 characters
    
    def _short_code(self, s: str) -> str:
        s = s.replace("-", " ")  # Replace dashes with spaces

        # Remove all characters except letters
        s = re.sub('[^a-zA-Z ]', '', s)

        words = s.split()
        # Ensure the first character is a letter and make it uppercase
        if len(words) > 1:  # if the string contains multiple words
            code = ''.join(word[0] for word in words).upper()
        else:
            code = s.upper()

        # Truncate to 10 characters
        code = code[:10]

        # Handle duplicates by adding a letter postfix
        original_code = code
        postfix = ''
        while code in self.existing_codes or len(code) < 2:
            postfix = self._next_postfix(postfix)
            code = (original_code[:10-len(postfix)] + postfix).upper()

        self.existing_codes.add(code)
        return code

    def _next_postfix(self, postfix):
        if not postfix:
            return 'A'  # Start with 'A' if no postfix
        elif postfix[-1] == 'Z':  # If last char is 'Z', increment previous char
            return self._next_postfix(postfix[:-1]) + 'A'
        else:  # Increment the last character
            return postfix[:-1] + chr(ord(postfix[-1]) + 1)
    
    # Method creates project in Qase
    def _create_project(self, title: str, description: Optional[str]) -> Union[str, None]:
        code = self._short_code(title)
        result = self.qase.create_project(title, description, code, self.mappings.group_id)
        if result:
            return code
        return None