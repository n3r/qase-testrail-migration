import base64
import time
import requests

class TestrailApiClient:
    def __init__(self, base_url, user, token, max_retries=3, backoff_factor=1):
        base_url = base_url
        if not base_url.endswith('/'):
            base_url += '/'
        self.base_url = base_url
        self.__url = base_url + 'index.php?/api/v2/'

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

    def get(self, uri):
        return self.send_request(requests.get, uri)

    def send_request(self, request_method, uri, payload=None):
        url = self.__url + uri
        for attempt in range(self.max_retries + 1):
            response = request_method(url, headers=self.headers, data=payload)
            if response.status_code != 429 and response.status_code <= 201:
                return self.process_response(response, uri)
            if response.status_code == 403 and uri[:15] == 'get_attachment/':
                raise APIError('Attachment not found.')
            if response.status_code == 400:
                raise APIError('Invalid data or entity not found.')
            elif attempt == self.max_retries:
                raise APIError('Max retries reached or server error.')
            else:
                time.sleep(self.backoff_factor * (2 ** attempt))

    def process_response(self, response, uri):
        if uri[:15] == 'get_attachment/':
            return response
        else:
            try:
                return response.json()
            except:
                raise APIError('Failed to parse JSON response')

class APIError(Exception):
    pass