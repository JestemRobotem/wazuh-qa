import os
import re
import json
import yaml
import ast
from Config import Config
from CodeParser import CodeParser
from Utils import clean_folder
import warnings
import logging

class DocGenerator:
    def __init__(self):
        self.conf = Config()
        self.parser = CodeParser()
        self.__id_counter = 0
        self.ignore_regex = []
        for ignore_regex in self.conf.ignore_paths:
            self.ignore_regex.append(re.compile(ignore_regex))
        self.include_regex = []
        for include_regex in self.conf.include_regex:
            self.include_regex.append(re.compile(include_regex))

    def is_valid_folder(self, path):
        for regex in self.ignore_regex:
            if regex.match(path):
                return False
        return True

    def is_valid_file(self, path):
        for regex in self.ignore_regex:
            if regex.match(path):
                return False
        for regex in self.include_regex:
            match = False
            if regex.match(path):
                match = True
                break
        if not match:
            return False
        return True

    def is_group_file(self, path):
        for group_file in self.conf.group_files:
            if path == group_file:
                return True
        return False

    def get_group_doc_path(self, path):
        base_path = os.path.join(self.conf.documentation_path, os.path.basename(self.scan_path))
        relative_path = path.replace(self.scan_path, "")
        group_dir = os.path.dirname(relative_path)
        group_name = os.path.basename(group_dir)
        doc_path = base_path+os.path.join(group_dir, group_name)+".group"
        return doc_path

    def get_test_doc_path(self, path):
        base_path = os.path.join(self.conf.documentation_path, os.path.basename(self.scan_path))
        relative_path = path.replace(self.scan_path, "")
        doc_path = os.path.splitext(base_path + relative_path)[0]
        return doc_path

    def dump_output(self, content, doc_path):
        if not content:
            warnings.warn(f"Content for {doc_path} is empty, ignoring it", stacklevel=2)
            logging.warning(f"Content for {doc_path} is empty, ignoring it")
            return
        if not os.path.exists(os.path.dirname(doc_path)):
            os.makedirs(os.path.dirname(doc_path))
        with open(doc_path + ".json", "w+") as outfile:
            outfile.write(json.dumps(content, indent=4))
        with open(doc_path + ".yaml", "w+") as outfile:
            outfile.write(yaml.dump(content))

    def create_group(self, path, group_id):
        self.__id_counter = self.__id_counter + 1
        group = self.parser.parse_group(path, self.__id_counter, group_id)
        doc_path = self.get_group_doc_path(path)
        self.dump_output(group, doc_path)
        logging.debug(f"New group file '{doc_path}' was created with ID:{self.__id_counter}")
        return self.__id_counter

    def create_test(self, path, group_id):
        self.__id_counter = self.__id_counter + 1
        test = self.parser.parse_test(path, self.__id_counter, group_id)
        doc_path = self.get_test_doc_path(path)
        self.dump_output(test, doc_path)
        logging.debug(f"New documentation file '{doc_path}' was created with ID:{self.__id_counter}")
        return self.__id_counter

    def parse_folder(self, path, group_id):
        if not os.path.exists(path):
            warnings.warn(f"Include path '{path}' doesn´t exist", stacklevel=2)
            logging.warning(f"Include path '{path}' doesn´t exist")
            return
        if not self.is_valid_folder(path):
            logging.debug(f"Ignoring files on '{path}'")
            return
        (root, folders, files) = next(os.walk(path))
        for file in files:
            if self.is_group_file(file):
                group_id = self.create_group(os.path.join(root,file), group_id)
                break
        for file in files:
            if self.is_valid_file(file):
                self.create_test(os.path.join(root,file), group_id)
        for folder in folders:
            self.parse_folder(os.path.join(root,folder), group_id)

    def run(self):
        logging.info("\nStarting documentation parsing")
        clean_folder(self.conf.documentation_path)
        for path in self.conf.include_paths:
            self.scan_path = path
            logging.debug(f"Going to parse files on '{path}'")
            self.parse_folder(path, self.__id_counter)

LOG_FOLDER = "logs"
LOG_PATH = os.path.join(LOG_FOLDER, os.path.splitext(os.path.basename(__file__))[0]+".log" )
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)
logging.basicConfig(filename=LOG_PATH, level=logging.DEBUG)

docs = DocGenerator()
docs.run()
