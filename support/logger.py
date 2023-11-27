import datetime

class Logger:
    def __init__(self, debug: bool = False, log_file: str = './log.txt'):
        if log_file == None:
            log_file = './log.txt'
        self.log_file = log_file
        self.debug = debug
        with open(self.log_file, 'w'):
            pass

    def log(self, message: str):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        log = f"[{time_str}] {message}\n"
        if self.debug:
            print(log)
            print()
        with open(self.log_file, 'a') as f:
            f.write(log)

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