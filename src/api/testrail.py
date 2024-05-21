import base64
import time
import requests
import re
import http.client
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup


class TestrailApiClient:
    def __init__(self, base_url, user, token, logger, max_retries=7, backoff_factor=5, skip_csrf=False):
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'index.php?/api/v2/'
        self._attachment_url = base_url + 'index.php?/attachments/get/'
        self.logger = logger
        self.base_url = base_url

        self.auth = str(
            base64.b64encode(
                bytes('%s:%s' % (user, token), 'utf-8')
            ),
            'ascii'
        ).strip()

        self.headers = {
            'Authorization': 'Basic ' + self.auth,
            'Content-Type': 'application/json',
        }
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.page_size = 30

        # Create a session object
        self.session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': '*/*',
            'Connection': 'keep-alive',
        }
        login_response = self.session.post(base_url + 'index.php?/auth/login/', data={'name': user, 'password': token, 'rememberme': '1'}, headers=headers)

        soup = BeautifulSoup(login_response.content, 'html.parser')

        # Find the input tag with name="_token" and extract the value attribute
        self.csrf_token = None if skip_csrf is True else soup.find('input', {'name': '_token'})['value']

        if login_response.status_code != 200:
            self.logger.log('Failed to login to TestRail API and get auth cookie')
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
            except (requests.exceptions.Timeout, http.client.RemoteDisconnected, ConnectionResetError, requests.exceptions.ConnectionError) as e:
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
            self.logger.log('Failed to login to TestRail API and get auth cookie')
            return self.get(f'get_attachment/{id}')
        else:
            return self.session.get(self._attachment_url + id)
        
    def fetch_data(self, offset):
        data = {
            'offset': offset,
            'order_by': 'created_on',
            'order_dir': 'desc',
            '_token': self.csrf_token
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        self.logger.log(f'Getting attachments list, offset: {offset}')
        try:
            response = self.session.post(self.base_url + 'index.php?/attachments/overview/0', data=data, headers=headers)
            response_data = response.json()
            # Extract only the needed fields (id and project_id) from each item
            return [{"id": item["id"], "project_id": item["project_id"]} for item in response_data['data']]
        except Exception as e:
            self.logger.log(f'Failed to get attachments list, offset: {offset}: {e}')
            return None

    def get_attachments_list(self):
        max_workers = 24
        total_items = 120000
        attachments = []
        stop = False
        next_offset = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.fetch_data, offset) for offset in range(0, max_workers * self.page_size, self.page_size)]

            while futures:
                for future in as_completed(futures):
                    futures.remove(future)
                    result = future.result()
                    if result is None:  # If a future returned None, stop submitting new tasks
                        stop = True
                        self.logger.log('No more attachments to process')
                    else:
                        attachments.extend(result)
                        if not stop:
                            next_offset += self.page_size
                            if next_offset < total_items:  # Ensure we do not exceed total_items
                                futures.append(executor.submit(self.fetch_data, next_offset))
                            else:
                                stop = True  # No more offsets to process

        return attachments
        
        

class APIError(Exception):
    pass