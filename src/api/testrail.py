import base64
import time
import requests
import http.client

class TestrailApiClient:
    def __init__(self, base_url, user, token, max_retries=3, backoff_factor=8):
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'index.php?/api/v2/'
        self._attachment_url = base_url + 'index.php?/attachments/get/'

        auth = str(
            base64.b64encode(
                bytes('%s:%s' % (user, token), 'utf-8')
            ),
            'ascii'
        ).strip()

        self.headers = {
            'Authorization': 'Basic ' + auth,
            'Content-Type': 'application/json'
        }
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Create a session object
        self.session = requests.Session()
        login_response = self.session.post(base_url + 'index.php?/auth/login/', data={'name': user, 'password': token})
        if login_response.status_code != 200:
            self.session = None

    def get(self, uri):
        return self.send_request(requests.get, uri)

    def send_request(self, request_method, uri, payload=None):
        url = self.__url + uri
        for attempt in range(self.max_retries + 1):
            try:
                response = request_method(url, headers=self.headers, data=payload)
                if response.status_code != 429 and response.status_code <= 201:
                    return self.process_response(response, uri)
                if response.status_code == 403:
                    raise APIError('Access denied.')
                if response.status_code == 400:
                    raise APIError('Invalid data or entity not found.')
                else:
                    time.sleep(self.backoff_factor * (2 ** attempt))
            except (requests.exceptions.Timeout, http.client.RemoteDisconnected, ConnectionResetError) as e:
                time.sleep(self.backoff_factor * (2 ** attempt))
            
            if attempt == self.max_retries:
                raise APIError('Max retries reached or server error.')

    def process_response(self, response, uri):
        try:
            return response.json()
        except:
            raise APIError('Failed to parse JSON response')
            
    def get_attachment(self, id):
        if not self.session:
            return self.send_request(requests.get, f'get_attachment/{id}')
        else:
            return self.session.get(self._attachment_url + id)

class APIError(Exception):
    pass