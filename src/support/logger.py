import datetime

import os

class Logger:
    def __init__(self, debug: bool = False, prefix: str = ''):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f'{prefix}_{timestamp}.log'
        log_dir = './logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_file = os.path.join(log_dir, f'{filename}')
        self.debug = debug
        with open(self.log_file, 'w'):
            pass

    def log(self, message: str, level: str = 'info'):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        log = f"[{time_str}][{level}] {message}\n"
        if self.debug:
            print(log)
        with open(self.log_file, 'a') as f:
            f.write(log)

    def divider(self):
        self.log('-----------------------------------')

    def print_status(self, message: str, completed: int = 0, total: int = 0, level: int = 0):
        icon = '↪'
        color_code = '34'
        if completed != 0 and total != 0:
            message = f"{message} [{completed}/{total}]"
        if completed == total:
            icon = '✓'
            color_code = '32'

        tabs = '\t'
        for i in range(level):
            tabs += '  '
        print(f"{tabs}\033[{color_code}m{icon}\033[0m {message}", end='\r', flush=True)
        if completed == total:
            print()

    def print_group(self, message: str):
        print(f"\t\033[35m↪\033[0m {message}", end='\r')
        print()