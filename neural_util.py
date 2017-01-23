"""
This file contains functions for tensorflow neural networks in general.
"""
from operator import mul

import numpy as np
import tensorflow as tf
from typing import Union, Tuple, List, Dict

import vgg


def get_tensor_num_elements(tensor):
    # type: (tf.Tensor) -> int
    tensor_shape = map(lambda i: i.value, tensor.get_shape())
    return reduce(mul, tensor_shape, 1)


def concat_content_img_style_weight_mask_to_input(input_tensor, content_img_style_weight_mask):
    # type: (tf.Tensor, tf.Tensor) -> tf.Tensor
    """

    :param input_tensor: tensor with shape (batch_size, height, width, num_features)
    :param content_img_style_weight_mask: (batch_size, height, width, 1)
    :return: a tensor created by concatenating the input and the mask in their last dimension.
    """
    assert content_img_style_weight_mask is not None
    input_concatenated = tf.concat(3, (input_tensor, content_img_style_weight_mask))
    return input_concatenated


def spatial_batch_norm(input_layer, name='spatial_batch_norm', reuse=False):
    # type: (tf.Tensor, str, bool) -> tf.Tensor
    """
    Batch-normalizes the layer as in http://arxiv.org/abs/1502.03167
    This is important since it allows the different scales to talk to each other when they get joined.
    :param input_layer: tensor with shape (batch_size, height, width, num_features)
    :param name: name of the variable scope
    :param reuse: reuse variables if set to true. Otherwise create new ones.
    :return: a tensor with shape (batch_size, height, width, num_features) with the normalization applied.
    """
    with tf.variable_scope(name, reuse=reuse):
        mean, variance = tf.nn.moments(input_layer, [0, 1, 2])
        # NOTE: Tensorflow norm has some issues when the actual variance is near zero. I have to apply abs on it.
        variance = tf.abs(variance)
        variance_epsilon = 0.001
        num_channels = input_layer.get_shape().as_list()[3]
        scale = tf.get_variable('scale', [num_channels], tf.float32, tf.random_uniform_initializer())
        offset = tf.get_variable('offset', [num_channels], tf.float32, tf.constant_initializer())
        return_val = tf.nn.batch_normalization(input_layer, mean, variance, offset, scale, variance_epsilon, name=name)
        return return_val


def instance_norm(input_layer, name='instance_norm', reuse=False):
    # type: (tf.Tensor, str, bool) -> tf.Tensor
    """
    Instance-normalize the layer as in https://arxiv.org/abs/1607.08022
    :param input_layer: tensor with shape (batch_size, height, width, num_features)
    :param name: name of the variable scope
    :param reuse: reuse variables if set to true. Otherwise create new ones.
    :return: a tensor with shape (batch_size, height, width, num_features) with the normalization applied.
    """
    with tf.variable_scope(name, reuse=reuse):
        input_layers = tf.unpack(input_layer)
        return_val = []
        num_channels = input_layer.get_shape().as_list()[3]
        # The scale and offset variable is reused for all batches in this norm.
        scale = tf.get_variable('scale', [num_channels], tf.float32, tf.random_uniform_initializer())
        offset = tf.get_variable('offset', [num_channels], tf.float32, tf.constant_initializer())
        for l in input_layers:
            l = tf.expand_dims(l, 0)
            # NOTE: Tensorflow norm has some issues when the actual variance is near zero. I have to apply abs on it.
            mean, variance = tf.nn.moments(l, [0, 1, 2])
            variance = tf.abs(variance)
            variance_epsilon = 0.001
            return_val.append(
                tf.squeeze(tf.nn.batch_normalization(l, mean, variance, offset, scale, variance_epsilon, name=name),
                           [0]))
        return_val = tf.pack(return_val)
        return return_val


def conditional_instance_norm(input_layer, input_style_placeholder, name='conditional_instance_norm', reuse=False):
    # type: (tf.Tensor, tf.Tensor, str, bool) -> tf.Tensor
    """
    Instance-normalize the layer conditioned on the style as in https://arxiv.org/abs/1610.07629
    :param input_layer: tensor with shape (batch_size, height, width, num_features)
    :param input_style_placeholder: a one hot vector (1 x N tensor) with length N where N is the number of different
    style images.
    :param name: name of the variable scope
    :param reuse: reuse variables if set to true. Otherwise create new ones.
    :return: a tensor with shape (batch_size, height, width, num_features) with the normalization applied.
    """
    with tf.variable_scope(name, reuse=reuse):
        input_layers = tf.unpack(input_layer)
        return_val = []
        num_styles = input_style_placeholder.get_shape().as_list()[1]
        num_channels = input_layer.get_shape().as_list()[3]
        scale = tf.get_variable('scale', [num_styles, num_channels], tf.float32, tf.random_uniform_initializer())
        offset = tf.get_variable('offset', [num_styles, num_channels], tf.float32, tf.constant_initializer())
        scale_for_current_style = tf.matmul(input_style_placeholder, scale)
        offset_for_current_style = tf.matmul(input_style_placeholder, offset)
        for l in input_layers:
            l = tf.expand_dims(l, 0)
            # NOTE: Tensorflow norm has some issues when the actual variance is near zero. I have to apply abs on it.
            mean, variance = tf.nn.moments(l, [0, 1, 2])
            variance = tf.abs(variance)
            variance_epsilon = 0.001
            return_val.append(tf.squeeze(tf.nn.batch_normalization(
                l, mean, variance, offset_for_current_style, scale_for_current_style, variance_epsilon, name=name),
                [0]))
        return_val = tf.pack(return_val)
        return return_val


