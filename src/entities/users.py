from ..service import QaseService, TestrailService
from ..support import Logger, Mappings

class Users:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings

        self.map = {}

    def import_users(self):
        # Function builds a map of TestRail users to Qase users and stores it in self.users_map
        self.logger.log("Building users map")
        
        testrail_users = self.testrail.get_all_users()
        qase_users = self.qase.get_all_users()

        i = 0
        total = len(testrail_users)
        self.logger.print_status('Importing users', i, total)

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
                self.mappings.users[testrail_user['id']] = self.mappings.default_user
                self.logger.log(f"User {testrail_user['email']} not found in Qase, using default user {self.mappings.default_user}")
            self.logger.print_status('Importing users', i, total)
        
        return self.mappings