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
        
        testrail_users = self.testrail.get_all_users()
        qase_users = self.qase.get_all_users()

        i = 0
        total = len(testrail_users)
        self.logger.print_status('Importing users', i, total)

        if (self.scim and self.config.get('users.create')):
            # Creating Group in Qase
            if (self.config.get('users.group_name') != None):
                group_name = self.config.get('users.group_name')
            else:
                group_name = 'TestRail Migration'

            group_id = self.scim.create_group(group_name)

            self.mappings.group_id = group_id
            # We need to create users in order to match Author ID with TestRail User ID
            for testrail_user in testrail_users:
                flag = False
                for qase_user in qase_users:
                    if (testrail_user['email'] == qase_user['email'] and testrail_user['is_active'] == True):
                        flag = True
                        break
                if (flag == False):
                    self.logger.log(f"User {testrail_user['email']} not found in Qase, creating a new one.")
                    try:
                        user_id = self.create_user(testrail_user)
                        try:
                            self.logger.log(f"Adding user {testrail_user['email']} to group {group_name}")
                            self.scim.add_user_to_group(group_id, user_id)
                        except Exception as e:
                            self.logger.log(f"Failed to add user {testrail_user['email']} to group {group_name}")
                            self.logger.log(e)
                            continue
                    except Exception as e:
                        self.logger.log(f"Failed to create user {testrail_user['email']}")
                        self.logger.log(e)
                        continue

            qase_users = self.qase.get_all_users()

        for testrail_user in testrail_users:
            i += 1
            flag = False
            for qase_user in qase_users:
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
        
        return self.mappings
    
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

        user_id = self.scim.create_user(testrail_user['email'], first_name, last_name, testrail_user['role'])
        self.logger.log(f"User {testrail_user['email']} created in Qase with id {user_id}")
        return user_id