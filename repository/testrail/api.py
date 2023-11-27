"""TestRail API binding for Python 3.x.

(API v2, available since TestRail 3.0)

Compatible with TestRail 3.0 and later.

Learn more:

http://docs.gurock.com/testrail-api2/start
http://docs.gurock.com/testrail-api2/accessing

Copyright Gurock Software GmbH. See license.md for details.
"""

import base64
import json

import requests

class TestrailApiRepository:
    def __init__(self, base_url, user, token):
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'index.php?/api/v2/'
        self.user = user
        self.token = token

    def _send_get(self, uri, filepath=None):
        """Issue a GET request (read) against the API.

        Args:
            uri: The API method to call including parameters, e.g. get_case/1.
            filepath: The path and file name for attachment download; used only
                for 'get_attachment/:attachment_id'.

        Returns:
            A dict containing the result of the request.
        """
        return self.__send_request('GET', uri, filepath)

    def _end_post(self, uri, data):
        """Issue a POST request (write) against the API.

        Args:
            uri: The API method to call, including parameters, e.g. add_case/1.
            data: The data to submit as part of the request as a dict; strings
                must be UTF-8 encoded. If adding an attachment, must be the
                path to the file.

        Returns:
            A dict containing the result of the request.
        """
        return self.__send_request('POST', uri, data)

    def __send_request(self, method, uri, data):
        url = self.__url + uri

        auth = str(
            base64.b64encode(
                bytes('%s:%s' % (self.user, self.token), 'utf-8')
            ),
            'ascii'
        ).strip()
        headers = {'Authorization': 'Basic ' + auth}

        headers['Content-Type'] = 'application/json'
        if method == 'POST':
            payload = bytes(json.dumps(data), 'utf-8')
            response = requests.post(url, headers=headers, data=payload)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code > 201:
            try:
                error = response.json()
            except:     # response.content not formatted as JSON
                error = str(response.content)
            raise APIError('TestRail API returned HTTP %s (%s)' % (response.status_code, error))
        else:
            if uri[:15] == 'get_attachment/':   # Expecting file, not JSON
                return response
            else:
                try:
                    return response.json()
                except: # Nothing to return
                    return {}
    
    def get_all_users(self):
        """Returns a list of users."""
        return self._send_get('get_users')
    
    def get_case_types(self):
        return self._send_get('get_case_types')
    
    def get_priorities(self):
        return self._send_get('get_priorities')
    
    def get_case_fields(self):
        return self._send_get('get_case_fields')
    
    def get_projects(self):
        return self._send_get('get_projects')
    
    def get_suites(self, project_id, offset = 0, limit = 100):
        suites = self._send_get('get_suites/' + str(project_id) + f'&limit={limit}')
        if (suites and len(suites) == limit):
            suites += self.get_suites(project_id, offset + limit, limit)
        return suites
    
    def get_sections(self, project_id: int, limit: int = 100, offset: int = 0, suite_id: int = 0):
        uri = 'get_sections/' + str(project_id) + f'&limit={limit}&offset={offset}'
        if (suite_id > 0):
            uri += f'&suite_id={suite_id}'
        return self._send_get(uri)
    
    def get_cases(self, project_id: int, suite_id: int = 0, limit: int = 250, offset: int = 0) -> dict:
        uri = 'get_cases/' + str(project_id) + f'&limit={limit}&offset={offset}'
        if (suite_id > 0):
            uri += f'&suite_id={suite_id}'
        return self._send_get(uri)
    
    def count_runs(self, project_id: int, suite_id: int = 0, created_after: int = 0) -> int:
        uri = 'get_runs/' + str(project_id) + f'&limit=1'
        if (created_after > 0):
            uri += f'&created_after={created_after}'
        if (suite_id > 0):
            uri += f'&suite_id={suite_id}'
        result = self._send_get(uri)
        return result['size']
    
    def get_runs(self, project_id: int, suite_id: int = 0, created_after: int = 0, limit: int = 250, offset: int = 0):
        uri = 'get_runs/' + str(project_id) + f'&limit={limit}&offset={offset}'
        if (created_after > 0):
            uri += f'&created_after={created_after}'
        if (suite_id > 0):
            uri += f'&suite_id={suite_id}'
        result = self._send_get(uri)
        return result['runs']
    
    def count_results(self, run_id: int):
        result = self._send_get('get_results_for_run/' + str(run_id) + f'&limit=1')
        return result['size']
    
    def get_results(self, run_id: int, limit: int = 250, offset: int = 0):
        result = self._send_get('get_results_for_run/' + str(run_id) + f'&limit={limit}&offset={offset}')
        return result['results']
    
    def get_attachment(self, attachment):
        return self._send_get('get_attachment/' + str(attachment))
    
    def count_plans(self, project_id: int, suite_id: int = 0, created_after: int = 0) -> int:
        uri = 'get_plans/' + str(project_id) + f'&limit=1'
        if (created_after > 0):
            uri += f'&created_after={created_after}'
        if (suite_id > 0):
            uri += f'&suite_id={suite_id}'
        result = self._send_get(uri)
        return result['size']
    
    def get_test(self, test_id: int):
        return self._send_get('get_test/' + str(test_id))

class APIError(Exception):
    pass