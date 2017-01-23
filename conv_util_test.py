import numpy as np

from conv_util import *


class ConvUtilTest(tf.test.TestCase):
    def test_mirror_padding(self):
        with self.test_session():
            batch = 1
            height = 3
            width = 3
            feature = 1
            input_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            kernel_size = 3
            out_channels = 1
            weights = tf.placeholder(tf.float32, [kernel_size, kernel_size, feature, out_channels], name='weights')
            biases = tf.placeholder(tf.float32, [out_channels], name='biases')
            stride = 1
            mirror_padded_convoluted_input_layer = conv2d_mirror_padding(input_layer, weights, biases, kernel_size,
                                                                         stride=stride)

            init_input_layer = np.array([[[[1], [2], [3]], [[4], [5], [6]], [[7], [8], [9]]]])

            feeddict = {input_layer: init_input_layer,
                        weights: np.ones((kernel_size, kernel_size, feature, out_channels)),
                        biases: np.zeros((out_channels))}

            expected_output = np.array([[[[33], [36], [39]], [[42], [45], [48]], [[51], [54], [57]]]])
            self.assertAllEqual(mirror_padded_convoluted_input_layer.eval(feeddict), expected_output)


if __name__ == '__main__':
    tf.test.main()
