# qase-testrail-migration

This script helps you to migrate your test cases from TestRail to Qase. It's written in Python 3.7 and uses [Qase API](https://qase.io/api/v1/) and [TestRail API](http://docs.gurock.com/testrail-api2/start).

## How to use
### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
Create a new config file from the example or use template:
```json
{
    "qase": {
        "token": "<QASE_API_TOKEN>",
        "host": "<QASE_API_HOST|Default:qase.io>"
    },
    "testrail": {
        "host": "<TESTRAIL_HOST>",
        "user": "<TESTRAIL_USER_EMAIL>",
        "password": "<TESTRAIL_USER_PASSWORD>"
    },
    "projects": [
        "Exact name of project in TestRail",
        {
            "name": "Exact name",
            "suites": ["Suite 1", "Suite 2", "Suite 3"]
        }
    ],
    "preserveids": true,
    "suitesasprojects": true,
    "fields": {
        
    },
    "types": {
        "1": "other",
        "2": "smoke",
        "3": "regression",
        "4": "security",
        "5": "usability",
        "6": "performance",
        "7": "acceptance",
        "8": "functional",
        "9": "compatibility",
        "10": "integration",
        "11": "exploratory"
    },
    "priorities": {
        "0": "not set",
        "1": "high",
        "2": "medium",
        "3": "low"
    },
    "defaultuser": 1,
    "threads": 5
}
```

Required fields to fill:
- `qase.token` - API token from Qase
- `testrail.host` - URL of your TestRail instance
- `testrail.user` - Email of user in TestRail. This user should have *administrator* access rights
- `testrail.password` - Password of user in TestRail
- `projects` - List of projects to migrate. You can specify only name of project or name of project and list of suites to migrate. If you specify only name of project, all suites will be migrated
- `preserveids` - If `true`, then all test cases will be migrated with the same IDs as in TestRail. If `false`, then all test cases will be migrated with new IDs
- `suitesasprojects` - If `true`, then all suites inside project will be migrated as separate projects. If `false`, then all suites will be migrated as suites in one project
- `fields` - Map of custom fields to import. You can specify custom fields in TestRail and Qase and map them to migrate data from TestRail to Qase. Example:
- `types` - ids and values for "type" field from Qase. In the example you can find default values created for a new workspace in Qase. If you have changed the values, you can pass an updated map here.
- `priorities` - ids and values for "priority" field from Qase. In the example you can find default values created for a new workspace in Qase. If you have changed the values, you can pass an updated map here.
```json

```
- `defaultuser` - ID of user in Qase. This user will be used as author of all test cases if migrator unable to match user from TestRail to Qase
- `threads` - Number of threads to use for migration. Default: 5

### 3. Run
```bash
python start.py
```