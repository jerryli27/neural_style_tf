"""
This file contains utility functions for general purposes like image reading, saving, and resizing. No function here
contains tensorflow or neural network.
"""
import math
import os
import urllib
from operator import mul
from os.path import basename, dirname

import numpy as np
import scipy.misc
from PIL import Image
from typing import Union, List


def imread(path, shape=None, bw=False, rgba=False, dtype=np.float32):
    # type: (str, tuple, bool, bool) -> np.ndarray
    """

    :param path: path to the image
    :param shape: (Height, width)
    :param bw: Whether the image is black and white.
    :param rgba: Whether the image is in rgba format.
    :return: np array with shape (height, width, num_color(1, 3, or 4))
    """
    assert not (bw and rgba)
    if bw:
        convert_format = 'L'
    elif rgba:
        convert_format = 'RGBA'
    else:
        convert_format = 'RGB'

    if shape is None:
        return np.asarray(Image.open(path).convert(convert_format), dtype)
    else:
        return np.asarray(Image.open(path).convert(convert_format).resize((shape[1], shape[0])), dtype)


def imsave(path, img):
    # type: (str, np.ndarray) -> None
    """
    Automatically clip the image represented in a numpy array to 0~255 and save the image.
    :param path: Path to save the image.
    :param img: Image represented in numpy array with a legal format for scipy.misc.imsave
    :return: None
    """
    img = np.clip(img, 0, 255).astype(np.uint8)
    scipy.misc.imsave(path, img)


def read_and_resize_images(dirs, height=None, width=None, bw=False, rgba=False):
    # type: (Union[str,List[str]], Union[int,None], Union[int,None], bool, bool) -> Union[np.ndarray,List[np.ndarray]]
    """

    :param dirs: a single string or a list of strings of paths to images.
    :param height: height of outputted images. If height and width are both None, then the image is not resized.
    :param width: width of outputted images. If height and width are both None, then the image is not resized.
    :param bw: Whether the image is black and white
    :param rgba: Whether the image is in rgba format.
    :return: images resized to the specific height or width supplied. It is either a numpy array or a list of numpy
    arrays
    """
    if isinstance(dirs, list):
        images = [read_and_resize_images(d, height, width) for d in dirs]
        return images
    elif isinstance(dirs, str):
        image_1 = imread(dirs)
        # If there is no width and height, we automatically take the first image's width and height and apply to all the
        # other ones.
        if width is not None:
            if height is not None:
                target_shape = (height, width)
            else:
                target_shape = (int(math.floor(float(image_1.shape[0]) /
                                               image_1.shape[1] * width)), width)
        else:
            if height is not None:
                target_shape = (height, int(math.floor(float(image_1.shape[1]) /
                                                       image_1.shape[0] * height)))
            else:
                target_shape = (image_1.shape[0], image_1.shape[1])
        return imread(dirs, shape=target_shape, bw=bw, rgba=rgba)


def read_and_resize_batch_images(dirs, height, width, dtype=np.float32):
    # type: (List[str], Union[int,None], Union[int,None]) -> np.ndarray
    """

    :param dirs: a list of strings of paths to images.
    :param height: height of outputted images. If height and width are both None, then the images are not resized.
    :param width: width of outputted images. If height and width are both None, then the images are not resized.
    :return: an numpy array representing the resized images. The shape is (num_image, height, width, 3). Note this
    takes a while to format an image (3-6 seconds per image on average on my laptop.)
    """
    if height is None and width is None:
        shape = None
    else:
        if height is None or width is None:
            raise AssertionError('The height and width has to be both non None or both None.')
        shape = (height, width)
    images = [imread(d, shape=shape, dtype=dtype) for d in dirs]
    return np.array(images,dtype=dtype)


def read_and_resize_bw_mask_images(dirs, height, width, batch_size, semantic_masks_num_layers):
    # type: (List[str], Union[int,None], Union[int,None], int, int) -> np.ndarray
    """

    :param dirs: a list of strings of paths to masks of images. The list must be ordered by image first then masks.
    Example: ['image1_mask1.jpg', 'image1_mask2.jpg', 'image2_mask1.jpg', 'image2_mask2.jpg',...]
    :param height: height of outputted images. If height and width are both None, then the images are not resized.
    :param width: width of outputted images. If height and width are both None, then the images are not resized.
    :param batch_size: the size of the batch aka the number of images.
    :param semantic_masks_num_layers: The number of black and white masks we have for each image.
    :return: an numpy array representing the resized images. The shape is:
    (batch_size, height, width, semantic_masks_num_layers)
    """
    if height is None and width is None:
        shape = None
    else:
        if height is None or width is None:
            raise AssertionError('The height and width has to be both non None or both None.')
        shape = (height, width)
    images = [imread(d, shape=shape, bw=True) for d in dirs]
    np_images = np.array(images)
    if shape is None:
        shape = (np_images.shape[1], np_images.shape[2])
    # There will be batch_size * semantic_masks_num_layers images. We need to separate each batch.
    np_images = np.reshape(np_images, (batch_size, semantic_masks_num_layers, shape[0], shape[1]))
    np_images = np.transpose(np_images, (0, 2, 3, 1))
    return np_images


