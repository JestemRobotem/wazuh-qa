# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import yaml
from enum import Enum
import os
import re

from wazuh_testing.qa_docs import QADOCS_LOGGER
from wazuh_testing.tools.logging import Logging
from wazuh_testing.tools.exceptions import QAValueError


class Config():
    """Class that parses the schema file and exposes the available configurations.

    Two modes of execution exist : `default mode` and `single test mode`.
    Predefined values are still missing, they will be added soon.

    The schema fields and pre-defined values can be checked here:
    https://github.com/wazuh/wazuh-qa/wiki/Documenting-tests-using-the-qadocs-schema#schema-blocks

    Attributes:
        mode (Mode): An enumeration that stores the `doc_generator` mode when it is running.
        project_path (str): A string that specifies the path where the tests to parse are located.
        include_paths (str): A list of strings that contains the directories to parse.
        include_regex (str): A list of strings(regular expressions) used to find test files.
        group_files (str): A string that specifies the group definition file.
        function_regex (list): A list of regular expressions used to find test functions.
        ignore_paths (str): A string that specifies which paths will be ignored.
        module_fields (_fields): A struct that contains the module documentation data.
        test_fields (_fields): A struct that contains the test documentation data.
        test_cases_field (_fields): A string that contains the test_cases key.
        test_types (list): A list with the types to be parsed.
        test_modules (list): A list with the modules to be parsed.
        test_names (list): A list with the tests to be parsed.
        LOGGER (_fields): A custom qa-docs logger.
    """
    LOGGER = Logging.get_logger(QADOCS_LOGGER)

    def __init__(self, schema_path, test_dir, output_path='', test_types=None, test_modules=None, test_names=None,
                 check_doc=False):
        """Constructor that loads the schema file and set the `qa-docs` configuration.

        If a test name is passed, it would be run in `single test mode`.
        And if an output path is not received, when is running in single test mode, it will be printed using the
        standard output. But if an output path is passed, there will be generated a JSON file with the same data that
        would be printed in `single test` mode.

        The default output path for `default mode` is `qa_docs_installation/output`, it cannot be changed.

        Args:
            schema_path (str): A string that contains the schema file path.
            test_dir (str): A string that contains the path of the tests.
            output_path (str): A string that contains the doc output path.
            test_types (list): A list that contains the tests type(s) to be parsed.
            test_types (list): A list that contains the test type(s) that the user specifies.
            test_modules (list): A list that contains the test module(s) that the user specifies.
            test_names (list): A list that contains the test name(s) that the user specifies.
            check_dock (boolean): Flag to indicate if the test specified (with -t parameter) is documented.
        """
        self.mode = Mode.DEFAULT
        self.project_path = test_dir
        self.include_paths = []
        self.include_regex = ["^test_.*py$"]
        self.group_files = "README.md"
        self.function_regex = ["^test_"]
        self.ignore_paths = []
        self.module_fields = _fields()
        self.test_fields = _fields()
        self.test_cases_field = None
        self.test_types = []
        self.test_modules = []
        self.predefined_values = {}
        self.check_doc = check_doc

        self.__read_schema_file(schema_path)
        self.__read_output_fields()
        self.__read_test_cases_field()
        self.__set_documentation_path(output_path.replace('\\', '/'))
        self.__read_predefined_values()

        if test_names is not None:
            # When a name is passed, it is using just a single test.
            self.mode = Mode.PARSE_TESTS
            self.test_names = test_names

        if test_types is None:
            self.__get_test_types()
        else:
            self.test_types = test_types

            if test_modules:
                self.test_modules = test_modules

        # Get the paths to parse
        self.__get_include_paths()

    def __set_documentation_path(self, path):
        """Set the path of the documentation output."""
        Config.LOGGER.debug('Setting the path documentation')
        self.documentation_path = path

    def __get_test_types(self):
        """Get all the test types within wazuh-qa framework."""
        for name in os.listdir(self.project_path):
            if os.path.isdir(os.path.join(self.project_path, name)):
                self.test_types.append(name)

    def __get_include_paths(self):
        """Get all the modules to include within all the specified types.

        The paths to be included are generated using this info.
        """
        dir_regex = re.compile("test_.")
        self.include_paths = []

        for type in self.test_types:
            subset_tests = os.path.join(self.project_path, type)

            if self.test_modules:
                for name in self.test_modules:
                    self.include_paths.append(os.path.join(subset_tests, name))
            else:
                for name in os.listdir(subset_tests):
                    if os.path.isdir(os.path.join(subset_tests, name)) and dir_regex.match(name):
                        self.include_paths.append(os.path.join(subset_tests, name))

    def __read_schema_file(self, file):
        """Read schema file.

        Args:
            file (string): A string that contains the file name.

        Raises:
            QAValuerError (IOError): Cannot load schema file.
        """
        try:
            Config.LOGGER.debug('Loading schema file')
            with open(file) as config_file:
                self._schema_data = yaml.safe_load(config_file)
        except IOError:
            raise QAValueError('Cannot load schema file', Config.LOGGER.error)

    def __read_predefined_values(self):
        """Read from the schema file the predefined values for the documentation fields.

        If predefined values are not defined in the schema file, an error will be raised.

        Raises:
            QAValueError: predefined values are missing in the schema file
        """
        Config.LOGGER.debug('Reading predefined values from the schema file')

        if not self._schema_data['predefined_values']:
            raise QAValueError('predefined values are missing in the schema file', Config.LOGGER.error)

        self.predefined_values = self._schema_data['predefined_values']

    def __read_module_fields(self):
        """Read from the schema file the optional and mandatory fields for the test module.

        If the module block fields are not defined in the schema file, an error will be raised.

        Raises:
            QAValueError: module fields are missing in the schema file
            QAValueError: mandatory module fields are missing in the schema file
        """
        Config.LOGGER.debug('Reading mandatory and optional module fields from the schema file')

        if 'module' not in self._schema_data['output_fields']:
            raise QAValueError('module fields are missing in the schema file', Config.LOGGER.error)

        module_fields = self._schema_data['output_fields']['module']

        if 'mandatory' not in module_fields and 'optional' not in module_fields:
            raise QAValueError('mandatory module fields are missing in the schema file', Config.LOGGER.error)

        if 'mandatory' in module_fields:
            self.module_fields.mandatory = module_fields['mandatory']

        if 'optional' in module_fields:
            self.module_fields.optional = module_fields['optional']

    def __read_test_fields(self):
        """Read from the schema file the optional and mandatory fields for the test functions.

        If the test block fields are not defined in the schema file, an error will be raised.

        Raises:
           QAValueError: test_fields are missing in the schema file
           QAValueError: mandatory module fields are missing in the schema file
        """
        Config.LOGGER.debug('Reading mandatory and optional test fields from the schema file')

        if 'test' not in self._schema_data['output_fields']:
            raise QAValueError('test_fields are missing in the schema file', Config.LOGGER.error)

        test_fields = self._schema_data['output_fields']['test']

        if 'mandatory' not in test_fields and 'optional' not in test_fields:
            raise QAValueError('mandatory module fields are missing in the schema file', Config.LOGGER.error)

        if 'mandatory' in test_fields:
            self.test_fields.mandatory = test_fields['mandatory']

        if 'optional' in test_fields:
            self.test_fields.optional = test_fields['optional']

    def __read_output_fields(self):
        """Read all the mandatory and optional fields from schema file.

        Raises:
            QAValueError: Documentation schema not defined in the schema file
        """
        if 'output_fields' not in self._schema_data:
            raise QAValueError('Documentation schema not defined in the schema file', Config.LOGGER.error)

        self.__read_module_fields()
        self.__read_test_fields()

    def __read_test_cases_field(self):
        """Read from the schema file the key to identify a Test Case list."""
        Config.LOGGER.debug('Reading Test Case key from the schema file')

        if 'test_cases_field' in self._schema_data:
            self.test_cases_field = self._schema_data['test_cases_field']


class _fields:
    """Struct for the documentation fields.

    Attributes:
        mandatory: A list of strings that contains the mandatory block fields
        optional: A list of strings that contains the optional block fields
    """
    def __init__(self):
        self.mandatory = []
        self.optional = []


class Mode(Enum):
    """Enumeration for behaviour classification

    The current modes that `doc_generator` has are these:

        Modes:
            DEFAULT: `default mode` parses all tests within tests directory.
            PARSE_TESTS: `single tests mode` parses a list of tests.

            For example, if you want to declare that it is running thru all tests directory, you must specify it by:

            mode = Mode.DEFAULT

    Args:
        Enum (Class): Base class for creating enumerated constants.
    """
    DEFAULT = 1
    PARSE_TESTS = 2
