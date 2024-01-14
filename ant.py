# this module will contain all the classes for ANT
import csv
import json
import sys

# from types import NoneType
from icmplib import ping, traceroute, Host
from datetime import datetime
import subprocess
import jc
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

    def initialise(self):
        """
        This method is called by all consumers of ImportHandler instances, and is for the handler to perform any
        initialisation tasks. For a CSV import handler this may mean reading the entire CSV file, whereas for a
        stream-based handler (database, API, etc) this method would just initialise the source (eg. open database).
        Generic tasks appear in this parent class initialise() method, and source-specific tasks appear in the child
        class's method. It is expected that the parent initialise() method is called *after* the child's; that is,
        the last line of the child's extended initialise() method should be super().initialise(). The parent method
        expects the child to have populated self.intermediate[] with a list of dicts, where each dict represents a
        test. The parent method then uses this data to create Test objects and append them to self.tests[].
        NOTE: in stream-based import handlers, we may OVERRIDE initialise() rather than extend it, since a stream-
        based handler will not be able to populate self.intermediate[] (or self.tests[]), as it's pulling in records
        one at a time from a source that's possibly remote.
        :return: None
        """
        # Iterate over intermediate[] and check what kind of test it is; create appropriate Test object accordingly.
        # TODO: I don't think this code all belongs here. Any issues that PingTest has with None values should be
        #  handled by PingTest's constructor, not here. Omitting test_type is okay to filter out here though, as that
        #  will be universal across all import sources.
        #  Also, The intermediate[] -> tests[] interface doesn't fit here for stream-based handlers, although they
        #  could just override the parent's initialise() entirely. Another approach would be to introduce a middle layer
        #  of subclassing, ie. ImportHandler -> StreamHandler | FileHandler, with StreamHandler -> SqlHandler,
        #  ApiHandler, etc. and FileHandler -> CsvHandler, JsonHandler, etc. The current code below would be used for
        #  the FileHandler parent class.
        # for test in self.intermediate:
        #     if test['test_type'] == PingTest.name:  # "ping"
        #         # Create a PingTest object and append it to tests[]. We want to omit any arguments which are None.
        #         # This is because the PingTest constructor has defaults for infrequently used values like IP version,
        #         # payload size, etc and we don't want to override those inadvertently if our importer (eg CSV) has
        #         # set those values to None. We also omit the test_type argument, as that's not relevant for PingTest.
        #
        #         # Make a dict of args for creating a PingTest, excluding None values as well as test_type
        #         # ping_args = {}
        #         ping_args = {key: value for key, value in test.items() if key != 'test_type'}
        #
        #         self.tests.append(PingTest(**ping_args))
        #         logger.debug(f"{self.__class__.__name__}: Added PingTest object to tests[]. ping_args = {ping_args}")
        #     elif test['test_type'] == 'traceroute':
        #         trace_args = {}
        #         for key, value in test.items():
        #             if value is not None and key != 'test_type':
        #                 trace_args[key] = value
        #
        #         self.tests.append(TracerouteTest(**trace_args))
        #     else:
        #         # throw an exception
        #         pass

        # This list must be updated when a new Test subclass is added
        test_classes = [PingTest, TracerouteTest]

        class_dict = {cls.name: cls for cls in test_classes}      # {"ping": PingTest, ... etc}

        for test in self.intermediate:
            cls = class_dict.get(test['test_type'])     # if test_type = "ping", cls = PingTest class
            args = {key: value for key, value in test.items() if key != 'test_type'}
            self.tests.append(cls(**args))


    def next_test(self):
        # This method will return the next test in import_handler.tests[], and will also remove it from the list.
        # This is to allow for stream-based data sources such as APIs or databases. For this method in the base class,
        # we will implement a simple pop from the list. Child classes can override this method to implement any
        # specific logic for their data source, such as initiating an HTTP request for the next record before
        # returning anything to the caller.

        # I'm thinking that a stream based handler could just extend this method, putting one test into tests[] before
        # calling super().next_test().

        # if self.tests is not empty, return the next test in the list and remove it from the list
        if self.tests:
            return self.tests.pop(0)
        else:
            return None


