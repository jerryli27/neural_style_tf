#!/usr/bin/env python
# -*- coding: utf-8 -*-

from general_util import *
from stylize import stylize

# default arguments
# TODO: Consider giving user options to specify those parameters (not a good idea in general but good for debugging)
CONTENT_WEIGHT = 5e0
STYLE_WEIGHT = 1e2
TV_WEIGHT = 1e2
SEMANTIC_MASKS_WEIGHT = 1.0
SEMANTIC_MASKS_NUM_LAYERS = 4
LEARNING_RATE = 1e1
STYLE_SCALE = 1.0
ITERATIONS = 1000
PRINT_ITERATIONS = 100
CHECKPOINT_ITERATIONS = 100
VGG_PATH = 'imagenet-vgg-verydeep-19.mat'
MAX_HEIGHT = 1024
MAX_WIDTH = 1024


def slow_stylize(content_dir, style_dirs, output, style_blend_weights = None, initial = None, content_img_style_weight_mask_dir = None, checkpoint_output = None):

    if not os.path.isfile(VGG_PATH):
        raise AssertionError("Network %s does not exist. (Did you forget to download it?)" % VGG_PATH)

    if not isinstance(style_dirs, list) or len(style_dirs) == 0:
        raise TypeError("Incorrect input for variable style_dirs in function slow_stylize. It should be a list with "
                        "length at least 1 which contains paths to style images.")

    content_image = None
    if content_dir != '':
        print('reading content image %s' % content_dir)
        content_image = read_and_resize_images(content_dir)
        assert content_image is not None
        if content_image.shape[0] > MAX_HEIGHT or content_image.shape[1] > MAX_WIDTH:
            if content_image.shape[0] > content_image.shape[1]:
                new_height = MAX_HEIGHT
                new_width = int(float(content_image.shape[1]) / content_image.shape[0] * MAX_HEIGHT)
            else:
                new_height = int(float(content_image.shape[0]) / content_image.shape[1] * MAX_WIDTH)
                new_width = MAX_WIDTH
            content_image = read_and_resize_images(content_dir, new_height, new_width)
            
            
    style_images = read_and_resize_images(style_dirs, None, None)  # We don't need to resize style images.

    target_shape = (1, int(content_image.shape[0]), int(content_image.shape[1]), 3)

    if style_blend_weights is None:
        # default is equal weights
        style_blend_weights = [1.0 / len(style_images) for _ in style_images]
    else:
        total_blend_weight = sum(style_blend_weights)
        style_blend_weights = [weight / total_blend_weight
                               for weight in style_blend_weights]

    output_semantic_mask = None
    style_semantic_masks = None
    # Does not support semantic masks yet.
    # if options.use_semantic_masks:
    #     assert output_semantic_mask is not None and output_semantic_mask != ''
    #     assert (len(options.style_semantic_masks) == len(style_dirs))
    #     output_semantic_mask_paths = get_all_image_paths_in_dir(output_semantic_mask)
    #     output_semantic_mask = read_and_resize_bw_mask_images(output_semantic_mask_paths, content_image.shape[0], content_image.shape[1],
    #                                                           1,
    #                                                           options.semantic_masks_num_layers)
    #     style_semantic_masks = []
    #     for style_i, style_semantic_mask_dir in enumerate(options.style_semantic_masks):
    #         style_semantic_mask_paths = get_all_image_paths_in_dir(style_semantic_mask_dir)
    #         style_semantic_masks.append(
    #             read_and_resize_bw_mask_images(style_semantic_mask_paths, style_images[style_i].shape[0],
    #                                            style_images[style_i].shape[1], 1,
    #                                            options.semantic_masks_num_layers))

    if initial is not None:
        initial = imread(initial, shape=(content_image.shape[0], content_image.shape[1]))

    content_img_style_weight_mask = None
    if content_img_style_weight_mask_dir and content_img_style_weight_mask_dir != '':
        content_img_style_weight_mask = (
            read_and_resize_bw_mask_images([content_img_style_weight_mask_dir], content_image.shape[0], content_image.shape[1], 1,
                                           1))

    if checkpoint_output and "%s" not in checkpoint_output:
        raise AssertionError("To save intermediate images, the checkpoint output parameter must contain `%s` "
                             "(e.g. `foo%s.jpg`)")
    if checkpoint_output:
        checkpoint_dir = os.path.dirname(checkpoint_output)
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
    output_dir = os.path.dirname(output)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for iteration, image in stylize(network=VGG_PATH, content=content_image, styles=style_images,
                                    shape=target_shape, iterations=ITERATIONS,
                                    content_weight=CONTENT_WEIGHT, style_weight=STYLE_WEIGHT,
                                    tv_weight=TV_WEIGHT, style_blend_weights=style_blend_weights,
                                    learning_rate=LEARNING_RATE, initial=initial, use_mrf=False,
                                    use_semantic_masks=False,
                                    output_semantic_mask=output_semantic_mask,
                                    style_semantic_masks=style_semantic_masks,
                                    semantic_masks_weight=SEMANTIC_MASKS_WEIGHT,
                                    print_iterations=PRINT_ITERATIONS,
                                    checkpoint_iterations=CHECKPOINT_ITERATIONS,
                                    semantic_masks_num_layers=SEMANTIC_MASKS_NUM_LAYERS,
                                    content_img_style_weight_mask=content_img_style_weight_mask):
        output_file = None
        if iteration is not None:
            if checkpoint_output:
                output_file = checkpoint_output % iteration
        else:
            output_file = str(output)
        if output_file:
            imsave(output_file, image)
            yield output_file
