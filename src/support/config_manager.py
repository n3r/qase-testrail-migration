import os
import json


class ConfigManager:

    def __init__(self, config_file = './config.json', env_vars_prefix = 'QASE_'):
        self.config_file = config_file
        self.env_vars_prefix = env_vars_prefix
        self.config = {}

    def load_config(self):
        # Load from file
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as file:
                    self.config = json.load(file)
        except Exception as e:
            print(f"⚠️  Failed to load config from file {self.config_file}: {e}")

    def get(self, key):
        return self._get_config(key)

    def _get_keys(self, config, prefix=""):
        for key, value in config.items():
            if isinstance(value, dict):
                yield from self._get_keys(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    def _set_config(self, key, value):
        keys = key.split(".")
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value

    def _get_config(self, key):
        keys = key.split(".")
        config = self.config
        for key in keys[:-1]:
            config = config.get(key, {})
        return config.get(keys[-1], None)
    
    def build_config(self):
        config = {}

        print("Please enter the following configuration details. Press Enter for default value.")

        # Qase Configuration
        config['qase']['token'] = input("Enter Qase token: ")
        config['qase']['host'] = input("Enter Qase host (default: api.qase.io): ") or "api.qase.io"

        # Testrail Configuration
        connection_type = input("Enter Testrail connection (api/db): ")
        if connection_type.lower() == "api":
            config['testrail']['connection'] = "api"
            config['testrail']['api']['password'] = input("Enter Testrail API password: ")
            config['testrail']['api']['host'] = input("Enter Testrail API host: ")
            config['testrail']['api']['user'] = input("Enter Testrail API user: ")
        elif connection_type.lower() == "db":
            config['testrail']['connection'] = "db"
            config['testrail']['db']['DB_HOST'] = input("Enter Testrail DB host: ")
            config['testrail']['db']['DB_USER'] = input("Enter Testrail DB user: ")
            config['testrail']['db']['DB_PASSWORD'] = input("Enter Testrail DB password: ")
            config['testrail']['db']['DB_NAME'] = input("Enter Testrail DB name: ")
            config['testrail']['db']['DB_PORT'] = input("Enter Testrail DB port: ")

        # Projects Configuration
        projects_import = input("Enter project names for import, separated by commas (default: []): ") or ""
        config['projects']['import'] = [project.strip() for project in projects_import.split(',')] if projects_import else []
        completed_input = input("Are the projects completed? (True/False, default: True): ")
        config['projects']['completed'] = True if completed_input.lower() in ['true', ''] else False

        # Save the configuration to a JSON file
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)

        print("Configuration saved to config.json")
