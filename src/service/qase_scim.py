from ..support import ConfigManager, Logger

import certifi
import json

from ..api import QaseScimClient

from qaseio.exceptions import ApiException
from ..exceptions import ImportException

class QaseScimService:
    def __init__(self, config: ConfigManager, logger: Logger):
        self.config = config
        self.logger = logger

        self.client = QaseScimClient(self.config.get('qase.host'), self.config.get('qase.scim_token'))

    def create_user(self, email, first_name, last_name, roleTitle, is_active=True):
        try:
            payload = {
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
                'userName': email,
                'name': {
                    'familyName': last_name,
                    'givenName': first_name
                },
                'active': is_active,
                'roleTitle': roleTitle
            }
            response = self.client.create_user(payload)

            return response['id']
        except ApiException as e:
            raise ImportException(f'Failed to create user: {e}')
        
    def create_group(self, group_name):
        try:
            payload = {
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
                'displayName': group_name
            }
            response = self.client.create_group(payload)
            return response['id']
        except ApiException as e:
            raise ImportException(f'Failed to create group: {e}')
        
    def add_user_to_group(self, group_id, user_id):
        try:
            self.client.add_user_to_group(group_id, user_id)
        except ApiException as e:
            raise ImportException(f'Failed to add user to group: {e}')
        return
        
    