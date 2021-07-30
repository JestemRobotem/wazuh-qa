from abc import ABC, abstractmethod


class Test(ABC):
    """ Abstract class to be extended by Pytest and used by TestLauncher.

    Attributes:
        tests_path (str): Path to the set of tests to be executed
        tests_run_dir (str): Path to the directory from where the tests are going to be executed

    Args:
        tests_path (str): Path to the set of tests to be executed
        tests_run_dir (str): Path to the directory from where the tests are going to be executed

    """

    def __init__(self, tests_path, tests_run_dir):
        self.tests_path = tests_path
        self.tests_run_dir = tests_run_dir
        self.result = None

    @abstractmethod
    def run(self):
        pass