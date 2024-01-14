from ant import TestEngine, ManualImportHandler, StdoutExportHandler, CsvImportHandler
import logging

"""################################### START OF LOGGER CONFIGURATION ###################################"""
# Create a custom logger
logger = logging.getLogger("ant")
logger.setLevel(logging.DEBUG)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler("ant.log")
c_handler.setLevel(logging.ERROR)
f_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
c_format = logging.Formatter("%(levelname)s: %(message)s")
f_format = logging.Formatter(fmt="%(asctime)s.%(msecs)03d - %(levelname)08s: %(funcName)s: %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)

"""#################################### END OF LOGGER CONFIGURATION ####################################"""

test_engine = TestEngine(ManualImportHandler(), StdoutExportHandler())
# test_engine = TestEngine(CsvImportHandler("tests.csv"), StdoutExportHandler())
test_engine.run_tests()
