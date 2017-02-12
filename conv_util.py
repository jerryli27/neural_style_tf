"""
This file contains utility functions for creating a convolution neural network.
"""

import math

import tensorflow as tf
from typing import Union, Callable

WEIGHTS_INIT_STDEV = .1



def conv_layer(net, num_filters, filter_size, strides, with_bias = True, elu=True, mirror_padding=True, one_hot_style_vector=None,
               norm='instance_norm', dilation = 1, name='', reuse=False):
    # type: (tf.Tensor, int, int, int, bool, bool, bool, Union[None,tf.Tensor], str, int, str, bool) -> tf.Tensor
    """
    This function generates a convolution layer given the input layer and the output shape info.
    :param net: tensor with shape (batch_size, height, width, num_input_features)
    :param num_filters: Number of output filters/features/channels.
    :param filter_size: The size of each filter.
    :param strides: The stride size of the CNN.
    :param with_bias: If true, add bias to conv layers. The default is not having bias in conv and deconv layers.
    :param elu: whether we apply elu after convolution and normalization.
    :param mirror_padding: If true it uses mirror padding. Otherwise it uses zero padding.
    :param one_hot_style_vector: The 1d tensor representing which style is currently being trained. It is used with
    instance norm.
    :param norm: The normalization applied after convolution. If left blank then no normalization is done.
    :param name: The name for the conv layer.
    :param reuse: If true, it tries to reuse the variable previously defined by the same network with the same name.
    :return: A tensor with shape (batch_size, height / strides, width / strides, num_filters). The height and width of
    the output may change slightly if it cannot be divided evenly by the "strides".
    """
    with tf.variable_scope('conv_layer' + name, reuse=reuse):
        weights_init, bias_init = conv_init_vars(net, num_filters, filter_size, with_bias=with_bias, name=name, reuse=reuse)
        if mirror_padding:
            net = conv2d_mirror_padding(net, weights_init, bias_init, filter_size, stride=strides, dilation=dilation)
        else:
            if dilation == 1:
                strides_shape = [1, strides, strides, 1]
                net = tf.nn.conv2d(net, weights_init, strides_shape, padding='SAME')
                if bias_init:
                    net = tf.nn.bias_add(net, bias_init)
            else:
                net = tf.nn.atrous_conv2d(net, weights_init, dilation, padding='SAME')
                if bias_init:
                    net = tf.nn.bias_add(net, bias_init)
        if norm == 'instance_norm':
            net = instance_norm(net, name=name, one_hot_style_vector=one_hot_style_vector, reuse=reuse)
        elif norm == 'batch_norm':
            net = batch_norm(net, name=name, reuse=reuse)
        elif norm == '' or norm == None:
            pass
        else:
            raise NotImplementedError('Please specify a valid normalization method: "instance_norm", "batch_norm", '
                                      'or simply leave it blank')
        if elu:
            # In some papers relu or leaky relu were also used instead of elu. There shouldn't be a big difference.
            net = tf.nn.elu(net)

        return net



def conv_tranpose_layer(net, num_filters, filter_size, strides, with_bias = True, elu=True, mirror_padding=True,
                        one_hot_style_vector=None, norm='instance_norm', name='', reuse=False):
    # type: (tf.Tensor, int, int, int, bool, bool, bool, Union[None,tf.Tensor], str, str, bool) -> tf.Tensor
    """
    Same as the conv_layer function except that it is now doing convolution tranpose (aka deconvolution). For detailed
    documentation for each variable, please refer to that function.
    """
    with tf.variable_scope('conv_tranpose_layer' + name, reuse=reuse):
        weights_init, bias_init = conv_init_vars(net, num_filters, filter_size, with_bias=with_bias, transpose=True, name=name, reuse=reuse)

        batch_size, rows, cols, in_channels = [i.value for i in net.get_shape()]
        new_rows, new_cols = int(rows * strides), int(cols * strides)
        new_shape = [batch_size, new_rows, new_cols, num_filters]
        tf_shape = tf.pack(new_shape)
        strides_shape = [1, strides, strides, 1]

        if mirror_padding:
            net = conv2d_transpose_mirror_padding(net, weights_init, bias_init, tf_shape, filter_size, stride=strides)
        else:
            net = tf.nn.conv2d_transpose(net, weights_init, tf_shape, strides_shape, padding='SAME')
            if bias_init:
                net = tf.nn.bias_add(net, bias_init)

        if norm == 'instance_norm':
            net = instance_norm(net, name=name, one_hot_style_vector=one_hot_style_vector, reuse=reuse)
        elif norm == 'batch_norm':
            net = batch_norm(net, name=name, reuse=reuse)
        elif norm == '' or norm == None:
            pass
        else:
            raise NotImplementedError('Please specify a valid normalization method: "instance_norm", "batch_norm", '
                                      'or simply leave it blank')
        if elu:
            net = tf.nn.elu(net)
        return net


