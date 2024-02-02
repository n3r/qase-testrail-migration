from ..service import QaseService, TestrailService
from ..support import Logger, Mappings

class Configurations:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger, mappings: Mappings) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger
        self.mappings = mappings

        self.map = {}
        self.logger.divider()

    def import_configurations(self, project) -> Mappings:
        self.logger.log(f"[{project['code']}][Configurations] Importing configurations")
        configs = self.testrail.get_configurations(project['testrail_id'])
        if configs:
            self.logger.log(f"[{project['code']}][Configurations] Found {len(configs)} configurations")
            for group in configs:
                self.logger.log(f"[{project['code']}][Configurations] Importing configuration group {group['name']}")
                
                group_id = self.qase.create_configuration_group(
                    project['code'], 
                    title=group['name'],
                )
                if 'configs' in group and group_id:
                    for config in group['configs']:
                        self.mappings.stats.add_entity_count(project['code'], 'configurations', 'testrail')
                        id = self.qase.create_configuration(
                            project['code'], 
                            config['name'], 
                            group_id,
                        )
                        if id:
                            self.mappings.stats.add_entity_count(project['code'], 'configurations', 'qase')
                            self.map[config['id']] = id
        else:
            self.logger.log(f"[{project['code']}][Configurations] No configurations found")

        self.mappings.configurations[project['code']] = self.map
        
        return self.mappings