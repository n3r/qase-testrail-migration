class Mappings:
    def __init__(self, default_user: int = 1):
        self.suites = {}
        self.users = {}
        self.types = {}
        self.priorities = {}
        self.projects = []
        # A map of TestRail custom fields types to Qase custom fields types
        self.custom_fields_type = {
            1: 1,
            2: 0,
            3: 2,
            4: 7,
            5: 4,
            6: 3,
            7: 8,
            8: 9,
            12: 6,
        }
        self.qase_fields_type = {
            "number": 0,
            "string": 1,
            "text": 2,
            "selectbox": 3,
            "checkbox": 4,
            "radio": 5,
            "multiselect": 6,
            "url": 7,
            "user": 8,
            "datetime": 9,
        }

        self.custom_fields = {}

        # Step fields. Used to determine if a field is a step field or not during import
        self.step_fields = []

        self.refs_id = None

        self.default_user = default_user

    def get_user_id(self, id: int) -> int:
        if (id in self.users):
            return self.users[id]
        return self.default_user  