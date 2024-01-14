from ..service import QaseService, TestrailService
from ..support import Logger, Mappings

from typing import List

from io import BytesIO

import tempfile

from urllib.parse import unquote

import re

class Attachments:
    def __init__(self, qase_service: QaseService, testrail_service: TestrailService, logger: Logger) -> Mappings:
        self.qase = qase_service
        self.testrail = testrail_service
        self.logger = logger

        self.map = {}

    def check_and_replace_attachments(self, string: str, code: str) -> str:
        if string:
            attachments = self.check_attachments(string)
            if (attachments):
                self.import_attachments(code, attachments)
                return self.replace_attachments(string=string)
        return string
    
    def check_and_replace_attachments_array(self, attachments: list, code: str) -> list:
        result = []
        self.import_attachments(code, attachments)
        for attachment in attachments:
            result.append(self.map[attachment]['hash'])
        return result
    
    def check_attachments(self, string: str) -> List:
        if (string):
            return re.findall(r'index\.php\?/attachments/get/([a-f0-9-]+)', str(string))
        return []
    
    def import_attachments(self, code: str, testrail_attachments: List) -> None:
        for attachment in testrail_attachments:
            try: 
                self.logger.log(f'Importing attachment: {attachment}')
                data = self.testrail.get_attachment(attachment)
                attachment_data = self._get_attachment_meta(data)
            except Exception as e:
                self.logger.log(f'Exception when calling TestRail->get_attachment: {e}')
                continue
            self.map[attachment] = self.qase.upload_attachment(code, attachment_data)
        return
    
    def _get_attachment_meta(self, data: dict) -> dict:
        content = BytesIO(data.content)
        content.mime = data.headers.get('Content-Type', '')
        content.name = "attachment"
        filename_header = data.headers.get('Content-Disposition', '')
        match = re.search(r"filename\*=UTF-8''(.+)", filename_header)
        if match:
            content.name = unquote(match.group(1))

        # Hack for new api version
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'_{content.name}', mode='wb') as tmp_file:
            tmp_file.write(content.read())
            tmp_file_path = tmp_file.name

        return tmp_file_path


    def replace_attachments(self, string: str) -> str:
        try:
            string = re.sub(
                r'!\[\]\(index\.php\?/attachments/get/([a-f0-9-]+)\)',
                lambda match: f'![{self.map[match.group(1)]["filename"]}]({self.map[match.group(1)]["url"]})',
                string
            )
        except Exception as e:
            self.logger.log(f'Exception when replacing attachments: {e}')
        return string