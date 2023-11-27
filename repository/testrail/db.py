import mysql.connector

class TestrailDbRepository:
    def __init__(self, host, database, user, password, logger):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.logger = logger

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except mysql.connector.Error as e:
            print("Error connecting to MySQL database:", e)

    def disconnect(self):
        if self.connection:
            self.connection.close()
            print("Disconnected from MySQL database")

    def get_runs(self, project_id, suite_id=None, created_after:int=0, limit=100, offset=0):
        if suite_id:
            query = "SELECT id, name, created_on, completed_on FROM runs WHERE project_id = %s and suite_id = %s and is_completed = 1 and is_plan = 0 and created_on > %s ORDER BY id DESC LIMIT %s OFFSET %s"
            params = (project_id, suite_id, created_after, limit, offset,)
        else:
            query = "SELECT id, name, created_on, completed_on FROM runs WHERE project_id = %s and is_completed = 1 and is_plan = 0 and created_on > %s ORDER BY id DESC LIMIT %s OFFSET %s"
            params = (project_id, created_after, limit, offset,)
        return self._get(query, params)
    
    def count_results(self, run_id:int) -> int:
        query = "SELECT COUNT(*) FROM tests WHERE run_id = %s"
        params = (run_id,)
        cursor = self._execute_query(query, params)
        if cursor:
            return cursor.fetchone()[0]
        return 0

    def get_results(self, run_id:int, limit:int = 100, offset:int = 0):
        query = "SELECT r.case_id, r.status_id, r.tested_by, r.tested_on, b.comment, b.elapsed, b.defects FROM tests AS r LEFT JOIN test_changes AS b ON r.id = b.test_id where r.run_id = %s LIMIT %s OFFSET %s"
        params = (run_id, limit, offset)
        return self._get(query, params)

    def get_plans(self, limit:int = 100, offset:int = 0):
        query = "SELECT * FROM plans LIMIT %s OFFSET %s"
        params = (limit, offset)
        return self._get(query, params)
    
    def get_suites(self, project_id: int):
        query = "SELECT id, name FROM suites WHERE project_id = %s and is_copy = 0"
        params = (project_id,)
        return self._get(query, params)
    
    def get_projects(self):
        return self._get("SELECT id, name, is_completed, suite_mode FROM projects")
    
    def get_users(self):
        return self._get("SELECT id, name, email, is_active FROM users")
    
    def count_runs(self, project_id:int, created_after:int = 0, suite_id:int = None) -> int:
        if suite_id:
            query = "SELECT COUNT(*) FROM runs WHERE project_id = %s and suite_id = %s and is_completed = 1 and is_plan = 0 and created_on > %s"
            params = (project_id, suite_id, created_after,)
        else:
            query = "SELECT COUNT(*) FROM runs WHERE project_id = %s and is_completed = 1 and is_plan = 0 and created_on > %s"
            params = (project_id, created_after,)

        cursor = self._execute_query(query, params)
        if cursor:
            return cursor.fetchone()[0]
        return 0
    
    def _get(self, query, params = None):
        cursor = self._execute_query(query, params)
        if cursor:
            columns = [col[0] for col in cursor.description]
            result = []
            for row in cursor.fetchall():
                res = dict(zip(columns, row))
                result.append(res)
            return result
        return []
    
    def _execute_query(self, query, params=None):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor
        except mysql.connector.Error as e:
            print("Error executing query:", e)
            return None