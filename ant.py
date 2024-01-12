# this module will contain all the classes for ANT
import csv
from types import NoneType

from icmplib import ping, Host
from datetime import datetime
import logging

logger = logging.getLogger("ant")


# TODO: add logging throughout this module, it's only in a few places at the moment.

class ImportHandler:
    # Base class for all import handlers. It will contain methods for importing test cases from various sources.
    # Child classes will be responsible for handling the specifics of how they get each test from their respective
    # medium (eg. CSV file). After that, the child class will hand back to the super's import_tests method,
    # which will do the common work of creating Test objects and appending them to tests[].
    def __init__(self):
        self.intermediate = []  # this is the common interface between the child class and the super class
        self.tests = []  # this will be a list of Test objects

    def import_tests(self):
        # this method will import the tests from the source and store them in the tests attribute It is expected that
        # the child class will extend this method, first running its own specific tasks to get the tests from the
        # source, putting those tests into a list of dicts, with each dict being the raw data for constructing a Test
        # object. Then the super's import_tests method is called to do the common work of creating Test objects and
        # appending them to tests[]. Specifically, the parent class will need to examine a test_type key within each
        # dict, and decide what type of Test object is created. For example, if test_type = 'ping', then a PingTest
        # object will be created.
        for test in self.intermediate:
            if test[
                'test_type'] == 'ping':  # TODO: factor 'ping' out to a PingTest class attribute and change the literal to PingTest.name or something similarly named
                # create a PingTest object and append it to tests[]. But we want to omit any arguments which are None.
                # This is because the PingTest constructor can't handle None arguments. So we create a dict of
                # arguments to be passed to the PingTest constructor as **kwargs, omitting any arguments that are None.
                # This is necessary because icmplib.ping is poorly written and can't handle arguments that are None.
                # we also want to omit test_type as that's not a relevant argument for PingTest.

                ping_args = {}
                for key, value in test.items():
                    if value is not None and key != 'test_type':
                        ping_args[key] = value
                self.tests.append(PingTest(**ping_args))

                # self.tests.append(PingTest(id_number=test['test_id'], destination=test['destination'],
                #                            count=test['packet_count'], payload_size=test['payload_size'],
                #                            interval=test['interval'], timeout=test['timeout'],
                #                            family=test['addr_family']))
            elif test['test_type'] == 'traceroute':
                # create a TracerouteTest object and append it to tests[]
                pass
            else:
                # throw an exception
                pass


class ManualImportHandler(ImportHandler):
    # This class is mostly for dev/test. It adds a single ping test to intermediate[] to a well-known IP address.
    def __init__(self, destination="8.8.8.8"):
        super().__init__()
        self.destination = destination

    def import_tests(self):
        self.intermediate.append(
            {'test_type': 'ping', 'test_id': 1, 'destination': self.destination, 'count': 5, 'interval': 0.2,
             'timeout': 1, 'family': 4, 'privileged': False})
        super().import_tests()