class ManualImportHandler(ImportHandler):
    # This class is mostly for dev/test. It adds one or more hard-coded tests to intermediate[].
    def __init__(self, destination="8.8.8.8"):
        super().__init__()
        self.destination = destination

    def initialise(self):
        self.intermediate.append(
            {'test_type': 'ping', 'id_number': 1, 'destination': self.destination, 'count': 10, 'interval': 0.2,
             'timeout': 1, 'family': 4, 'privileged': False}
        )
        self.intermediate.append(
            {'test_type': 'traceroute', 'id_number': 2, 'destination': 'www.google.com'}
        )

        super().initialise()


class CsvImportHandler(ImportHandler):
    # this class will contain methods for importing test cases from a CSV file. It will inherit from ImportHandler.
    # There will be an import method which takes a file path and imports the contents of the file into an attribute
    def __init__(self, file_path):
        self.file_path = file_path
        super().__init__()

    def initialise(self):
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
            # write a logger.debug entry that gives the count of entries that were just imported
            logger.debug(f"{self.__class__.__name__}: Imported {len(self.intermediate)} tests "
                         f"from {self.file_path} to intermediate")

        super().initialise()  # get the parent class to do the rest of the work

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


class StdoutExportHandler(ExportHandler):
    # this class is mostly for test/development purposes; it will simply display test results to the screen.
    def __init__(self):
        super().__init__()

    def export_results(self, result):
        """
        This method immediately outputs a result to the screen. It is mostly for testing purposes.
        :param result: an instance of a Result subclass, e.g. PingResult
        :return: None
        """
        # TODO: I wonder if tabulated output would be feasible. The main problem is that different tests have
        #  different result attributs (table columns) so we should first develop more Test subclasses and see what
        #  the common attributes are.

        # TODO: consider pulling the code out of the if isinstance() block below, as we are now using Result's __str__
        #  method to correctly print the result, so this should be reusable for other types of test.  To be confirmed
        #  after we write the Traceroute parts of the program and see if its export code would be identical.

        if isinstance(result, PingResult):
            timestamp_str = result.timestamp.strftime("%H:%M:%S %d-%m-%Y")
            print(f'\nTimestamp:     {timestamp_str}')
            print(f"Destination: {result}")  # {result} is the entire Result object, which has a __str__ method
        elif isinstance(result, TracerouteResult):
            print(result)
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
    # This class will contain the results of an icmplib.ping test.
    def __init__(self, timestamp, id_number, host_obj: Host):
        """
        Data-oriented class that holds the results of a ping test. It is a subclass of Result, and it is expected that
        the TestEngine class will call the run() method of a PingTest object, which will return a PingResult object.
        :param timestamp: a datetime object representing the date/time that the test was run
        :param id_number: the ID number of the test that this result is for
        :param host_obj: This must be icmplib.Host object, which is what icmplib.ping returns.
        """
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

        super().__init__(timestamp=timestamp, id_number=id_number)

    def __str__(self):
        # return self.str_format
        return (
            f"Host {self.destination} status: {'UP' if self.is_alive else 'DOWN'}. RTT values (min/avg/max/jitter): "
            f"{self.min_rtt} / {self.avg_rtt} / {self.max_rtt} / {self.jitter}. Packets sent/received (loss%): "
            f"{self.packets_sent}/{self.packets_received} ({self.packet_loss * 100}%).")


