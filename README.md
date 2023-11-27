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
        "connection": "api",
        "api": {
            "host": "<TESTRAIL_HOST>",
            "user": "<TESTRAIL_USER_EMAIL>",
            "password": "<TESTRAIL_USER_PASSWORD>"
        }
    },
    "projects": {
        "import": [],
        "completed": true
    },
    "tests": {
        "fields": [],
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
            "0": "Not set",
            "1": "High",
            "2": "Medium",
            "3": "Low"
        },
        "refs": {
            "enable": true,
            "url": "http://localhost:8899/"
        }
    },
    "runs": {
        "createdafter": 1672524000,
        "statuses": {
            "1": "passed",
            "2": "blocked",
            "3": "skipped",
            "4": "skipped",
            "5": "failed"
        }
    },
    "defaultuser": 1,
    "threads": 3
}
```

Required fields to fill:

- `qase.token` - API token from Qase
- `testrail.connection` - Type of connection to TestRail. Can be `api` or `db`
- `testrail.api.host` - URL of your TestRail instance
- `testrail.api.user` - Email of user in TestRail. This user should have *administrator* access rights
- `testrail.api.password` - Password of user in TestRail
- `projects` - List of projects to migrate. You can specify only name of project.
- `tests.fields` - A list of custom fields from TestRail to import (use "label" as a field value). Keep empty to import all fields
- `tests.types` - ids and values for "type" field from Qase. In the example you can find default values created for a new workspace in Qase. If you have changed the values, you can pass an updated map here. 
- `tests.priorities` - ids and values for "priority" field from Qase. In the example you can find default values created for a new workspace in Qase. If you have changed the values, you can pass an updated map here.
- `defaultuser` - ID of user in Qase. This user will be used as author of all test cases if migrator unable to match user from TestRail to Qase
- `threads` - Number of threads to use for migration. Default: 5

### 3. Run

```bash
python start.py
```