def residual_block(net, filter_size=3, mirror_padding=True, name='', one_hot_style_vector=None, reuse=False):
    # type: (tf.Tensor, int, bool, str, Union[None,tf.Tensor], bool) -> tf.Tensor
    """
    For meaning of each variable, please refer to the documentation in the "conv_layer" function. They're the same.
    For the purpose of this function, please refer to the paper
    "Texture Networks: Feed-forward Synthesis of Textures and Stylized Images"
    """
    tmp = conv_layer(net, 128, filter_size, 1, mirror_padding=mirror_padding, name=name + '_first',
                     one_hot_style_vector=one_hot_style_vector, reuse=reuse)
    return tf.add(net,
                  conv_layer(tmp, 128, filter_size, 1, mirror_padding=mirror_padding, name=name + '_second', elu=False,
                             one_hot_style_vector=one_hot_style_vector, reuse=reuse))


def instance_norm(net, name='', one_hot_style_vector=None, reuse=False):
    # type: (tf.Tensor, str, Union[None,tf.Tensor], bool) -> tf.Tensor
    """
    For meaning of each variable, please refer to the documentation in the "conv_layer" function. They're the same.
    For the purpose of this function, please refer to the paper
    "Instance Normalization - The Missing Ingredient for Fast Stylization"
    """
    with tf.variable_scope('instance_norm' + name, reuse=reuse):
        batch, rows, cols, channels = [i.value for i in net.get_shape()]
        if one_hot_style_vector is None:
            var_shape = [channels]
        else:
            num_styles = one_hot_style_vector.get_shape().as_list()[1]
            var_shape = [num_styles, channels]
        mu, sigma_sq = tf.nn.moments(net, [1, 2], keep_dims=True)
        # Try applying an abs on the sigma_sq. in theory it should always be positive but in practice due to inaccuracy
        # in float calculation, it may be negative when the actual sigma is very small, which causes the output to be
        # NaN sometimes. It's probably a bug on tensorflow's side.
        sigma_sq = tf.abs(sigma_sq)
        shift_init = tf.zeros(var_shape)
        shift = tf.get_variable('shift', initializer=shift_init)
        scale_init = tf.ones(var_shape)
        scale = tf.get_variable('scale', initializer=scale_init)
        if one_hot_style_vector is not None:
            shift = tf.matmul(one_hot_style_vector, shift)
            scale = tf.matmul(one_hot_style_vector, scale)
        epsilon = 1e-3
        normalized = (net - mu) / (sigma_sq + epsilon) ** (.5)
        return scale * normalized + shift


def batch_norm(input_layer, name='', reuse=False):
    # type: (tf.Tensor, str, bool) -> tf.Tensor
    """
    For meaning of each variable, please refer to the documentation in the "conv_layer" function. They're the same.
    Batch-normalizes the layer as in http://arxiv.org/abs/1502.03167
    This is important since it allows the different scales to talk to each other when they get joined.
    """
    with tf.variable_scope('spatial_batch_norm' + name, reuse=reuse):
        mean, variance = tf.nn.moments(input_layer, [0, 1, 2])
        # NOTE: Tensorflow norm has some issues when the actual variance is near zero. I have to apply abs on it.
        variance = tf.abs(variance)
        variance_epsilon = 0.001
        num_channels = input_layer.get_shape().as_list()[3]
        scale = tf.get_variable('scale', [num_channels], tf.float32, tf.random_uniform_initializer())
        offset = tf.get_variable('offset', [num_channels], tf.float32, tf.constant_initializer())
        return_val = tf.nn.batch_normalization(input_layer, mean, variance, offset, scale, variance_epsilon, name=name)
        return return_val


def conv_init_vars(net, out_channels, filter_size, with_bias = True, transpose=False, name='', reuse=False):
    # type: (tf.Tensor, int, int, bool, bool, str, bool) -> Tuple[tf.Tensor,Union[tf.Tensor,None]]
    """
    For meaning of each variable, please refer to the documentation in the "conv_layer" function. They're the same.
    "out_channels" is just "num_filters".
    This function initializes variables for the convolution networks.
    """
    with tf.variable_scope('conv_init_vars' + name, reuse=reuse):
        _, rows, cols, in_channels = [i.value for i in net.get_shape()]
        if not transpose:
            weights_shape = [filter_size, filter_size, in_channels, out_channels]
        else:
            weights_shape = [filter_size, filter_size, out_channels, in_channels]
        weights_initializer = tf.truncated_normal_initializer(stddev=WEIGHTS_INIT_STDEV)

        weights_init = tf.get_variable('weights_init', shape=weights_shape, dtype=tf.float32,
                                       initializer=weights_initializer)
        if with_bias:
            bias_shape = [out_channels]
            bias_init =  tf.get_variable('bias_init', shape=bias_shape, dtype=tf.float32,
                                       initializer=weights_initializer)
        else:
            bias_init = None

        assert (with_bias is False or bias_init is not None)
        return weights_init, bias_init


