"""
This file implements the johnson network for feed-forward image generation network. It comes from the paper
"Perceptual losses for real-time style transfer and super-resolution".
The code mainly came from https://github.com/lengstrom/fast-style-transfer/blob/master/src/transform.py. Some functions
were moved to conv_util.py.
"""
from typing import List

from conv_util import *


def net(image, mirror_padding = True, one_hot_style_vector = None, reuse = False):
    # type: (tf.Tensor, bool, Union[None,tf.Tensor], bool) -> tf.Tensor
    """
    The network is a generator network that takes an image, tries to apply some nonlinear transformation, and outputs
    the result with the same shape as the input.
    :param image: tensor with shape (batch_size, height, width, num_features)
    :param mirror_padding: If true it uses mirror padding. Otherwise it uses zero padding. Note that there's a bug
    here if I use mirror padding in the conv-transpose layers, I will get errors during gradient computation.
    :param reuse: If true, it tries to reuse the variable previously defined by the same network.
    :return: tensor with shape (batch_size, height, width, num_features)
    """

    # NOTE: There might be a small change in the dimension of the input vs. output if the size cannot be divided evenly
    # by 4.
    # with tf.variable_scope('johnson', reuse=reuse):
    #     conv1 = conv_layer(image, 32, 9, 1, mirror_padding = mirror_padding, name ='conv1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     conv2 = conv_layer(conv1, 64, 3, 2, mirror_padding = mirror_padding, name ='conv2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     conv3 = conv_layer(conv2, 128, 3, 2, mirror_padding = mirror_padding, name ='conv3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     resid1 = residual_block(conv3, 3, mirror_padding = mirror_padding, name ='resid1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     resid2 = residual_block(resid1, 3, mirror_padding = mirror_padding, name ='resid2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     resid3 = residual_block(resid2, 3, mirror_padding = mirror_padding, name ='resid3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     resid4 = residual_block(resid3, 3, mirror_padding = mirror_padding, name ='resid4', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     resid5 = residual_block(resid4, 3, mirror_padding = mirror_padding, name ='resid5', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     conv_t1 = conv_tranpose_layer(resid5, 64, 3, 2, mirror_padding = False, name ='conv_t1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     conv_t2 = conv_tranpose_layer(conv_t1, 32, 3, 2, mirror_padding = False, name ='conv_t2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     conv_t3 = conv_layer(conv_t2, 3, 9, 1, elu=False, mirror_padding = mirror_padding, name ='conv_t3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    #     preds = tf.nn.tanh(conv_t3) * 150 + 255./2
    #
    #     # Do sanity check.
    #     image_shape = image.get_shape().as_list()
    #     final_shape = preds.get_shape().as_list()
    #     if not (image_shape[0] == final_shape[0] and image_shape[1] == final_shape[1] and image_shape[2] == final_shape[2]):
    #         print('image_shape and final_shape are different. image_shape = %s and final_shape = %s' % (
    #         str(image_shape), str(final_shape)))
    #         raise AssertionError
    #     return preds
    conv1 = conv_layer(image, 32, 9, 1, mirror_padding = mirror_padding, name ='conv1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    conv2 = conv_layer(conv1, 64, 3, 2, mirror_padding = mirror_padding, name ='conv2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    conv3 = conv_layer(conv2, 128, 3, 2, mirror_padding = mirror_padding, name ='conv3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    resid1 = residual_block(conv3, 3, mirror_padding = mirror_padding, name ='resid1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    resid2 = residual_block(resid1, 3, mirror_padding = mirror_padding, name ='resid2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    resid3 = residual_block(resid2, 3, mirror_padding = mirror_padding, name ='resid3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    resid4 = residual_block(resid3, 3, mirror_padding = mirror_padding, name ='resid4', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    resid5 = residual_block(resid4, 3, mirror_padding = mirror_padding, name ='resid5', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    conv_t1 = conv_tranpose_layer(resid5, 64, 3, 2, mirror_padding = False, name ='conv_t1', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    conv_t2 = conv_tranpose_layer(conv_t1, 32, 3, 2, mirror_padding = False, name ='conv_t2', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    conv_t3 = conv_layer(conv_t2, 3, 9, 1, elu=False, mirror_padding = mirror_padding, name ='conv_t3', one_hot_style_vector = one_hot_style_vector, reuse = reuse)
    preds = tf.nn.tanh(conv_t3) * 150 + 255./2

    # Do sanity check.
    image_shape = image.get_shape().as_list()
    final_shape = preds.get_shape().as_list()
    if not (image_shape[0] == final_shape[0] and image_shape[1] == final_shape[1] and image_shape[2] == final_shape[2]):
        print('image_shape and final_shape are different. image_shape = %s and final_shape = %s' % (
        str(image_shape), str(final_shape)))
        raise AssertionError
    return preds

def get_johnson_scale_offset_var():
    # type: () -> List[tf.Variable]
    """

    :return: The list of all scale and shift variables used by the instance normalization in the johnson network. Must
    be called after calling the "net()" function.
    """
    all_var = tf.all_variables()
    scale_offset_variables = []
    for var in all_var:
        if 'scale' in var.name or 'shift' in var.name:
            scale_offset_variables.append(var)
    if len(scale_offset_variables) !=  3 * 2 + 5 * 2 * 2 + 3 * 2:
        print('The number of scale offset variables is wrong. ')
        raise AssertionError
    return scale_offset_variables


def get_net_all_variables():
    if '0.12.0' in tf.__version__:
        return tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='johnson')
    else:
        return tf.get_collection(tf.GraphKeys.VARIABLES, scope='johnson')