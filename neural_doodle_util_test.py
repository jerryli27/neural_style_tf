from neural_doodle_util import *


class NeuralDoodleUtilTest(tf.test.TestCase):
    def test_gramian_with_mask(self):
        with self.test_session():
            batch_size = 1
            height = 2
            width = 3
            num_features = 2
            num_masks = 2
            size = height * width * num_features * 1.0

            input_layer = tf.placeholder(dtype=tf.float32, shape=(batch_size, height, width, num_features))
            init_input_layer = np.array([[[[1, 1], [2, 0], [3, 0]], [[4, 0], [5, 0], [6, 0]]]])

            masks = tf.placeholder(dtype=tf.float32, shape=(batch_size, height, width, num_masks))
            init_masks = np.array([[[[1, 0], [1, 0], [1, 0]], [[1, 0], [1, 0], [0, 1]]]])

            masked_gramian = gramian_with_mask(input_layer, masks)

            feeddict = {input_layer: init_input_layer,
                        masks: init_masks}

            layer_dot_mask = vgg_layer_dot_mask(masks, input_layer)
            layer_dot_mask_output = layer_dot_mask.eval(feeddict)

            init_mask_mean = [5.0/6.0, 1.0/6.0]

            expected_output = np.array([[[[sum([i ** 2 for i in range(1, 6)]) / init_mask_mean[0], 1 / init_mask_mean[0]], [1 / init_mask_mean[0], 1 / init_mask_mean[0]]]],
                                        [[[6**2 / init_mask_mean[1], 0 / init_mask_mean[1]], [0 / init_mask_mean[1], 0 / init_mask_mean[1]]]]]) / size
            actual_output = masked_gramian.eval(feeddict)
            np.testing.assert_almost_equal(actual_output, expected_output, decimal=4)


if __name__ == '__main__':
    tf.test.main()