def fully_connected(net, out_channels, activation_fn=None, name='', reuse=False):
    # type: (tf.Tensor, int, Union[None,Callable[[tf.Tensor], tf.Tensor]], str, bool) -> tf.Tensor
    with tf.variable_scope('fully_connected_' + name, reuse=reuse):
        # Fully connected layer
        # Reshape conv2 output to fit fully connected layer input

        batch_size, rows, cols, in_channels = [i.value for i in net.get_shape()]

        weights_shape = [rows * cols * in_channels, out_channels]
        weights_init_stdv = math.sqrt(1.0 / (rows * cols * in_channels))
        weights_initializer = tf.truncated_normal_initializer(stddev=weights_init_stdv)
        weights_init = tf.get_variable('weights_init', shape=weights_shape, dtype=tf.float32,
                                       initializer=weights_initializer)

        bias_shape = [out_channels]
        bias_init = tf.get_variable('bias_init', shape=bias_shape, dtype=tf.float32,
                                    initializer=tf.constant_initializer())

        fc1 = tf.reshape(net, [-1, rows * cols * in_channels])
        fc1 = tf.nn.bias_add(tf.matmul(fc1, weights_init), bias_init)

        if activation_fn is not None:
            fc1 = activation_fn(fc1)
        return fc1


def conv2d_mirror_padding(input_layer, w, b, kernel_size, stride=1, dilation=1):
    # type: (tf.Tensor, Union[tf.Tensor,tf.Variable], Union[tf.Tensor,tf.Variable], int, int) -> tf.Tensor
    """
    Apply mirror padding before doing a convolution on the input layer.
    :param input_layer: Input tensor.
    :param w: Weight. Either tensorflow constant or variable.
    :param b: Bias. Either tensorflow constant or variable.
    :param stride: Stride of the conv.
    :return: the 2d convolution tensor with mirror padding.
    """
    # N_out = N_in / stride + 2N_pad - N_kernel_size + 1. We have N_out and N_in fixed (treat as 0) and solve for N_pad.
    n_pad = (kernel_size - 1) / 2
    padding = [[0, 0], [n_pad, n_pad], [n_pad, n_pad], [0, 0]]
    mirror_padded_input_layer = tf.pad(input_layer, padding, "REFLECT", name='mirror_padding')
    if dilation != 1:
        # Maybe there will be problems in the padding... Not sure.
        conv_output = tf.nn.atrous_conv2d(mirror_padded_input_layer, w, rate=dilation, padding='VALID')
    else:
        conv_output = tf.nn.conv2d(mirror_padded_input_layer, w, strides=[1, stride, stride, 1], padding='VALID')
    if b is not None:
        return tf.nn.bias_add(conv_output, b)
    else:
        return conv_output


def conv2d_transpose_mirror_padding(input_layer, w, b, output_shape, kernel_size, stride=1):
    # type: (tf.Tensor, Union[tf.Tensor,tf.Variable], Union[tf.Tensor,tf.Variable, None], int, int) -> tf.Tensor
    """
    Apply mirror padding before doing a transposed convolution on the input layer.
    :param input_layer: Input tensor.
    :param w: Weight. Either tensorflow constant or variable.
    :param b: Bias. Either tensorflow constant or variable.
    :param stride: Stride of the conv.
    :return: the 2d convolution tensor with mirror padding.
    """
    # N_out = N_in / stride + 2N_pad - N_kernel_size + 1. We have N_out and N_in fixed (treat as 0) and solve for N_pad.
    n_pad = (kernel_size - 1) / 2
    padding = [[0, 0], [n_pad, n_pad], [n_pad, n_pad], [0, 0]]
    mirror_padded_input_layer = tf.pad(input_layer, padding, "REFLECT", name='mirror_padding')
    conv_output = tf.nn.conv2d_transpose(mirror_padded_input_layer, w, output_shape, strides=[1, stride, stride, 1],
                                         padding='VALID')
    if b is not None:
        return tf.nn.bias_add(conv_output, b)
    else:
        return conv_output