def get_all_image_paths_in_dir(directory):
    # type: (str) -> List[str]
    """

    :param directory: The parent directory of the images.
    :return: A sorted list of paths to images in the directory as well as all of its subdirectories.
    """
    _allowed_extensions = ['.jpg', '.png', '.JPG', '.PNG']
    if not directory.endswith('/'):
        raise AssertionError('The directory must end with a /')
    content_dirs = []
    for path, subdirs, files in os.walk(directory):
        for name in files:
            full_file_path = os.path.join(path, name)
            base, ext = os.path.splitext(full_file_path)
            if ext in _allowed_extensions:
                content_dirs.append(full_file_path)
    if len(content_dirs) == 0:
        raise AssertionError('There is no image in directory %s' % directory)
    content_dirs = sorted(content_dirs)
    return content_dirs


def get_global_step_from_save_dir(tf_save_path):
    # type: (str) -> int
    """
    A hacky way to get the global step for a tensorflow checkpoint.
    :param tf_save_path: the path to tensorflow checkpoint file.
    :return: the global step of that checkpoint file.
    """
    return int(tf_save_path[tf_save_path.rfind("-") + 1:])


def get_batch_paths(path_list, start_index, batch_size):
    # type: (List[str], int, int) -> List[str]
    """

    :param path_list: a list of paths to fetch the batch from.
    :param start_index: The start of the current batch.
    Note: the batch will automatically wrap around the path_list if start index is larger than the list length.
    :param batch_size: .
    :return: An array of string with length = batch_size containing paths to the current batch.
    """
    l = len(path_list)
    if not batch_size <= l:
        raise AssertionError('Given batch size must be smaller than the number of photos to load. Batch size : %d, '
                             'num photos: %d' % (batch_size, len(path_list)))
    start_index %= l
    if start_index + batch_size < l:
        return path_list[start_index:start_index + batch_size]
    else:
        end_index = (start_index + batch_size) % l
        return path_list[start_index:] + path_list[:end_index]


def get_batch_indices(dataset_len, start_index, batch_size):
    # type: (int, int, int) -> List[int]
    """

    :param dataset_len: the length of the dataset to fetch the batch from
    :param start_index: The start of the current batch.
    Note: the batch will automatically wrap around if start index is larger than the list length.
    :param batch_size: .
    :return: An array of int with length = batch_size containing indices to the current batch.
    """

    l = dataset_len
    assert batch_size < l
    start_index %= l
    if start_index + batch_size < l:
        return range(start_index, start_index + batch_size)
    else:
        end_index = (start_index + batch_size) % l
        return range(start_index, l) + range(0, end_index)


def get_np_array_num_elements(arr):
    # type: (np.ndarray) -> int
    return reduce(mul, arr.shape, 1)


def np_image_dot_mask(image, mask):
    # type: (np.ndarray, np.ndarray) -> np.ndarray
    """
    Dot a numpy-represented image with a numpy-represented mask and return the dotted result (image features takes
    priority over mask features, so the return is image_dot_mask1_rgb, image_dot_mask2_rgb, ...)
    :param image: Numpy represented image with shape (batch, height, width, num_colors)
    :param mask:  Numpy represented image with shape (batch, height, width, num_masks)
    :return: Numpy represented image with shape (batch, height, width, num_colors * num_masks)
    """
    image_layer_num = image.shape[3]
    mask_layer_num = mask.shape[3]

    ret = []
    for j in range(mask_layer_num):
        for i in range(image_layer_num):
            ret.append(np.multiply(image[..., i], mask[..., j]))

    ret = np.transpose(np.array(ret), axes=(1, 2, 3, 0))
    return ret


def get_file_name(file_path):
    # type: (Union[str,unicode]) -> Union[str,unicode]
    """
    Get the file name of the given path without its extension and parent directories.
    :param file_path: .
    :return: file name.
    """
    return basename(file_path).split('.')[0]

def download_if_not_exist(fileurl, file_save_path, helpmsg=''):
    # type: (str, str, str) -> bool
    """

    :param fileurl: The url to the file to be downloaded.
    :param file_save_path: Where the downloaded fill will be saved.
    :param helpmsg: Brief description of the file. It is used for displaying debugging information.
    :return: Whether the file download process has succeeded.
    """
    if not os.path.isfile(file_save_path):
        print('%s file does not exist. Attempting to download.' % helpmsg)
        try:
            file_save_dir = dirname(file_save_path)
            if not os.path.exists(file_save_dir):
                os.makedirs(file_save_dir)
            urllib.urlretrieve(fileurl, file_save_path)
            if not os.path.isfile(file_save_path):
                raise AssertionError
            print('Download finished!')
            return True
        except:
            print('Download failed.')
            return False


