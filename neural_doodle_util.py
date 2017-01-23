# This file contains functions related to neural doodle. That is we feed in two additional semantic mask layers to
# tell the model which part of the object is what. Using mrf loss and nearest neighbor matching, this technique can
# essentially "draw" according to the mask layers provided.

import tensorflow as tf
from typing import Tuple, Dict

import vgg
from general_util import *
from neural_util import gramian


def concatenate_mask_layer_tf(mask_layer, vgg_feature_layer):
    # type: (Union[np.ndarray,tf.Tensor], Union[np.ndarray,tf.Tensor]) -> tf.Tensor
    """

    :param mask_layer: mask with shape (num_batch, height, width, num_masks)
    :param vgg_feature_layer: The vgg feature layer with shape (num_batch, height, width, num_features)
    :return: The two layers concatenated in their last dimension.
    """
    return tf.concat(3, [mask_layer, vgg_feature_layer])

def vgg_layer_dot_mask(masks, vgg_layer):
    # type: (Union[np.ndarray,tf.Tensor], Union[np.ndarray,tf.Tensor]) -> tf.Tensor
    """

    :param masks:  mask with shape (num_batch, height, width, num_masks)
    :param vgg_layer: The vgg feature layer with shape (num_batch, height, width, num_features)
    :return: The two layers dotted for each mask and each feature. The returned tensor will have shape
    (num_batch, height, width, num_features * num_masks)
    """
    masks_dim_expanded = tf.expand_dims(masks, 4)
    vgg_layer_dim_expanded = tf.expand_dims(vgg_layer, 3)
    dot = tf.mul(masks_dim_expanded, vgg_layer_dim_expanded)

    batch_size, height, width, num_mask, num_features = map(lambda i: i.value, dot.get_shape())
    dot = tf.reshape(dot, [batch_size, height, width, num_mask * num_features])
    return dot

def masks_average_pool(masks):
    # type: (tf.Tensor) -> Dict[str,tf.Tensor]
    """
    This  function computes the average pool of a given mask to simulate the process of an image being passed through
    the vgg network and the boarders in the image become blurry after convolution layers and pooling layers. (It
    make less sense to apply a perfectly sharp mask to a blurry image.)
    :param masks: The mask to compute average pool over.
    :return: A dictionary with key = layer name and value = the average pooled masked at that layer.
    """
    layers = (
        'conv1_1', 'relu1_1', 'conv1_2', 'relu1_2', 'pool1',

        'conv2_1', 'relu2_1', 'conv2_2', 'relu2_2', 'pool2',

        'conv3_1', 'relu3_1', 'conv3_2', 'relu3_2', 'conv3_3',
        'relu3_3', 'conv3_4', 'relu3_4', 'pool3',

        'conv4_1', 'relu4_1', 'conv4_2', 'relu4_2', 'conv4_3',
        'relu4_3', 'conv4_4', 'relu4_4', 'pool4',

        'conv5_1', 'relu5_1', 'conv5_2', 'relu5_2', 'conv5_3',
        'relu5_3', 'conv5_4', 'relu5_4'
    )
    ret = {}
    current = masks
    for i, name in enumerate(layers):
        kind = name[:4]
        if kind == 'conv':
            current = tf.contrib.layers.avg_pool2d(current, kernel_size=[3,3], stride=[1,1],padding='SAME')
        elif kind == 'relu':
            pass
        elif kind == 'pool':
            current = tf.contrib.layers.avg_pool2d(current, kernel_size=[2,2], stride=[2,2],padding='SAME')
        ret[name] = current

    assert len(ret) == len(layers)
    return ret


def gramian_with_mask(layer, masks):
    # type: (Union[np.ndarray,tf.Tensor], tf.Tensor, bool) -> tf.Tensor
    """
    It computes the gramian of the given layer with given masks. Each mask will have its independent gramian for that
    layer.
    :param layer: The vgg feature layer with shape (num_batch, height, width, num_features)
    :param masks: mask with shape (num_batch, height, width, num_masks)
    :return: a tensor with dimension gramians of dimension (num_masks, num_batch, num_features, num_features)
    """
    mask_list = tf.unpack(masks, axis=3) # A list of masks with dimension (1,height, width)

    gram_list = []

    for mask in mask_list:
        mask = tf.expand_dims(mask, dim=3)
        layer_dotted_with_mask = vgg_layer_dot_mask(mask, layer)
        layer_dotted_with_mask_gram = gramian(layer_dotted_with_mask)
        # Normalization is very importantant here. Because otherwise there is no way to compare two gram matrices
        # with different masks applied to them.
        layer_dotted_with_mask_gram_normalized = layer_dotted_with_mask_gram / (tf.reduce_mean(mask) + 0.000001) # Avoid division by zero.
        gram_list.append(layer_dotted_with_mask_gram_normalized)
    grams = tf.pack(gram_list)

    if isinstance(layer, np.ndarray):
        _, _, _, num_features = layer.shape
    else:
        _,_,_,num_features  =  map(lambda i: i.value, layer.get_shape())

    number_colors,_, gram_height, gram_width,  = map(lambda i: i.value, grams.get_shape())

    assert num_features == gram_height
    assert num_features == gram_width
    assert number_colors == len(mask_list)

    return grams


