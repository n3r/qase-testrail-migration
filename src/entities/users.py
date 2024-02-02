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
        self.map = {} # This is a map of TestRail user ids to Qase user ids. Used for mapping users to groups
        self.active_ids = [] # This is a list of Qase active users that should be added to groups
        self.testrail_users = []
        self.logger.divider()

    def import_users(self):
        self.get_testrail_users()

        if (self.scim != None):
            self.create_users()
            if (self.config.get('groups.create')):
                self.create_root_group()
                self.import_groups()

        self.build_map()


        return self.mappings
    
    def build_map(self):
        self.logger.log("[Users] Building users map")
        qase_users = self.qase.get_all_users()
        self.mappings.stats.add_user('qase', len(qase_users))
        self.mappings.stats.add_user('testrail', len(self.testrail_users))
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
                    self.logger.log(f"[Users] User {testrail_user['email']} found in Qase as {qase_user['email']}")
                    break
            if (flag == False):
                # Not found, using default user
                self.mappings.users[testrail_user['id']] = self.config.get('users.default')
                self.logger.log(f"[Users] User {testrail_user['email']} not found in Qase, using default user.")
            self.logger.print_status('Building users map', i, total)
    
    def create_root_group(self):
        if (self.config.get('groups.name') != None):
            group_name = self.config.get('groups.name')
        else:
            group_name = 'TestRail Migration'
        self.logger.log(f"[Users] Creating group {group_name}")
        self.mappings.group_id = self.scim.create_group(group_name)
        for id in self.active_ids:
            self.logger.log(f"[Users] Adding user {id} to group {group_name}")
            self.scim.add_user_to_group(self.mappings.group_id, id)

    def create_users(self):
        self.logger.log("[Users] Loading users from Qase using SCIM")
        qase_users = self.scim.get_all_users()
        for testrail_user in self.testrail_users:
            flag = False
            for qase_user in qase_users:
                if (testrail_user['email'].lower() == qase_user['userName'].lower()):
                    self.logger.log("[Users] User found in Qase using SCIM, skipping creation.")
                    self.map[testrail_user['id']] = qase_user['id']
                    if (testrail_user['is_active']):
                        self.active_ids.append(qase_user['id'])
                    flag = True
            if (flag == False):
                # Not found, using default user
                if (testrail_user['is_active'] == False and not self.config.get('users.inactive')):
                    self.logger.log(f"[Users] User {testrail_user['email']} is not active, skipping creation.")
                    continue
                try:
                    if self.config.get('users.create'):
                        user_id = self.create_user(testrail_user)
                        self.map[testrail_user['id']] = user_id
                        if (testrail_user['is_active']):
                            self.active_ids.append(user_id)
                except Exception as e:
                    self.logger.log(f"[Users] Failed to create user {testrail_user['email']}", 'error')
                    self.logger.log(e)
                    continue

    def get_testrail_users(self):
        self.logger.log("[Users] Getting users from TestRail")
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
        self.logger.log(f"[Users] Found {len(self.testrail_users)} users in TestRail")
    
    def create_user(self, testrail_user):
        # Function creates a new user in Qase
        self.logger.log(f"[Users] Creating user {testrail_user['email']} in Qase")
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
        self.logger.log(f"[Users] User {testrail_user['email']} created in Qase with id {user_id}")
        return user_id
    
    def import_groups(self):
        self.logger.log("[Users] Importing groups from TestRail")
        groups = self.get_all_groups()
        for group in groups:
            self.logger.log(f"[Users] Importing group {group['name']}")
            group_id = self.scim.create_group(group['name'])
            for id in group['user_ids']:
                if (id in self.map):
                    if (self.map[id] in self.active_ids):
                        self.logger.log(f"[Users] Adding user {id} to group {group['name']}")
                        self.scim.add_user_to_group(group_id, self.map[id])
                    else:
                        self.logger.log(f"[Users] User {id} is not active, skipping adding to group {group['name']}")

    def get_all_groups(self):
        self.logger.log("[Users] Loading all groups from TestRail")
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
        self.logger.log(f"[Users] Found {len(result)} groups in TestRail")
        return result