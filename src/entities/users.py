from ..service import QaseService, QaseScimService, TestrailService
from ..support import Logger, Mappings, ConfigManager as Config

class Users:
    def __init__(
        self, 
        qase_service: QaseService, 
        testrail_service: TestrailService, 
        logger: Logger, 
        mappings: Mappings, 
        config: Config, 
        scim_service: QaseScimService = None
    ) -> Mappings:
        self.qase = qase_service
        self.scim = scim_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings
        self.config = config

        self.map = {}

    def import_users(self):
        # Function builds a map of TestRail users to Qase users and stores it in self.users_map
        self.logger.log("Building users map")
        self.logger.log("Getting users from Qase")
        self.qase_users = self.qase.get_all_users()

        self.logger.log("Getting users from TestRail")
        self.testrail_users = []

        self.get_testrail_users()

        if (self.scim != None and self.config.get('users.create')):
            self.create_group()
            self.create_users()
            # Refreshing users, because there is a difference between Member ID and Author ID
            self.qase_users = self.qase.get_all_users()

        self.build_map()

        return self.mappings
    
    def build_map(self):
        i = 0
        total = len(self.testrail_users)
        self.logger.print_status('Building users map', i, total)
        for testrail_user in self.testrail_users:
            i += 1
            flag = False
            for qase_user in self.qase_users:
                qase_user = qase_user.to_dict()
                if (testrail_user['email'] == qase_user['email'] and testrail_user['is_active'] == True):
                    self.mappings.users[testrail_user['id']] = qase_user['id']
                    flag = True
                    self.logger.log(f"User {testrail_user['email']} found in Qase as {qase_user['email']}")
                    break
            if (flag == False):
                # Not found, using default user
                self.mappings.users[testrail_user['id']] = self.config.get('users.default')
                self.logger.log(f"User {testrail_user['email']} not found in Qase, using default user.")
            self.logger.print_status('Importing users', i, total)
    
    def create_group(self):
        if (self.config.get('users.group_name') != None):
            group_name = self.config.get('users.group_name')
        else:
            group_name = 'TestRail Migration'
        self.logger.log(f"Creating group {group_name}")
        self.mappings.group_id = self.scim.create_group(group_name)

    def create_users(self):
        for testrail_user in self.testrail_users:
            flag = False
            for qase_user in self.qase_users:
                qase_user = qase_user.to_dict()
                if (testrail_user['email'] == qase_user['email']):
                    # We have found a user. No need to create it.
                    flag = True
                    break
            if (flag == False):
                # Not found, using default user
                if (testrail_user['is_active'] == False and not self.config.get('users.inactive')):
                    # Skipping user
                    continue
                try:
                    user_id = self.create_user(testrail_user)
                    try:
                        self.logger.log(f"Adding user {testrail_user['email']} to group")
                        self.scim.add_user_to_group(self.mappings.group_id, user_id)
                    except Exception as e:
                        self.logger.log(f"Failed to add user {testrail_user['email']} to group")
                        self.logger.log(e)
                        continue
                except Exception as e:
                    self.logger.log(f"Failed to create user {testrail_user['email']}")
                    self.logger.log(e)
                    continue    

    def get_testrail_users(self):
        limit = 250
        offset = 0
        while True:
            users = self.testrail.get_users(limit, offset)
            if ('users' in users and users['users'] != None):
                users = users['users']

            self.testrail_users = self.testrail_users + users

            if (len(users) < limit):
                break

            offset += limit
    
    def create_user(self, testrail_user):
        # Function creates a new user in Qase
        self.logger.log(f"Creating user {testrail_user['email']} in Qase")
        parts = testrail_user['name'].split()
        if (len(parts) == 2):
            first_name = parts[0]
            last_name = parts[1]
        else:
            first_name = testrail_user['name']
            last_name = ''

        user_id = self.scim.create_user(
            testrail_user['email'], 
            first_name, 
            last_name, 
            testrail_user['role'], 
            testrail_user['is_active']
        )
        self.logger.log(f"User {testrail_user['email']} created in Qase with id {user_id}")
        return user_id