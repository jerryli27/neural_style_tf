#!/usr/bin/env python
# -*- coding: utf-8 -*-
import shutil
import tempfile
import unittest

from general_util import *


class TestDataUtilMethods(unittest.TestCase):
    def test_get_global_step_from_save_dir(self):
        save_dir = 'model/savedir/model.ckpt-5000'
        expected_output = 5000
        actual_output = get_global_step_from_save_dir(save_dir)
        self.assertEqual(expected_output, actual_output)

    def test_get_all_image_paths_in_dir(self):
        dirpath = tempfile.mkdtemp()
        image_path = dirpath + '/image.jpg'
        f = open(image_path, 'w')
        f.close()
        subfolder = '/subfolder'
        os.makedirs(dirpath + subfolder)
        image_path2 = dirpath + subfolder + u'/骨董屋・三千世界の女主人_12746957.png'
        f = open(image_path2, 'w')
        f.close()
        actual_answer = get_all_image_paths_in_dir(dirpath + '/')
        expected_answer = [image_path, image_path2.encode('utf8')]
        shutil.rmtree(dirpath)
        self.assertEqual(expected_answer, actual_answer)

    def test_read_and_resize_images(self):
        height = 256
        width = 256
        batch_size = 8

        random_images = []

        content_folder = tempfile.mkdtemp()
        for i in range(batch_size):
            # DO NOT TEST WITH .jpg... There's a compression process. I debugged on this for half an hour.
            # Also refrain from using completely random image. There's a normalization process for saving the image.
            image_path = content_folder + ('/image_%d.png' % i)
            current_image = np.ones((height, width, 3)) * 255.0
            current_image[0, i, 0] = 0
            random_images.append(current_image)
            scipy.misc.imsave(image_path, random_images[-1])

        # Get path to all content images.
        content_dirs = get_all_image_paths_in_dir(content_folder + '/')

        content_pre_list = read_and_resize_images(
            get_batch_paths(content_dirs, 0, batch_size),
            height, width)

        expected_answer = random_images
        np.testing.assert_almost_equal(expected_answer, content_pre_list)

        shutil.rmtree(content_folder)

    def test_read_and_resize_batch_images(self):
        height = 256
        width = 256
        batch_size = 8

        random_images = []

        content_folder = tempfile.mkdtemp()
        for i in range(batch_size):
            # DO NOT TEST WITH .jpg... There's a compression process. I debugged on this for half an hour.
            # Also refrain from using completely random image. There's a normalization process for saving the image.
            image_path = content_folder + ('/image_%d.png' % i)
            current_image = np.ones((height, width, 3)) * 255.0
            current_image[0, i, 0] = 0
            random_images.append(current_image)
            scipy.misc.imsave(image_path, random_images[-1])

        # Get path to all content images.
        content_dirs = get_all_image_paths_in_dir(content_folder + '/')

        content_pre_list = read_and_resize_batch_images(
            get_batch_paths(content_dirs, 0, batch_size),
            height, width)

        expected_answer = np.round(np.array(random_images))
        np.testing.assert_almost_equal(expected_answer, content_pre_list)

        shutil.rmtree(content_folder)

    def test_read_and_resize_bw_mask_images(self):

        height = 256
        width = 256
        batch_size = 8
        semantic_masks_num_layers = 3
        num_images_per_batch = batch_size * semantic_masks_num_layers

        random_images = []

        content_folder = tempfile.mkdtemp()
        for i in range(batch_size):
            random_images.append([])
            for j in range(semantic_masks_num_layers):
                image_path = content_folder + ('/image_%d_%d.png' % (i, j))

                current_image = np.zeros((height, width, 3)) * 255.0
                rescaled = current_image.astype(np.uint8)
                random_images[-1].append(rescaled)

                f = Image.fromarray(random_images[-1][-1], 'RGB')
                f.save(image_path)

        # Get path to all content images.
        content_dirs = get_all_image_paths_in_dir(content_folder + '/')

        content_pre_list = read_and_resize_bw_mask_images(
            get_batch_paths(content_dirs, 0, num_images_per_batch),
            height, width, batch_size, semantic_masks_num_layers)

        temp = np.array(random_images)
        expected_answer = np.ndarray.astype(np.transpose(rgb2gray(temp), (0, 2, 3, 1)), np.int32)
        np.testing.assert_almost_equal(expected_answer, content_pre_list)

        shutil.rmtree(content_folder)

    def test_np_image_dot_mask(self):
        image = np.ones((1, 2, 3, 3))
        mask = np.ones((1, 2, 3, 2))

        image[0, 0, 0, 0] = 0
        mask[0, 0, 0, 1] = 2

        expected_output = np.ones((1, 2, 3, 6))
        expected_output[0, 0, 0, 0] = 0
        expected_output[0, 0, 0, 1] = 1
        expected_output[0, 0, 0, 2] = 1
        expected_output[0, 0, 0, 3] = 0
        expected_output[0, 0, 0, 4] = 2
        expected_output[0, 0, 0, 5] = 2

        actual_output = np_image_dot_mask(image, mask)

        np.testing.assert_array_equal(actual_output, expected_output)

    def test_imread_rgba(self):
        height = 256
        width = 256

        content_folder = tempfile.mkdtemp()
        image_path = content_folder + '/image.png'
        current_image = np.ones((height, width, 4)) * 255.0
        current_image[0, 0, 0] = 0
        scipy.misc.imsave(image_path, current_image)

        content_pre_list = imread(image_path, rgba=True)
        expected_answer = current_image
        np.testing.assert_almost_equal(expected_answer, content_pre_list)

        shutil.rmtree(content_folder)

    def test_imread_bw(self):
        height = 256
        width = 256

        content_folder = tempfile.mkdtemp()
        image_path = content_folder + u'/骨董屋・三千世界の女主人_12746957.png'
        current_image = np.ones((height, width, 3)) * 255.0
        current_image[0, 0, 0] = 0
        imsave(image_path, current_image)

        actual_output = imread(get_all_image_paths_in_dir(content_folder + '/')[0], bw=True)

        expected_answer = np.floor(rgb2gray(np.array(current_image)))
        np.testing.assert_almost_equal(expected_answer, actual_output)

    def test_imread_and_imsave_utf8(self):
        height = 256
        width = 256

        content_folder = tempfile.mkdtemp()
        image_path = content_folder + u'/骨董屋・三千世界の女主人_12746957.png'
        current_image = np.ones((height, width, 3)) * 255.0
        current_image[0, 0, 0] = 0
        imsave(image_path, current_image)

        actual_output = imread(get_all_image_paths_in_dir(content_folder + '/')[0])

        expected_answer = np.round(np.array(current_image))
        np.testing.assert_almost_equal(expected_answer, actual_output)

    def test_get_file_name(self):
        image_path = u'home/ubuntu/骨董屋・三千世界の女主人_12746957.png'
        actual_output = get_file_name(image_path)
        expected_output = u'骨董屋・三千世界の女主人_12746957'
        self.assertEqual(actual_output, expected_output)

    def test_get_batch_indices(self):
        dataset_len = 10
        start_index = 0
        batch_size = 3

        actual_output = get_batch_indices(dataset_len, start_index, batch_size)
        expected_output = [0, 1, 2]
        self.assertItemsEqual(actual_output, expected_output)

        start_index = 9
        actual_output = get_batch_indices(dataset_len, start_index, batch_size)
        expected_output = [9, 0, 1]
        self.assertItemsEqual(actual_output, expected_output)


if __name__ == '__main__':
    unittest.main()