def construct_masks_and_features(style_semantic_masks, styles, style_features, batch_size, height, width, semantic_masks_num_layers, style_layer_names, net_layer_sizes, semantic_masks_weight, vgg_data, mean_pixel, mask_resize_as_feature, use_mrf, average_pool = False):
    # type: (List[np.ndarray], List[np.ndarray], List[Dict[str,np.ndarray]], int, int, int, int, List[str], Dict[str,Union[List[int],Tuple[int]]], float, Dict[str,np.ndarray], Union[List[float],Tuple[float]], bool, bool, bool) -> Tuple[Dict[str,np.ndarray],List[Dict[str,np.ndarray]],tf.Tensor,List[tf.Tensor]]
    """
    This is a wrapper for computing the features for the style image as well as constructing the placeholders for
    the semantic masks.
    :param mask_resize_as_feature: If true, resize the mask and use the resized mask as additional feature besides the
    vgg network layers. If false, pass the masks (must have exactly 3 masks) into the vgg network and use the outputted
    layers as additional features. The merits of setting this to True is: it supports using more than 3 masks; it's
    meaning is more understandable than passing a mask through an image recognition network. The merits of setting it
    to False is: The mean/std for each layer would be the same as any other vgg layers, so it would be better for mrf
    loss (otherwise, if we use resize it would be treating the masks with different level of importance when doing nn
    matching since each vgg layer has different magnetudes but the mask layers all have the same magnetude across all
    layers.)
    TODO: This might be too complicated for a single function...
    """
    output_semantic_mask_features = {}

    output_semantic_mask_placeholder = tf.placeholder(tf.float32, [batch_size, height, width,
                                                        semantic_masks_num_layers],
                                           name='output_semantic_mask_placeholder')
    if mask_resize_as_feature:
        if average_pool:
            # According to http://dmitryulyanov.github.io/feed-forward-neural-doodle/,
            # resizing might not be sufficient. "Use 3x3 mean filter for mask when the data goes through
            # convolutions and average pooling along with pooling layers."
            output_semantic_masks_for_each_layer = masks_average_pool(output_semantic_mask_placeholder)
        for layer in style_layer_names:
            if average_pool:
                output_semantic_mask_feature = output_semantic_masks_for_each_layer[layer]
            else:
                output_semantic_mask_feature = tf.image.resize_images(output_semantic_mask_placeholder, (
                    net_layer_sizes[layer][1], net_layer_sizes[layer][2]))

            output_semantic_mask_shape = map(lambda i: i.value, output_semantic_mask_feature.get_shape())
            if (net_layer_sizes[layer][1] != output_semantic_mask_shape[1]) or (
                net_layer_sizes[layer][1] != output_semantic_mask_shape[1]):
                raise AssertionError("Semantic masks shape not equal. Net layer %s size is: %s, "
                                     "semantic mask size is: %s" % (layer, str(net_layer_sizes[layer]),
                                                                    str(output_semantic_mask_shape)))

            # Must be normalized (/ 255), otherwise the style loss just gets out of control.
            output_semantic_mask_features[layer] = output_semantic_mask_feature * semantic_masks_weight / 255.0
    else:
        if semantic_masks_num_layers != 3:
            raise AssertionError('The semantic_masks_num_layers must be 3 (RGB) if mask_resize_as_feature is turned '
                                 'off. Otherwise it is not possible to treat it as an image and pass it through the '
                                 'vgg network.')
        content_semantic_mask_pre = vgg.preprocess(output_semantic_mask_placeholder, mean_pixel)
        semantic_mask_net, _ = vgg.pre_read_net(vgg_data, content_semantic_mask_pre)
        for layer in style_layer_names:
            output_semantic_mask_feature = semantic_mask_net[layer] * semantic_masks_weight
            output_semantic_mask_features[layer] = output_semantic_mask_feature

    style_semantic_masks_pres = []
    style_semantic_masks_placeholders = []
    style_semantic_masks_for_each_layer = []
    for i in range(len(styles)):
        current_style_shape = styles[i].shape  # Shape has format : height width rgb
        style_semantic_masks_placeholders.append(
            tf.placeholder('float',
                           shape=(1, current_style_shape[0], current_style_shape[1], semantic_masks_num_layers),
                           name='style_mask_%d' % i))

        if not mask_resize_as_feature:
            style_semantic_masks_pres.append(
                np.array([vgg.preprocess(style_semantic_masks[i], mean_pixel)]))
            semantic_mask_net, _ = vgg.pre_read_net(vgg_data, style_semantic_masks_pres[-1])
        else:
            style_semantic_masks_for_each_layer.append(
                masks_average_pool(style_semantic_masks_placeholders[-1]))

        for layer in style_layer_names:
            if mask_resize_as_feature:
                features = tf.div(style_semantic_masks_for_each_layer[-1][layer], 255.0)
            else:
                features = semantic_mask_net[layer]
            features = tf.mul(features, semantic_masks_weight)
            if use_mrf:
                # TODO: maybe I should change the magnetude of the mask layers as i'm concatenating it with the vgg feature layers so that they're on the same magnitude.
                # I tried that but didn't find the setting that make it work yet.
                style_features[i][layer] = concatenate_mask_layer_tf(features, style_features[i][layer])
            else:
                gram = gramian_with_mask(style_features[i][layer], features)
                style_features[i][layer] = gram

    return output_semantic_mask_features, style_features, output_semantic_mask_placeholder, style_semantic_masks_placeholders