def read_resize_and_save_batch_images(dirs, height, width, save_path, bw=False, max_size_g=32):
    # type: (List[str], int, int, str, bool, int) -> np.ndarray
    """
    :param dirs: a list of strings of paths to images.
    :param height: height of outputted images. If height and width are both None, then the images are not resized.
    :param width: width of outputted images. If height and width are both None, then the images are not resized.
    :param save_path: The path to save the preprocessed images (as numpy array).
    :param max_size_g: the maximum size of the numpy array. If it exceeds this size, a warning will be displayed and
    nothing will be saved.
    :return: an numpy array representing the resized images. The shape is (num_image, height, width, 3). The numpy
    array is also saved at "save_dir".
    """
    if height is None or width is None:
        raise AssertionError('The height and width has to be both non None or both None.')
    shape = (height, width)
    estimated_size = height * width * (1 if bw else 3) * len(dirs) * 1 # 1 for the size of np.uint8
    print('Estimated numpy array size: %d' %estimated_size)
    max_bytes = max_size_g * (1024 ** 3)
    if estimated_size > max_bytes:
        raise AssertionError('The estimated size of the images (%fG) to be saved exceeds the max allowed size (%fG) '
                             'specified. ' %(float(estimated_size) / (1024**3), float(max_size_g)))

    images = np.array([imread(d, shape=shape, dtype=np.uint8, bw=bw) for d in dirs], np.uint8)
    print('Saving numpy array with size %.3f G' %(images.nbytes / float(1024 ** 3)))
    np.save(save_path, images)
    return images

def read_resize_and_save_all_imgs_in_dir(directory, height, width, save_dir, batch_size, bw=False,
                                         max_size_g=32):
    assert save_dir[-1] == '/'
    all_img_dirs = get_all_image_paths_in_dir(directory)
    num_images = len(all_img_dirs)
    image_per_file = max_size_g * (1024 ** 3) / (height * width * (1 if bw else 3) * 1)
    # Make sure that each file contains number of images that is divisible by batch size.
    num_images = num_images - num_images % batch_size
    image_per_file = image_per_file - image_per_file % batch_size

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    with open(save_dir + 'record.txt', 'w') as record_f:
        i = 0
        while i < num_images:
            if (i + image_per_file > num_images):
                end_i = num_images
                current_file_image_dirs = get_batch_paths(all_img_dirs, i, num_images - i)
            else:
                end_i = i + image_per_file
                current_file_image_dirs = get_batch_paths(all_img_dirs, i, image_per_file)

            current_images_save_path = save_dir + '%dx%d_%d_to_%d.npy' % (height,width,i,end_i)
            read_resize_and_save_batch_images(current_file_image_dirs, height, width, current_images_save_path,bw=bw,
                                              max_size_g=max_size_g)

            record_f.write('%s\t%d\t%d\t%d\t%d\t%d\n' %(current_images_save_path, batch_size,height,width,i,end_i))
            i = end_i
            print('%.3f%% Done.' %(float(end_i) / num_images * 100.0))
        assert i == num_images

def read_preprocessed_npy_record(save_dir):
    ret = []
    with open(save_dir + 'record.txt', 'r') as record_f:
        for line in record_f:
            line_split = line.split('\t')
            if len(line_split) == 6:
                for item in range(1,6):
                    line_split[item] = int(line_split[item])
                ret.append(line_split)
            elif len(line_split) == 0:
                pass
            else:
                raise AssertionError('Error in read_preprocessed_npy_record. Format of record.txt is wrong.')
    return ret

def find_corresponding_npy_from_record(record_list, start_index):
    num_images = record_list[-1][-1]
    start_index = start_index % num_images
    for record_i, record in enumerate(record_list):
        if start_index >= record[4] and start_index < record[5]:
            return record_i, start_index - record[4]
    raise AssertionError('Error in find_corresponding_npy_from_record.')

def np_total_variation(image_batch):
    batch_size, height, width, num_features = image_batch.shape
    top = image_batch[:,1:height,...]
    bottom = image_batch[:,0:height-1,...]

    left = image_batch[:,:,0:width-1,...]
    right = image_batch[:,:,1:width,...]

    vertical_diff = np.subtract(top,bottom)
    horizontal_diff = np.subtract(left,right)

    vertical_diff_num_elements = get_np_array_num_elements(vertical_diff)
    horizontal_diff_num_elements = get_np_array_num_elements(horizontal_diff)

    total_var = 2 * (np.linalg.norm(vertical_diff) / vertical_diff_num_elements +
                     np.linalg.norm(vertical_diff) / horizontal_diff_num_elements)
    return total_var

def rgb2gray(rgb):
    return np.dot(rgb[..., :3], [0.299, 0.587, 0.114])