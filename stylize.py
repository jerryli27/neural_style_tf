"""
This file contains one function that implemented the papers:
"A Neural Algorithm of Artistic Style" (https://arxiv.org/abs/1508.06576),
"Combining Markov Random Fields and Convolutional Neural Networks for Image Synthesis" (arxiv.org/abs/1601.04589),
"Instance Normalization - The Missing Ingredient for Fast Stylization" (https://arxiv.org/abs/1607.08022),
"Semantic Style Transfer and Turning Two-Bit Doodles into Fine Artworks" (https://arxiv.org/abs/1603.01768).

In addition, it contains one more functionality to control the degree of stylization of the content image by using a
weighted mask for the content image ("content_img_style_weight_mask" in the code)
The code skeleton was borrowed from https://github.com/anishathalye/neural-style.
"""

from sys import stderr

import numpy as np
import tensorflow as tf
from typing import Union, Tuple, List, Iterable

import neural_doodle_util
import neural_util
import vgg
from general_util import get_np_array_num_elements
from mrf_util import mrf_loss

try:
    reduce
except NameError:
    from functools import reduce

CONTENT_LAYER = 'relu4_2'
STYLE_LAYERS = ('relu1_1', 'relu2_1', 'relu3_1', 'relu4_1', 'relu5_1')  # This is used for texture generation (without content)
STYLE_LAYERS_WITH_CONTENT = ('relu1_1', 'relu2_1', 'relu3_1', 'relu4_1', 'relu5_1')
STYLE_LAYERS_MRF = ('relu3_1', 'relu4_1')  # According to https://arxiv.org/abs/1601.04589.


