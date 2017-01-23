import numpy as np

from mrf_util import *


class MrfUtilTest(tf.test.TestCase):
    def test_create_local_patches_sanity_check(self):
        with self.test_session():
            batch = 1
            height = 3
            width = 3
            feature = 1
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 3
            local_patches = create_local_patches(generated_layer, patch_size)

            init_generated_layer = np.array([[[[1], [2], [3]], [[4], [5], [6]], [[7], [8], [9]]]])

            feeddict = {generated_layer: init_generated_layer}

            expected_output = np.array([[[[1, 2, 3, 4, 5, 6, 7, 8, 9]]]])
            self.assertAllEqual(local_patches.eval(feeddict), expected_output)

    def test_create_local_patches_sanity_check_2(self):
        with self.test_session():
            batch = 1
            height = 3
            width = 3
            feature = 1
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            local_patches = create_local_patches(generated_layer, patch_size)

            init_generated_layer = np.array([[[[1], [2], [3]], [[4], [5], [6]], [[7], [8], [9]]]])

            feeddict = {generated_layer: init_generated_layer}

            expected_output = np.array([[[[1, 2, 4, 5], [2, 3, 5, 6]], [[4, 5, 7, 8], [5, 6, 8, 9]]]])
            self.assertAllEqual(local_patches.eval(feeddict), expected_output)

    def test_create_local_patches_sanity_check_3(self):
        with self.test_session():
            batch = 1
            height = 3
            width = 3
            feature = 2
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            local_patches = create_local_patches(generated_layer, patch_size)

            init_generated_layer = np.array(
                [[[[1, 1], [2, 2], [3, 3]], [[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]]]])

            feeddict = {generated_layer: init_generated_layer}

            expected_output = np.array([[[[1, 1, 2, 2, 4, 4, 5, 5], [2, 2, 3, 3, 5, 5, 6, 6]],
                                         [[4, 4, 5, 5, 7, 7, 8, 8], [5, 5, 6, 6, 8, 8, 9, 9]]]])
            self.assertAllEqual(local_patches.eval(feeddict), expected_output)

    def test_patch_matching_sanity_check(self):
        with self.test_session():
            batch = 1
            height = 3
            width = 3
            feature = 1
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            generated_layer_patches = create_local_patches(generated_layer, patch_size)

            style_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            style_layer_patches = create_local_patches(style_layer, patch_size)
            normalized_style_layer_patches = tf.nn.l2_normalize(style_layer_patches, dim=[3])
            actual_output = patch_matching(generated_layer_patches, normalized_style_layer_patches, patch_size)

            init_generated_layer = np.array([[[[1], [2], [3]], [[4], [5], [6]], [[7], [8], [9]]]])
            feeddict = {generated_layer: init_generated_layer, style_layer: init_generated_layer}
            expected_output = np.array([[[[1, 2, 4, 5], [2, 3, 5, 6]], [[4, 5, 7, 8], [5, 6, 8, 9]]]])
            expected_output = expected_output / np.expand_dims(np.linalg.norm(expected_output, axis=(3)), axis=3)
            np.testing.assert_array_almost_equal(actual_output.eval(feeddict), expected_output)

    def test_patch_matching_sanity_check_2(self):
        with self.test_session():
            batch = 2
            height = 3
            width = 3
            feature = 2
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            generated_layer_patches = create_local_patches(generated_layer, patch_size)

            style_layer = tf.placeholder(tf.float32, shape=(1, height, width, feature))
            patch_size = 2
            style_layer_patches = create_local_patches(style_layer, patch_size)
            normalized_style_layer_patches = tf.nn.l2_normalize(style_layer_patches, dim=[3])
            actual_output = patch_matching(generated_layer_patches, normalized_style_layer_patches, patch_size)

            init_generated_layer = np.array(
                [[[[1, 1], [2, 2], [3, 3]], [[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]]],
                 [[[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]], [[7, 7], [8, 8], [9, 9]]]])
            init_style_layer = np.array(
                [[[[1, 1], [2, 2], [3, 3]], [[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]]]])
            feeddict = {generated_layer: init_generated_layer, style_layer: init_style_layer}
            expected_output = np.array([[[[1, 1, 2, 2, 4, 4, 5, 5], [2, 2, 3, 3, 5, 5, 6, 6]],
                                         [[4, 4, 5, 5, 7, 7, 8, 8], [5, 5, 6, 6, 8, 8, 9, 9]]],
                                        [[[4, 4, 5, 5, 7, 7, 8, 8], [5, 5, 6, 6, 8, 8, 9, 9]],
                                         [[5, 5, 6, 6, 8, 8, 9, 9], [5, 5, 6, 6, 8, 8, 9, 9]]]])
            expected_output = expected_output / np.expand_dims(np.linalg.norm(expected_output, axis=(3)), axis=3)
            np.testing.assert_array_almost_equal(actual_output.eval(feeddict), expected_output)

    def test_mrf_loss_sanity_check(self):
        with self.test_session():
            batch = 2
            height = 3
            width = 3
            feature = 2
            generated_layer = tf.placeholder(tf.float32, shape=(batch, height, width, feature))
            patch_size = 2
            style_layer = tf.placeholder(tf.float32, shape=(1, height, width, feature))
            actual_output = mrf_loss(style_layer, generated_layer, patch_size=patch_size)

            init_generated_layer = np.array(
                [[[[1, 1], [2, 2], [3, 3]], [[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]]],
                 [[[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]], [[7, 7], [8, 8], [9, 9]]]])
            init_style_layer = np.array(
                [[[[1, 1], [2, 2], [3, 3]], [[4, 4], [5, 5], [6, 6]], [[7, 7], [8, 8], [9, 9]]]])
            feeddict = {generated_layer: init_generated_layer, style_layer: init_style_layer}
            # The first batch is a perfect match
            # The second batch has loss: 2^2  * 4 + 1^2  * 4+ 3^2* 4
            expected_output = (2.0 ** 2 * 4 + 1.0 ** 2 * 4 + 3.0 ** 2 * 4) / (
                height * width * feature) / patch_size ** 2
            self.assertAlmostEqual(actual_output.eval(feeddict), expected_output)


if __name__ == '__main__':
    tf.test.main()
