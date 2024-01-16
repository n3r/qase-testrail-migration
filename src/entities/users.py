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

        self.logger.log("Getting users from TestRail")
        self.testrail_users = []

        self.get_testrail_users()

        if (self.scim != None and self.config.get('users.create')):
            self.create_group()
            self.create_users()
            self.import_groups()

        self.build_map()

        return self.mappings
    
    def build_map(self):
        qase_users = self.qase.get_all_users()
        i = 0
        total = len(self.testrail_users)
        self.logger.print_status('Building users map', i, total)
        for testrail_user in self.testrail_users:
            i += 1
            flag = False
            for qase_user in qase_users:
                qase_user = qase_user.to_dict()
                if (testrail_user['email'].lower() == qase_user['email'].lower()):
                    self.mappings.users[testrail_user['id']] = qase_user['id']
                    flag = True
                    self.logger.log(f"User {testrail_user['email']} found in Qase as {qase_user['email']}")
                    break
            if (flag == False):
                # Not found, using default user
                self.mappings.users[testrail_user['id']] = self.config.get('users.default')
                self.logger.log(f"User {testrail_user['email']} not found in Qase, using default user.")
            self.logger.print_status('Building users map', i, total)
    
    def create_group(self):
        if (self.config.get('users.group_name') != None):
            group_name = self.config.get('users.group_name')
        else:
            group_name = 'TestRail Migration'
        self.logger.log(f"Creating group {group_name}")
        self.mappings.group_id = self.scim.create_group(group_name)

    def create_users(self):
        qase_users = self.scim.get_all_users()
        ids = []
        for testrail_user in self.testrail_users:
            flag = False
            for qase_user in qase_users:
                if (testrail_user['email'].lower() == qase_user['userName'].lower()):
                    # We have found a user. No need to create it.
                    ids.append(qase_user['id'])
                    self.map[testrail_user['id']] = qase_user['id']
                    flag = True
            if (flag == False):
                # Not found, using default user
                if (testrail_user['is_active'] == False and not self.config.get('users.inactive')):
                    # Skipping user
                    continue
                try:
                    user_id = self.create_user(testrail_user)
                    try:
                        self.logger.log(f"Adding user {testrail_user['email']} to group")
                        ids.append(user_id)
                        self.map[testrail_user['id']] = user_id
                    except Exception as e:
                        self.logger.log(f"Failed to add user {testrail_user['email']} to group")
                        self.logger.log(e)
                        continue
                except Exception as e:
                    self.logger.log(f"Failed to create user {testrail_user['email']}")
                    self.logger.log(e)
                    continue    

        if (len(ids) > 0):
            self.logger.log(f"Adding {len(ids)} users to group")
            for id in ids:
                self.scim.add_user_to_group(self.mappings.group_id, id)

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
    
    def import_groups(self):
        self.logger.log("Importing groups")
        groups = self.get_all_groups()
        for group in groups:
            self.logger.log(f"Importing group {group['name']}")
            group_id = self.scim.create_group(group['name'])
            for id in group['user_ids']:
                if (id in self.map):
                    self.logger.log(f"Adding user {id} to group {group['name']}")
                    self.scim.add_user_to_group(group_id, self.map[id])

    def get_all_groups(self):
        self.logger.log("Getting groups from TestRail")
        limit = 250
        offset = 0
        result = []
        while True:
            groups = self.testrail.get_groups(limit, offset)
            if ('groups' in groups and groups['groups'] != None):
                groups = groups['groups']

            result = result + groups

            if (len(groups) < limit):
                break

            offset += limit
        return result