class CsvImportHandler(ImportHandler):
    # this class will contain methods for importing test cases from a CSV file. It will inherit from ImportHandler.
    # There will be an import method which takes a file path and imports the contents of the file into an attribute
    def __init__(self, file_path):
        self.file_path = file_path
        super().__init__()

    def import_tests(self):
        # this child class method does the specifics of importing tests from a CSV file. It will read the contents of
        # the CSV and put the data into self.intermediate[] (list of dicts). Then it will call the parent class's
        # import_tests method. Effectively the child import_tests() method is an adapter that translates the CSV file
        # into a list of dicts, which is the common interface between the child and parent classes.

        # Because DictReader converts empty fields to '', we need to convert any '' values to None manually
        with open(self.file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            row: dict  # this is a type-hint to prevent a spurious PyCharm warning from appearing
            for row in reader:
                self.intermediate.append(self.data_cleaner(data=row))

        super().import_tests()  # get the parent class to do the rest of the work

    @staticmethod
    def data_cleaner(data: dict) -> dict:
        """
        This method takes a dict as an argument, and makes certain data-type modifications to correct for quirks of
        Csv.DictReader and CSV files in general, namely that empty fields are converted to '', and that all fields
        are strings. Note: validations/transforms that are specific to a particular test type are done within the
        individual Test subclass's constructor.
        :param data: a CSV row that has been imported as a dict by Csv.DictReader
        :return: the same dict, but with the data cleaned
        """
        for key, value in data.items():
            # Convert empty strings to None early in the import process, as this is a text-file specific issue.
            if value == '':
                data[key] = None
            # We want the test_id to be converted to int as soon as possible in the import process.
            if key == 'test_id':
                data[key] = int(value)
        return data


class ExportHandler:
    # this will be a base class for all export handlers. It will contain methods for exporting test results to
    # various sources. I'm not sure what this base class should have in it, to begin with.
    def __init__(self):
        pass

    def export_results(self, tests):
        # this method will take a list of Test objects and export the results to the source. It is expected that
        # the child class will extend this method, first running its own specific tasks to export the results to the
        # source. Then the super's export_results method is called to do the common work of exporting the results.
        pass


class DummyExportHandler(ExportHandler):
    # this class is for test/development purposes; it will simply display test results to the screen.
    def __init__(self):
        super().__init__()

    def export_results(self, result):
        """
        This method immediately outputs a result to the screen. It is mostly for testing purposes.
        :param result: an instance of a Result subclass, e.g. PingResult
        :return: None
        """
        # TODO: develop a table-based version, either as a separate ExportHandler subclass, or as an option within this class
        if isinstance(result, PingResult):
            # need to convert the timestamp to something nicer, like hh:mm:ss dd-mm-yyyy
            timestamp_str = result.timestamp.strftime("%H:%M:%S %d-%m-%Y")
            print(f'\nResults for ping test to: {result.destination} at {timestamp_str}')
            print('Destination address: {}'.format(result.destination))
            print('Is reachable: {}'.format(result.is_alive))
            print('RTT min/avg/max: {} / {} / {} ms'.format(result.min_rtt, result.avg_rtt, result.max_rtt))
            # print('RTTs: {}'.format(result.rtts))
            print('Packets sent/received/%loss: {} / {} / {}%'.format(result.packets_sent, result.packets_received,
                                                                      result.packet_loss * 100))
            print('Packets received: {}'.format(result.packets_received))
            print('Jitter: {}'.format(result.jitter))
            print('Timestamp: {}'.format(result.timestamp))
        elif isinstance(result, TracerouteTest):
            pass
        else:
            # throw an exception
            pass


class FileExportHandler(ExportHandler):
    # this class will contain methods for exporting test results to a file. It will inherit from ExportHandler.
    def __init__(self):
        super().__init__()
        pass


class Result:
    # This is a base class for all results. It will mostly be a data class that stores the results of a test. There
    # will be child classes (eg. PingResult) that have attributes specific to that kind of test.
    def __init__(self, timestamp, id_number):
        # the common attribute across all results is the timestamp
        self.timestamp = timestamp
        self.id_number = id_number


class PingResult(Result):
    # This class will contain the results of a ping test
    def __init__(self, timestamp, id_number, host_obj):
        """
        Data-oriented class that holds the results of a ping test. It is a subclass of Result, and it is expected that
        the TestEngine class will call the run() method of a PingTest object, which will return a PingResult object.
        :param timestamp: a datetime object representing the date/time that the test was run
        :param id_number: the ID number of the test that this result is for
        :param host_obj: This must be icmplib.Host object, which is what icmplib.ping returns.
        """
        # initialise all the arguments to instance attributes
        self.destination = host_obj.address
        self.is_alive = host_obj.is_alive
        self.min_rtt = host_obj.min_rtt
        self.avg_rtt = host_obj.avg_rtt
        self.max_rtt = host_obj.max_rtt
        self.rtts = host_obj.rtts
        self.packets_sent = host_obj.packets_sent
        self.packets_received = host_obj.packets_received
        self.packet_loss = host_obj.packet_loss
        self.jitter = host_obj.jitter
        self.str_format = host_obj.__str__()

        # if len(args) == 1 and isinstance(args[0], Host):
        #     # this means that the result is being passed in as an icmplib.Host object
        #     self.destination = args[0].address
        #     self.is_alive = args[0].is_alive
        #     self.min_rtt = args[0].min_rtt
        #     self.avg_rtt = args[0].avg_rtt
        #     self.max_rtt = args[0].max_rtt
        #     self.rtts = args[0].rtts
        #     self.packets_sent = args[0].packets_sent
        #     self.packets_received = args[0].packets_received
        #     self.packet_loss = args[0].packet_loss
        #     self.jitter = args[0].jitter
        #     self.str_format = args[0].__str__()
        # elif kwargs and 'host_obj' in kwargs:
        #     # check if a 'host_obj' argument was passed in **kwargs, and if it was, then use that to populate the
        #     # attributes. If not, then use the kwargs to populate the attributes individually.
        #     # this means that the result is being passed in as an icmplib.Host object
        #     self.destination = kwargs['host_obj'].address
        #     self.is_alive = kwargs['host_obj'].is_alive
        #     self.min_rtt = kwargs['host_obj'].min_rtt
        #     self.avg_rtt = kwargs['host_obj'].avg_rtt
        #     self.max_rtt = kwargs['host_obj'].max_rtt
        #     self.rtts = kwargs['host_obj'].rtts
        #     self.packets_sent = kwargs['host_obj'].packets_sent
        #     self.packets_received = kwargs['host_obj'].packets_received
        #     self.packet_loss = kwargs['host_obj'].packet_loss
        #     self.jitter = kwargs['host_obj'].jitter
        #     self.str_format = args[0].__str__()
        # else:
        #     raise TypeError('Invalid arguments passed to PingResult constructor')

        super().__init__(timestamp=timestamp, id_number=id_number)

    def __str__(self):
        return self.str_format


class Test:
    # this will be a base class for classes that represent different types of network test (eg. PingTest,
    # TracerouteTest). Each test will contain both the test's parameters (eg. destination IP address),
    # and the results of the test. This is because the results of a test are particular to the type of test,
    # eg. a ping test has two categories of results: 1) it proves reachability to the destination, and 2) it measures
    # the round-trip time (min, max, avg, stddev) to the destination. A traceroute test has a different set of
    # results, eg. the list of hops between the source and destination. So it makes sense for each Test subclass to
    # have its own custom results data structure. Or would it make more sense to have a Result parent class with eg.
    # PingResult and TracerouteResult subclasses?
    def __init__(self, id_number):
        self.id_number = self.convert_type(id_number, int)
        self.timestamp = None
        self.results = None

    def run(self):
        # Get the current date/time and store it in the results object
        self.timestamp = datetime.now()

    @staticmethod
    def convert_type(arg, to_type):
        """
        Conditional data type changer for converting data types only if necessary. This is to reduce code duplication
        in the constructors of any Test subclasses that use libraries like icmplib which are strictly typed. It's
        generic enough to be kept in the parent class, further reducing code duplication.
        :param arg: the variable that needs checking/converting
        :param to_type: the target data type, e.g. int | float | bool
        :return: the converted variable, or the original variable if no conversion was necessary
        """
        if isinstance(arg, to_type):
            return arg
        else:
            try:
                if to_type == bool:
                    if arg.lower() == "true":
                        return True
                    elif arg.lower() == 'false':
                        return False
                    else:
                        raise ValueError
                else:
                    return to_type(arg)
            except ValueError:
                raise TypeError(f"Cannot convert {arg} to {to_type}")


class PingTest(Test):
    # This class will contain the parameters and execution code for a ping test
    def __init__(self, id_number, destination, count=5, interval=0.2, payload_size=56, timeout=1, family=4,
                 privileged=False):
        super().__init__(id_number=id_number)

        # Before assigning arguments to instance attributes, we do some data-cleaning to convert some
        # str values to int, float or bool values, using isinstance(var, type). Each assignment will check the 
        # argument's type, and type-convert it if necessary. We have already converted '' to None in the 
        # CsvImportHandler.data_cleaner() method, so we don't need to do that here.

        # this one doesn't need any conversion
        self.destination = destination

        # arguments that will need converting to int: count, payload_size, timeout, family
        self.count = self.convert_type(count, int)
        self.payload_size = self.convert_type(payload_size, int)
        self.timeout = self.convert_type(timeout, int)
        self.family = self.convert_type(family, int)
        self.interval = self.convert_type(interval, float)
        self.privileged = self.convert_type(privileged, bool)

    def run(self) -> PingResult:
        """
        Runs a ping test, and returns a PingResult object. This method is called by the TestEngine class and it
        expects all data fields to be correctly typed.
        :return: PingResult object instance.
        """

        # First run whatever the parent class's run method is (do timestamping etc)
        super().run()

        logger.info(
            f"Running ping test with the following parameters: destination={self.destination}, count={self.count}, "
            f"interval={self.interval}, payload_size={self.payload_size}, timeout={self.timeout}, "
            f"family={self.family}, privileged={self.privileged}")

        host = ping(address=self.destination, count=self.count, interval=self.interval, payload_size=self.payload_size,
                    timeout=self.timeout, family=self.family, privileged=self.privileged)

        logger.info(f"ping result for {host.address}. Host status: {'UP' if host.is_alive else 'DOWN'}. "
                    f"RTT values (min/avg/max/jitter): {host.min_rtt}/{host.avg_rtt}/{host.max_rtt}/{host.jitter}. "
                    f"Packets sent/received/loss: {host.packets_sent}/{host.packets_received}/{host.packet_loss * 100}%.")

        return PingResult(timestamp=self.timestamp, id_number=self.id_number, host_obj=host)


class TestEngine:
    # this class will contain all the methods for performing network tests. Its constructor will take an
    # ImportHandler object and an ExportHandler object as an argument. These objects will be like plug-ins that
    # abstract the TestEngine from caring about where the testing cases come from and how/where the results are
    # stored/exported.
    def __init__(self, import_handler: ImportHandler, export_handler: ExportHandler):
        self.import_handler = import_handler
        self.export_handler = export_handler
        self.import_handler.import_tests()  # this will populate the tests[] attribute
        self.tests = import_handler.tests  # this will be a list of Test objects

    def run_tests(self):
        # this method will run all the tests in the tests[] attribute. It will call the run() method of each test.
        # Then it will call the export_handler's export_results() method, passing it the tests[] attribute.
        for test in self.tests:
            result = test.run()
            self.export_handler.export_results(result)
