"""
This file runs all the unit tests. Run this to make sure at least the functions tested are working as they're supposed
to.
"""

from neural_util_test import *
from neural_doodle_util_test import *
from mrf_util_test import *
from johnson_feedforward_net_util_test import *
from general_util_test import *
from conv_util_test import *
import unittest

# Not importing the following util test because it will require human input to verify the effect of the function.
# from sketches_util_test import *

if __name__ == '__main__':
    unittest.main()