from neural_util import *


class SquareTest(tf.test.TestCase):
    def testSquare(self):
        with self.test_session():
            x = tf.square([2, 3])
            self.assertAllEqual(x.eval(), [4, 9])
    def test_get_tensor_num_elements(self):
        with self.test_session():
            tensor_shape = [1,2,3,4,5,6,7]
            tensor = tf.placeholder(tf.float32, shape=tensor_shape)
            actual_output = get_tensor_num_elements(tensor)
            expected_output = 1*2*3*4*5*6*7
            self.assertEqual(actual_output, expected_output)

    def test_concat_content_img_style_weight_mask_to_input(self):
        with self.test_session():
            input_tensor = tf.placeholder(tf.float32, shape=[1,2,3,2])
            content_img_style_weight_mask = tf.placeholder(tf.float32, shape=[1,2,3,1])
            concatenated_tensor = concat_content_img_style_weight_mask_to_input(input_tensor, content_img_style_weight_mask)

            input_tensor_init = np.ones([1,2,3,2])
            content_img_style_weight_mask_init = np.zeros([1,2,3,1])
            feed_dict = {input_tensor:input_tensor_init, content_img_style_weight_mask:content_img_style_weight_mask_init}
            actual_output = concatenated_tensor.eval(feed_dict=feed_dict)
            expected_output = np.concatenate((input_tensor_init,content_img_style_weight_mask_init), axis=3)
            np.testing.assert_array_equal(actual_output, expected_output)

    # TODO: add unit tests for each function, but I'm too lazy to manually compute the gramian/variation etc.

if __name__ == '__main__':
    tf.test.main()
