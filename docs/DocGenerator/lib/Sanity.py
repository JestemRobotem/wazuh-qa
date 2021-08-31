"""
brief: Wazuh DocGeneratot sanity check module
copyright: Copyright (C) 2015-2021, Wazuh Inc.
date: August 02, 2021
license: This program is free software; you can redistribute it
         and/or modify it under the terms of the GNU General Public
         License (version 2) as published by the FSF - Free Software Foundation.
"""

import os
import re
import json
import ast
import logging
from lib.Utils import check_existance


class Sanity():
    """
    brief: Class in charge of performing a general sanity check on the already parsed documentation.
    It´s in charge of walk every documentation file, and every group file to dump the parsed documentation.
    """
    def __init__(self, config):
        self.conf = config
        self.files_regex = re.compile("^(?!.*group)test.*json$", re.IGNORECASE)
        self.error_reports = []
        self.found_tags = set()
        self.found_tests = set()
        self.found_modules = set()
        self.project_tests = 0

    def get_content(self, full_path):
        """
        brief: Loads a documentation file into a JSON dictionary.
        args:
            - "full_path (str): The documentation file."
        """
        try:
            with open(full_path) as file:
                return json.load(file)
        except:
            logging.error(f"Cannot load '{full_path}' file for sanity check")
            raise Exception(f"Cannot load '{full_path}' file for sanity check")

    def validate_fields(self, required_fields, available_fields):
        """
        brief: Method to check if all the required fields are present into the found ones.
               This method will be called recursively for nested dictionaries.
               If a required field isn´t found, the error is logged and written in a report structure for future print.
        args:
            - "required_fields (dict): The fields that must exist."
            - "available_fields (dict): The fields found into the documentation file."
        """
        if isinstance(required_fields, dict):
            for field in required_fields:
                if not check_existance(available_fields, field):
                    self.add_report(f"Mandatory field '{field}' is missing in file {self.scan_file}")
                    logging.error(f"Mandatory field '{field}' is missing in file {self.scan_file}")
                elif isinstance(required_fields[field], dict) or  isinstance(required_fields[field], list):
                    self.validate_fields(required_fields[field], available_fields)
        elif isinstance(required_fields, list):
            for field in required_fields:
                if isinstance(field, dict) or isinstance(field, list):
                    self.validate_fields(field, available_fields)
                else:
                    if not check_existance(available_fields, field):
                        self.add_report(f"Mandatory field '{field}' is missing in file {self.scan_file}")
                        logging.error(f"Mandatory field '{field}' is missing in file {self.scan_file}")

    def validate_module_fields(self, fields):
        """
        brief: Checks if all the mandatory module fields are present.
        args:
            - "fields(dict): The module fields found in the documentation file."
        """
        self.validate_fields(self.conf.module_fields.mandatory, fields)

    def validate_test_fields(self, fields):
        """
        brief: Checks if all the mandatory test fields are present.
        args:
            - "fields(dict): The test fields found in the documentation file."
        """
        if 'tests' in fields:
            for test_fields in fields['tests']:
                self.validate_fields(self.conf.test_fields.mandatory, test_fields)

    def identify_tags(self, content):
        """
        brief: Identifies every new tag found in the documentation files and saves it for future reporting.
        args:
            - "content(dict): The dictionary content of a documentation file."
        """
        if 'metadata' in content and 'tags' in content['metadata']:
            for tag in content['metadata']['tags']:
                self.found_tags.add(tag)

    def identify_tests(self, content):
        """
        brief: Identifies every new test found in the documentation files and saves it for future reporting.
        args:
            - "content(dict): The dictionary content of a documentation file."
        """
        if 'tests' in content:
            for test in content['tests']:
                self.found_tests.add(test['name'])

    def count_project_tests(self):
        """
        brief: Count how many tests are into every test file into the Project folder.
               This information will be used for a coverage report.
        """
        file_regexes = []
        function_regexes = []
        for regex in self.conf.include_regex:
            file_regexes.append(re.compile(regex))
        for regex in self.conf.function_regex:
            function_regexes.append(re.compile(regex))

        for (root, *_, files) in os.walk(self.conf.project_path, topdown=True):
            for regex in file_regexes:
                test_files = list(filter(regex.match, files))
                for test_file in test_files:
                    with open(os.path.join(root,test_file)) as fd:
                        file_content = fd.read()
                    module = ast.parse(file_content)
                    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)]
                    for function in functions:
                        for regex in function_regexes:
                            if regex.match(function.name):
                                self.project_tests = self.project_tests + 1

    def add_report(self, message):
        """
        brief: Adds a new entry to the report.
        args:
            - "message (string): Message to be included in the report."
        """
        self.error_reports.append(message)

    def print_report(self):
        """
        brief: Makes a report with all the errors found, the coverage and the tags found.
        """
        print("")
        print("During the sanity check:")

        print("")
        if self.error_reports:
            print("The following errors were found:")
            for error in self.error_reports:
                print("- "+error)
        else:
            print("No errors were found:")

        if self.found_tags:
            print("")
            print("The following tags were found:")
            for tag in self.found_tags:
                print("- "+tag)

        print("")
        modules_count = len(self.found_modules)
        tests_count = len(self.found_tests)
        tests_percentage = tests_count / self.project_tests * 100
        print(f"A total of {len(self.found_tests)} tests were found in {modules_count} modules")
        print("A {:.2f}% from the tests of {} is covered.".format(tests_percentage, self.conf.project_path))

    def run(self):
        """
        brief: Runs a complete sanity check of each documentation file on the output folder.
        """
        logging.info("\nStarting documentation sanity check")
        for (root, *_, files) in os.walk(self.conf.documentation_path, topdown=True):
            files = list(filter(self.files_regex.match, files))
            for file in files:
                full_path = os.path.join(root, file)
                content = self.get_content(full_path)
                if content:
                    self.scan_file = full_path
                    self.validate_module_fields(content)
                    self.validate_test_fields(content)
                    self.identify_tags(content)
                    self.identify_tests(content)
                    self.found_modules.add(content['name'])

        self.count_project_tests()
        self.print_report()