class TracerouteResult(Result):
    # This class will contain the results of a command-line traceroute test that has been parsed by jc into a dict.
    # The arguments to the constructor will be timestamp, id_number, and data (the dict that jc returns).
    def __init__(self, timestamp, id_number, data):
        self.destination_ip = data['destination_ip']
        self.destination_name = data['destination_name']
        self.hops = data['hops']

        super().__init__(timestamp=timestamp, id_number=id_number)

    def __str__(self):
        # Define here so that we have a return-able value even if the whole block is skipped because self.hops is empty
        output_text = ""

        # The following block looks pretty gnarly but all it's doing is iterating over each hop to print each hop's
        # probes. And for each probe, it'll print that probe's full details (ip, name, RTT) if its IP address differs
        # from the preceding probe. This is how the real traceroute command's output works, ie. one or more probes
        # that have the same IP, do not need that probe's dest IP/name printed every time, but if adjacent probes have
        # different IPs they should be on their own line, for readability. This is how traceroute works under Darwin
        # (MacOS) and it's far more readable for hops where all probes do not pass through the same router IP.
        for hop in self.hops:
            hop_num_str = str(hop['hop'])
            pad_space = " " * (2 - len(hop_num_str))  # pad 1 or 0 spaces if hop_num is 1 or 2 chars long
            output_text += pad_space + hop_num_str + " " * 2
            if hop['probes']:  # if a whole hop got no probe responses, probes[] will be empty
                first_probe = hop['probes'][0]  # interim variable for readability's sake
                this_hop_text = f"{first_probe['name']} ({first_probe['ip']}) {first_probe['rtt']} ms"
                prev_ip = first_probe['ip']
                for probe in hop['probes'][1:]:  # for all probes except the first
                    if probe['ip'] == prev_ip:  # if this probe went via the same router IP as last probe
                        this_hop_text += " " * 2 + f"{probe['rtt']} ms"  # then stay on same line and just add the RTT
                    else:  # if this probe went via different router, print on a separate line
                        this_hop_text += "\n" + " " * 4 + f"{probe['name']} ({probe['ip']}) {probe['rtt']} ms"
                    prev_ip = probe['ip']  # update our previous-probe reference for the next iteration
            else:
                this_hop_text = "* * *"  # probe list is empty because this traceroute hop got no responses
            output_text += this_hop_text + "\n"

        return output_text

    """
    Example output - looks exactly like a MacOS traceroute, huh?
    
     1  mymodem (192.168.0.1) 4.973 ms
     2  ashs-mbp (192.168.0.180) 15.649 ms  2.728 ms  2.201 ms
     3  * * *
     4  * * *
     5  ashs-mbp (192.168.0.180) 252.135 ms  144.268 ms  16.953 ms
     6  10.5.86.72 (10.5.86.72) 27.017 ms  33.914 ms  16.121 ms
     7  203.50.63.96 (203.50.63.96) 16.198 ms  23.78 ms  12.975 ms
     8  bundle-ether26.stl-core30.sydney.telstra.net (203.50.61.96) 32.825 ms  17.052 ms  160.231 ms
     9  bundle-ether1.chw-edge903.sydney.telstra.net (203.50.11.177) 125.895 ms  23.198 ms  12.961 ms
    10  goo2503069.lnk.telstra.net (58.163.91.194) 17.526 ms
        74.125.49.138 (74.125.49.138) 16.775 ms  15.713 ms
    11  192.178.97.141 (192.178.97.141) 18.212 ms
        192.178.97.215 (192.178.97.215) 20.137 ms
        192.178.97.219 (192.178.97.219) 17.073 ms
    12  142.250.212.137 (142.250.212.137) 101.693 ms  16.833 ms  23.173 ms
    13  syd09s24-in-f4.1e100.net (142.250.76.100) 17.366 ms  18.382 ms  15.083 ms
    """