def stylize(network, content, styles, shape, iterations, content_weight=5.0, style_weight=100.0, tv_weight=100.0,
            style_blend_weights=None, learning_rate=10.0, initial=None, use_mrf=False, use_semantic_masks=False,
            mask_resize_as_feature=True, output_semantic_mask=None, style_semantic_masks=None,
            semantic_masks_weight=1.0, print_iterations=None, checkpoint_iterations=None,
            semantic_masks_num_layers=4, content_img_style_weight_mask=None):
    # type: (str, Union[None,np.ndarray], List[np.ndarray], Tuple[int,int,int,int], int, float, float, float, Union[None,List[float]], float, Union[None,np.ndarray], bool, bool, bool, Union[None,np.ndarray], Union[None,List[np.ndarray], float, Union[None,int], Union[None,int], Union[None,int], Union[None,np.ndarray], Union[None,int]]) -> Iterable[Tuple[Union[None,int],np.ndarray]]
    """
    Stylize images.
    :param network: Path to pretrained vgg19 network. It can be downloaded at
    http://www.vlfeat.org/matconvnet/models/imagenet-vgg-verydeep-19.mat
    :param content: The content image. If left blank, it will enter texture generation mode (style synthesis without
    context loss).
    :param styles: A list of style images as numpy arrays.
    :param shape: The shape of the output image. It should be with format (1, height, width, 3)
    :param iterations: The number of iterations to run.
    :param content_weight: The weight for content loss. The larger the weight, the more the output will look like
    the content image.
    :param style_weight: The weight for style loss. The larger the weight, the more the output will have a style that
    looks like the style images.
    :param tv_weight: The weight for total-variation loss. The larger the weight, the smoother the output will be.
    :param style_blend_weights: If inputting multiple style images, this controls the balance between their styles.
    If left as None, it will treat all style images as equal.
    :param learning_rate: As name suggests.
    :param initial: The initial starting point for the output. If left blank, the initial would just be noise.
    :param use_mrf: Whether we use markov-random-field loss instead of gramian loss. mrf_util.py contains more info.
    :param use_semantic_masks: Whether we use semantic masks as additional semantic information. Please check the paper
    "Semantic Style Transfer and Turning Two-Bit Doodles into Fine Artworks" for more information.
    :param mask_resize_as_feature: If true, resize the mask and use the resized mask as additional feature besides the
    vgg network layers. If false, pass the masks (must have exactly 3 masks) into the vgg network and use the outputted
    layers as additional features.
    :param output_semantic_mask: The semantic masks you would like to apply to the outputted image.The mask should have
    shape (batch_size, height, width, semantic_masks_num_layers) Unlike the neural doodle paper, here I use one
    black-and-white image for each semantic mask (the paper had semantic masks represented as rgb images, limiting the
    semantic channels to 3).
    :param style_semantic_masks: A list of semantic masks you would like to apply to each style image. The mask should
    have shape (batch_size, height, width, semantic_masks_num_layers)
    :param semantic_masks_weight: How heavily you'd like to weight the semantic masks as compared to other sources of
    semantic information obtained through passing the image through vgg network. Default is 1.0.
    :param print_iterations: Print loss information every n iterations.
    :param checkpoint_iterations: Save a checkpoint as well as the best image so far every n iterations.
    :param semantic_masks_num_layers: The number of semantic masks each image have.
    :param content_img_style_weight_mask: One black-and-white mask specifying how much we should "stylize" each pixel
    in the outputted image. The areas where the mask has higher value would be stylized more than other areas. A
    completely white mask would mean that we stylize the output image just as before, while a completely dark mask
    would mean that we do not stylize the output image at all, so it should look pretty much the same as content image.
    If you do not wish to use this feature, just leave it as None.
    :return: a tuple where the first item is either the current iteration or None, indicating it has finished training.
    The second item is the image that has the lowest loss so far. The tuples are yielded every 'checkpoint_iterations'
    iterations as well as the last iteration.
    :rtype: iterator[tuple[int|None,image]]
    """
    global STYLE_LAYERS
    if content is not None:
        STYLE_LAYERS = STYLE_LAYERS_WITH_CONTENT
    if use_mrf:
        STYLE_LAYERS = STYLE_LAYERS_MRF  # Easiest way to be compatible with no-mrf versions.
    if use_semantic_masks:
        assert semantic_masks_weight is not None
        assert output_semantic_mask is not None
        assert style_semantic_masks is not None
    if content_img_style_weight_mask is not None:
        if shape[1] != content_img_style_weight_mask.shape[1] or shape[2] != content_img_style_weight_mask.shape[2]:
            raise AssertionError("The shape of style_weight_mask is incorrect. It must have the same height and width "
                                 "as the output image. The output image has shape: %s and the style weight mask has "
                                 "shape: %s" % (str(shape), str(content_img_style_weight_mask.shape)))
        if content_img_style_weight_mask.dtype != np.float32:
            raise AssertionError('The dtype of style_weight_mask must be float32. it is now %s' % str(
                content_img_style_weight_mask.dtype))

    # Append a (1,) in front of the shapes of the style images. So the style_shapes contains (1, height, width, 3).
    # 3 corresponds to rgb.
    style_shapes = [(1,) + style.shape for style in styles]
    if style_blend_weights is None:
        style_blend_weights = [1.0 / len(styles) for _ in styles]
    content_features = {}
    style_features = [{} for _ in styles]
    output_semantic_mask_features = {}

    # The default behavior of tensorflow was to allocate all gpu memory. Here it is set to only use as much gpu memory
    # as it needs.
    with tf.Graph().as_default(), tf.Session(
            config=tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True))) as sess:
        vgg_data, mean_pixel = vgg.read_net(network)

        # Compute content features in feed-forward mode
        content_image = tf.placeholder('float', shape=shape, name='content_image')
        net = vgg.pre_read_net(vgg_data, content_image)
        content_features[CONTENT_LAYER] = net[CONTENT_LAYER]
        net_layer_sizes = vgg.get_net_layer_sizes(net)

        if content is not None:
            content_pre = np.array([vgg.preprocess(content, mean_pixel)])

        # Compute style features in feed-forward mode.
        if content_img_style_weight_mask is not None:
            style_weight_mask_layer_dict = neural_doodle_util.masks_average_pool(content_img_style_weight_mask)

        for i in range(len(styles)):
            # Using precompute_image_features, which calculates on cpu and thus allow larger images.
            style_features[i] = neural_util.precompute_image_features(styles[i], STYLE_LAYERS, style_shapes[i],
                                                                      vgg_data, mean_pixel, use_mrf, use_semantic_masks)

        if use_semantic_masks:
            output_semantic_mask_features, style_features, content_semantic_mask, style_semantic_masks_images = neural_doodle_util.construct_masks_and_features(
                style_semantic_masks, styles, style_features, shape[0], shape[1], shape[2], semantic_masks_num_layers,
                STYLE_LAYERS, net_layer_sizes, semantic_masks_weight, vgg_data, mean_pixel, mask_resize_as_feature,
                use_mrf, average_pool=False)  # TODO: average pool is not working so well in practice??

        if initial is None:
            initial = tf.random_normal(shape) * 0.256
        else:
            initial = np.array([vgg.preprocess(initial, mean_pixel)])
            initial = initial.astype('float32')
        image = tf.Variable(initial)
        net, _ = vgg.net(network, image)

        # content loss
        _, height, width, number = map(lambda i: i.value, content_features[CONTENT_LAYER].get_shape())
        content_features_size = height * width * number
        content_loss = content_weight * (2 * tf.nn.l2_loss(
            net[CONTENT_LAYER] - content_features[CONTENT_LAYER]) /
                                         content_features_size)
        # style loss
        style_loss = 0
        for i in range(len(styles)):
            style_losses = []
            for style_layer in STYLE_LAYERS:
                layer = net[style_layer]
                if content_img_style_weight_mask is not None:
                    # Apply_style_weight_mask_to_feature_layer, then normalize with average of that style weight mask.
                    layer = neural_doodle_util.vgg_layer_dot_mask(style_weight_mask_layer_dict[style_layer], layer) \
                            / (tf.reduce_mean(style_weight_mask_layer_dict[style_layer]) + 0.000001)

                if use_mrf:
                    if use_semantic_masks:
                        # TODO: Compare the effect of concatenate masks to vgg layers versus dotting them with vgg
                        # layers. If you change this to dot, don't forget to also change that in neural_doodle_util.
                        layer = neural_doodle_util.concatenate_mask_layer_tf(output_semantic_mask_features[style_layer],
                                                                             layer)
                        # layer = neural_doodle_util.vgg_layer_dot_mask(output_semantic_mask_features[style_layer], layer)
                    style_losses.append(mrf_loss(style_features[i][style_layer], layer, name='%d%s' % (i, style_layer)))
                else:
                    if use_semantic_masks:
                        gram = neural_doodle_util.gramian_with_mask(layer, output_semantic_mask_features[style_layer])
                    else:
                        gram = neural_util.gramian(layer)
                    style_gram = style_features[i][style_layer]
                    style_gram_size = get_np_array_num_elements(style_gram)
                    style_losses.append(tf.nn.l2_loss(
                        gram - style_gram) / style_gram_size)  # TODO: Check normalization constants. the style loss is way too big compared to the other two.
            style_loss += style_weight * style_blend_weights[i] * reduce(tf.add, style_losses)
        # total variation denoising
        tv_loss = tf.mul(neural_util.total_variation(image), tv_weight)

        # overall loss
        if content is None:  # If we are doing style/texture regeration only.
            loss = style_loss + tv_loss
        else:
            loss = content_loss + style_loss + tv_loss

        # optimizer setup
        train_step = tf.train.AdamOptimizer(learning_rate).minimize(loss)

        def print_progress(i, feed_dict, last=False):
            stderr.write('Iteration %d/%d\n' % (i + 1, iterations))
            if last or (print_iterations is not None and print_iterations != 0 and i % print_iterations == 0):
                if content is not None:
                    stderr.write('  content loss: %g\n' % content_loss.eval(feed_dict=feed_dict))
                stderr.write('    style loss: %g\n' % style_loss.eval(feed_dict=feed_dict))
                stderr.write('       tv loss: %g\n' % tv_loss.eval(feed_dict=feed_dict))
                stderr.write('    total loss: %g\n' % loss.eval(feed_dict=feed_dict))

        # optimization
        best_loss = float('inf')
        best = np.zeros(shape=shape)
        feed_dict = {}
        if content is not None:
            feed_dict[content_image] = content_pre
        if use_semantic_masks:
            feed_dict[content_semantic_mask] = output_semantic_mask
            for styles_iter in range(len(styles)):
                feed_dict[style_semantic_masks_images[styles_iter]] = style_semantic_masks[styles_iter]
        sess.run(tf.initialize_all_variables(), feed_dict=feed_dict)
        for i in range(iterations):
            last_step = (i == iterations - 1)
            print_progress(i, feed_dict, last=last_step)
            train_step.run(feed_dict=feed_dict)

            if (checkpoint_iterations and i % checkpoint_iterations == 0) or last_step:
                this_loss = loss.eval(feed_dict=feed_dict)
                if this_loss < best_loss:
                    best_loss = this_loss
                    best = image.eval()
                yield (
                    (None if last_step else i),
                    vgg.unprocess(best.reshape(shape[1:]), mean_pixel)
                )


def _tensor_size(tensor):
    from operator import mul
    return reduce(mul, (d.value for d in tensor.get_shape()), 1)