def gramian(layer):
    # type: (tf.Tensor) -> tf.Tensor
    """
    :param layer: tensor with shape (batch_size, height, width, num_features)
    :return: The gramian of the layer -- a tensor with dimension gramians of dimension (batches, channels, channels)
    """
    # Instead of iterating over #channels width by height matrices and computing similarity, we vectorize and compute
    # the entire gramian in a single matrix multiplication.
    _, height, width, number = map(lambda i: i.value, layer.get_shape())
    size = height * width * number
    layer_unpacked = tf.unpack(layer)
    grams = []
    for single_layer in layer_unpacked:
        feats = tf.reshape(single_layer, (-1, number))
        # Note: the normalization factor might be wrong. I've seen many different forms of normalization. The current
        # one works though.
        grams.append(tf.matmul(tf.transpose(feats), feats) / size)
    return tf.pack(grams)


def total_variation(image_batch):
    # type: (Union[tf.Tensor,tf.Variable]) -> tf.Tensor
    """
    :param image_batch: A 4D tensor of shape (batch_size, height, width, num_features)
    :return: The variation of the input represented as a scalar tensor.
    """
    batch_shape = image_batch.get_shape().as_list()
    batch_size = batch_shape[0]
    height = batch_shape[1]
    left = tf.slice(image_batch, [0, 0, 0, 0], [-1, height - 1, -1, -1])
    right = tf.slice(image_batch, [0, 1, 0, 0], [-1, -1, -1, -1])

    width = batch_shape[2]
    top = tf.slice(image_batch, [0, 0, 0, 0], [-1, -1, width - 1, -1])
    bottom = tf.slice(image_batch, [0, 0, 1, 0], [-1, -1, -1, -1])

    # left and right are 1 less wide than the original, top and bottom 1 less tall
    # In order to combine them, we take 1 off the height of left-right, and 1 off width of top-bottom
    vertical_diff = tf.slice(tf.sub(left, right), [0, 0, 0, 0], [-1, -1, width - 1, -1])
    horizontal_diff = tf.slice(tf.sub(top, bottom), [0, 0, 0, 0], [-1, height - 1, -1, -1])

    num_pixels_in_vertical_diff = get_tensor_num_elements(vertical_diff)
    num_pixels_in_horizontal_diff = get_tensor_num_elements(horizontal_diff)

    # Why there's a 2 here? I added it according to https://github.com/antlerros/tensorflow-fast-neuralstyle and
    # https://github.com/anishathalye/neural-style
    total_var = 2 * (tf.nn.l2_loss(horizontal_diff) / num_pixels_in_horizontal_diff + tf.nn.l2_loss(
        vertical_diff) / num_pixels_in_vertical_diff)

    return total_var


def precompute_image_features(img, layers, shape, vgg_data, mean_pixel, use_mrf, use_semantic_masks):
    # type: (np.ndarray, Union[Tuple[str], List[str]], Union[Tuple[int], List[int]], Dict[str, np.ndarray], List[float], bool, bool) -> Dict[str, np.ndarray]
    """
    Precompute the features of the image by passing it through the vgg network and storing the computed layers.
    :param img: the image of which the features would be precomputed. It must have shape (height, width, 3)
    :param layers: A list of string specifying which layers would we be returning. Check vgg.py for layer names.
    :param shape: shape of the image placeholder.
    :param vgg_data: The vgg network represented as a dictionary. It can be obtained by vgg.pre_read_net.
    :param mean_pixel: The mean pixel value for the vgg network. It can be obtained by vgg.read_net or just hardcoded.
    :param use_mrf: Whether we're using mrf loss. If true, it does not calculate and store the gram matrix.
    :param use_semantic_masks: Whether we're using semantic masks. If true, it does not calculate and store the gram
    matrix.
    :return: A dictionary containing the precomputed feature for each layer.
    """
    features_dict = {}
    g = tf.Graph()
    # Choose to use cpu here because we only need to compute this once and using cpu would provide us more memory
    # than the gpu and therefore allow us to process larger style images using the extra memory. This will not have
    # an effect on the training speed later since the gram matrix size is not related to the size of the image.
    with g.as_default(), g.device('/cpu:0'), tf.Session():
        image = tf.placeholder('float', shape=shape)
        net = vgg.pre_read_net(vgg_data, image)
        style_pre = np.array([vgg.preprocess(img, mean_pixel)])
        for layer in layers:
            if use_mrf or use_semantic_masks:
                features = net[layer].eval(feed_dict={image: style_pre})
                features_dict[layer] = features
            else:
                # Calculate and store gramian.
                features = net[layer].eval(feed_dict={image: style_pre})
                features = np.reshape(features, (-1, features.shape[3]))
                gram = np.matmul(features.T, features) / features.size
                features_dict[layer] = gram
    return features_dict