class Test:
    # This is a base class for classes that represent different types of network test (eg. PingTest,
    # TracerouteTest). Each test will contain the test's parameters (eg. destination IP address), an ID number and a
    # timestamp. There will be child classes (eg. PingTest) that have attributes specific to that kind of test.

    # define a placeholder Class attribute so that our logger string can use it
    name = None

    def __init__(self, id_number):
        self.id_number = self.convert_type(id_number, int)
        self.timestamp = None

    def run(self):
        """
        This method wraps the _specific_run() method, performing generic tasks before calling the child class's
        _specific_run() method, then finally generic tasks before returning the result to the caller. This avoids code
        repetition that would result if we had to put logger calls in every child class's run() method. See docstring
        for _specific_run() for more details.
        :return: A subclass of Result, eg. PingResult
        """

        # First run whatever the parent class's run method is (do timestamping etc)
        self.timestamp = datetime.now()

        logger_string = f"Running test {self.id_number} '{self.name}', parameters: "
        # Loop over this object's attributes and unpack them into a log-friendly string then append to logger_string.
        # This keeps the logger code generic so that it can live in the parent class and reduce code duplication.
        for key, value in self.__dict__.items():
            logger_string += f"{key}={value}, "
        logger.info(logger_string[:-2])  # remove the trailing comma and space

        result = self._specific_run()

        logger.info(f"Test {self.id_number} '{self.name}' completed. Result: {result}")

        return result

    def _specific_run(self):
        """
        This method is wrapped by the parent class's run() method, and contains the code that is specific to a child
        class's test type. E.g. for a PingTest this method calls icmplib.ping(). This design is known as the template
        method pattern. It allows the parent-class run() to contain the generic before/after stuff like logger calls,
        and avoids code repetition that would result if we had to put logger calls in every child class's run() method.
        :return: A subclass of Result, eg. PingResult
        """
        # When creating child classes, the only responsibility of this method is to run the actual test (eg. execute a
        # ping), perform specific data-mangling (if any) for this test type, then return the result. The parent class's
        # run() method takes care of the rest.
        pass

    @staticmethod
    def convert_type(arg, to_type):
        """
        Conditional data-type changer for converting data types only if necessary. This is to reduce code duplication
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
    # All Test subclasses must have a class attribute called 'name' which is a string that identifies the test type.
    name = "ping"

    # This class will contain the parameters and execution code for a ping test
    def __init__(self, id_number, destination, count=5, interval=0.2, payload_size=56, timeout=1, family=4,
                 privileged=False):
        super().__init__(id_number=id_number)

        # During assignment of arguments to instance attributes we ensure that any arguments that are explicitly None
        # are explicitly set to their defaults. If they are not None then we do some data-cleaning to convert some
        # str values to int, float or bool values, before assigning them to their respective instance attributes.
        # Note: We already convert '' to None in the CsvImportHandler.data_cleaner() method.
        # Note: we use "is not None" because other values (e.g. zero) will evaluate to False, and we don't want that.
        self.count = self.convert_type(count, int) if count is not None else 5
        self.payload_size = self.convert_type(payload_size, int) if payload_size is not None else 56
        self.timeout = self.convert_type(timeout, int) if timeout is not None else 1
        self.family = self.convert_type(family, int) if family is not None else 4
        self.interval = self.convert_type(interval, float) if interval is not None else 0.2
        self.privileged = self.convert_type(privileged, bool) if privileged is not None else False

        # this one doesn't need any conversion
        self.destination = destination

    def _specific_run(self) -> PingResult:
        """
        This method will be called by the parent class's run() method. It contains the code that is specific to this
        test type. For example, for a ping test, this method will contain the code that calls icmplib.ping(). This
        structure is known as the template method pattern, and we're using it so that we can 'wrap' the code specific
        to a type of test (eg. PingTest) with before and after code, like logger calls. This avoids us repeating the
        same logger calls in every Test subclass.
        :return: A subclass of Result, eg. PingResult
        """
        host = ping(address=self.destination, count=self.count, interval=self.interval, payload_size=self.payload_size,
                    timeout=self.timeout, family=self.family, privileged=self.privileged)
        test_result = PingResult(timestamp=self.timestamp, id_number=self.id_number, host_obj=host)

        return test_result


class TracerouteTest(Test):
    # All Test subclasses must have a class attribute called 'name' which is a string that identifies the test type.
    name = "traceroute"

    # This class will contain the parameters and execution code for a traceroute test
    def __init__(self, id_number, destination, count=3, timeout=1, max_probes=30, dont_resolve_names=False):
        super().__init__(id_number=id_number)

        # During assignment of arguments to instance attributes we do some data-cleaning to convert some str values to
        # int, float or bool values. Note: We already convert '' to None in the CsvImportHandler.data_cleaner() method,
        # so we don't need to do that here.

        # this one doesn't need any conversion
        self.destination = destination

        # arguments that will need converting to int: count, payload_size, timeout, family
        self.count = self.convert_type(count, int)
        self.timeout = self.convert_type(timeout, int)
        self.max_probes = self.convert_type(max_probes, int)
        self.dont_resolve_names = self.convert_type(dont_resolve_names, bool)

    def _specific_run(self) -> TracerouteResult:
        """
        This method will be called by the parent class's run() method. It contains the code that is specific to this
        test type. For example, for a ping test, this method will contain the code that calls icmplib.ping(). This
        structure is known as the template method pattern, and we're using it so that we can 'wrap' the code specific
        to a type of test (eg. PingTest) with before and after code, like logger calls. This avoids us repeating the
        same logger calls in every Test subclass.
        :return: A subclass of Result, eg. TracerouteResult
        """

        # Because all the Python libraries for traceroute require root privileges, we are going to rely on the Unix
        # traceroute utility, and we will combine this with the module 'jc', which converts the output of many Unix
        # command-line utilities into JSON, which is then easy to parse.

        # Step 0: construct the list parameter that subprocess.check_output requires, so that we can include our
        # constructor parameters as arguments to traceroute. For example, only include "-n" if resolve_names = True.

        command = [
            "traceroute",
            "-n" if self.dont_resolve_names else "",
            "-w", str(self.timeout),
            "-q", str(self.count),
            "-m", str(self.max_probes),
            self.destination,
        ]

        # filter out the empty string that may result if dont_resolve_names is False
        command = [option for option in command if option]

        logger.debug(f"Executing subprocess.check_output({command})")
        # run traceroute and capture stdout and stderr to cmd_output
        cmd_output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)

        # parse the cmd_output into a dictionary
        data = jc.parse("traceroute", cmd_output)
        # print(json.dumps(data, indent=3))

        # Step 3: parse the data into a TracerouteResult, maybe just timestamp, id_number, destination/address, and
        # hops (hops could optionally be a class, but we'll worry about that later)

        test_result = TracerouteResult(timestamp=self.timestamp, id_number=self.id_number, data=data)

        return test_result


class TestEngine:
    """
    This class is like an orchestrator that pull a test (Test subclass instance) from the assigned ImportHandler, runs
    test's run() method, then sends the results to the assigned ExportHandler.  Import Handlers and Export Handlers
    are like plug-ins that abstract the TestEngine from caring about where testing cases come from and how/where the
    results are stored/exported. This modularity allows extensibility, for example adding a web interface, or logic
    to switch on cloud resources.
    """

    def __init__(self, import_handler: ImportHandler, export_handler: ExportHandler):
        self.import_handler = import_handler
        self.export_handler = export_handler

        # Arguably the engine shouldn't have to tell the import_handler to "import tests". It would be better to have
        # a generically-named method like "initialise", because not all handlers will import their tests the way the
        # CsvImportHandler does. For example, what if we were importing tests from a database? We would want the
        # handler to simply initialise itself and perform any necessary setup that doesn't belong in the next() method,
        # e.g. set up a database connection, check for file existence, network connectivity (for APIs) etc.
        self.import_handler.initialise()
        self.tests = import_handler.tests

    def run_tests(self):
        """
        Runs all the tests that import_handler is willing to supply, by calling import_handler.next_test(). Having
        retrieved the next test (which is an instance of a Test subclass), it calls the test's run() method, then
        passes the result to the export handler.
        :return:
        """
        # Call the import_handler's next_test() method, which will return the next test in the list.
        while True:
            test = self.import_handler.next_test()
            if test is None:
                break
            else:
                result = test.run()
                self.export_handler.export_results(result)
