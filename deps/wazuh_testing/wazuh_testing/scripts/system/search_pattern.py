import json
import re
import argparse
from wazuh_testing.tools.monitoring import FileMonitor

def make_callback(pattern, prefix="wazuh", escape=False):
    """
    Creates a callback function from a text pattern.

    Args:
        pattern (str): String to match on the log
        prefix  (str): String prefix (modulesd, remoted, ...)
        escape (bool): Flag to escape special characters in the pattern
    Returns:
        lambda function with the callback
    """
    if escape:
        pattern = re.escape(pattern)
    else:
        pattern = r'\s+'.join(pattern.split())

    full_pattern = pattern if prefix is None else fr'{prefix}{pattern}'
    regex = re.compile(full_pattern)

    return lambda line: regex.match(line.decode() if isinstance(line, bytes) else line)


def main():
    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument('-p', '--pattern', metavar='patterns', type=str, required=True, nargs="*",
                            default=None, help='Pattern to search', dest='pattern')

    arg_parser.add_argument('-f', '--file', metavar='file', type=str, required=True, nargs="*",
                            default=None, help='File to search the pattern', dest='file')

    arg_parser.add_argument('-t', '--timeout', metavar='timeout', type=int, required=True, nargs="*",
                            default=None, help='Timeout', dest='timeout')

    args = arg_parser.parse_args()

    for regex, file, timeout in zip(args.patterns, args.file, args.timeout):
        wazuh_log_monitor = FileMonitor(file)
        callback_search = make_callback(pattern=regex, prefix=None)
        match = wazuh_log_monitor.start(timeout=timeout, callback=callback_search, error_message="Regex not found").result()
        print(f"Regex {regex}: {[str(match.group(0))] + list(match.groups())}")

if __name__ == '__main__':
    main()
