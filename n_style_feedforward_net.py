"""
This file implements the feed-forward texture networks as described in the following papers

Related papers (and one blog):
"Perceptual losses for real-time style transfer and super-resolution" (https://arxiv.org/abs/1603.08155)
"A Learned Representation For Artistic Style" (https://arxiv.org/abs/1610.07629)
"Exploring the Neural Algorithm of Artistic Style" (https://arxiv.org/abs/1602.07188)
"Feed-forward neural doodle" blog (http://dmitryulyanov.github.io/feed-forward-neural-doodle/)
"Semantic Style Transfer and Turning Two-Bit Doodles into Fine Artworks" (https://arxiv.org/abs/1603.01768)
"Texture Networks - Feed-forward Synthesis of Textures and Stylized Images" (https://arxiv.org/abs/1603.03417)


-- Back propagation neural style papers:
"A Neural Algorithm of Artistic Style" (https://arxiv.org/abs/1508.06576),
"Combining Markov Random Fields and Convolutional Neural Networks for Image Synthesis" (arxiv.org/abs/1601.04589),
"Instance Normalization - The Missing Ingredient for Fast Stylization" (https://arxiv.org/abs/1607.08022),
"Semantic Style Transfer and Turning Two-Bit Doodles into Fine Artworks" (https://arxiv.org/abs/1603.01768).
"""

# import gtk.gdk
from sys import stderr

import cv2
import tensorflow as tf

import johnson_feedforward_net_util
import neural_doodle_util
import neural_util
import skip_noise_4_feedforward_net
import vgg
from general_util import *
from mrf_util import mrf_loss
from neural_util import gramian, total_variation, precompute_image_features

# For compatibility among tensorflow versions.
try:
    image_summary = tf.image_summary
    scalar_summary = tf.scalar_summary
    histogram_summary = tf.histogram_summary
    merge_summary = tf.merge_summary
    SummaryWriter = tf.train.SummaryWriter
except:
    image_summary = tf.summary.image
    scalar_summary = tf.summary.scalar
    histogram_summary = tf.summary.histogram
    merge_summary = tf.summary.merge
    SummaryWriter = tf.summary.FileWriter

CONTENT_LAYER = 'relu4_2'  # Same setting as in the paper https://arxiv.org/abs/1603.03417.
STYLE_LAYERS = ('relu1_1', 'relu2_1', 'relu3_1', 'relu4_1', 'relu5_1') # According to http://arxiv.org/abs/1603.03417
STYLE_LAYERS_MRF = ('relu3_1', 'relu4_1')  # According to https://arxiv.org/abs/1601.04589.

# This class is only used to pass a variable one_hot_vector to the style_synthesis_net function.
class one_hot_vector_container:
    def __init__(self,vec):
        self.vec = vec

def style_synthesis_net(path_to_network, height, width, styles, iterations, batch_size, content_weight=5.0,
                        style_weight=100.0, tv_weight=100.0, style_blend_weights=None, learning_rate=0.001,
                        lr_decay_steps=200, min_lr=0.001, lr_decay_rate=0.7, style_only=False,
                        multiple_styles_train_scale_offset_only=False, use_mrf=False, use_johnson=False,
                        use_skip_noise_4=False, print_iterations=None, checkpoint_iterations=None, save_dir="model/",
                        content_folder=None, content_preprocessed_folder = None,
                        use_semantic_masks=False, mask_folder=None, mask_resize_as_feature=True,
                        style_semantic_masks=None, semantic_masks_weight=1.0, semantic_masks_num_layers=1,
                        do_restore_and_train=False, do_restore_and_generate=False, from_screenshot=False,
                        from_webcam=False, test_img_dir=None, one_hot_vector_for_restore_and_generate=None,
                        content_img_style_weight_mask=None, style_weight_mask_for_training=None):
    """
    Stylize images.

    This function yields tuples (iteration, image); `iteration` is None
    if this is the final image (the last iteration).  Other tuples are yielded
    every `checkpoint_iterations` iterations.
    :param path_to_network: Path to pretrained vgg19 network. It can be downloaded at
    http://www.vlfeat.org/matconvnet/models/imagenet-vgg-verydeep-19.mat
    :param height: Height of both the content images and the output.
    :param width:  Width of both the content images and the output.
    :param styles: A list of style images as numpy arrays.
    :param iterations: The number of iterations to run.
    :param batch_size: as name suggests.
    :param content_weight: The weight for content loss. The larger the weight, the more the output will look like
    the content image.
    :param style_weight: The weight for style loss. The larger the weight, the more the output will have a style that
    looks like the style images.
    :param tv_weight: The weight for total-variation loss. The larger the weight, the smoother the output will be.
    :param style_blend_weights: If inputting multiple style images, this controls the balance between their styles.
    If left as None, it will treat all style images as equal.
    :param learning_rate: As name suggests. Default works. Higher learning rate may result in unstable result.
    :param lr_decay_steps: learning rate decays by lr_decay_rate after lr_decay steps.
    Default per https://arxiv.org/abs/1603.03417. I didn't find it so useful though because if I try to set the lr to
    be too high, training fails no matter how I lower the learning rate later on.
    :param min_lr: The minimum learning rate. The learning rate will not be decrease beyong this point.
    :param lr_decay_rate: The learning rate is decreased by a factor every this number of batches.
    :param style_only: If true, it will be trained to generate only style/texture without content images.
    :param multiple_styles_train_scale_offset_only: If true, the network will be training only on the scale and shift
    variables (of the instance norms) for any style images other than the first one.
    :param use_mrf: Whether we use markov-random-field loss instead of gramian loss. mrf_util.py contains more info.
    This is still in experimental stage!!! I'm not sure feed forward network can learn mrf which is fundamentally
    a nearest neighbor method.
    :param use_johnson: If true, it will use the johnson feed forward network as the generator.
    :param use_skip_noise_4: If true, it will use the skip_noise_4 feed forward network as the generator.
    :param print_iterations: Print loss information every n iterations.
    :param checkpoint_iterations: Save a checkpoint as well as the best image so far every n iterations.
    :param save_dir: The folder to save the checkpoints.
    :param content_folder: The folder from where it collect content images for training if needed. A good choice would
    be the Microsoft COCO dataset.
    :param content_preprocessed_folder: the folder from where it will read the preprocessed content images,
    save them in the memory instead of read and preprocess the images during training. If the
    folder is blank, then it will not save the preprocessed image and will instead read the images as it is training.
    :param use_semantic_masks: Whether we use semantic masks as additional semantic information. Please check the paper
    "Semantic Style Transfer and Turning Two-Bit Doodles into Fine Artworks" as well as the blog for the fast forward
    version of it for more information.
    :param mask_folder: The folder containing training images for masks.
    :param mask_resize_as_feature: If true, resize the mask and use the resized mask as additional feature besides the
    vgg network layers. If false, pass the masks (must have exactly 3 masks) into the vgg network and use the outputted
    layers as additional features.
    :param style_semantic_masks: A list of semantic masks you would like to apply to each style image. The mask should
    have shape (batch_size, height, width, semantic_masks_num_layers)
    :param semantic_masks_weight: How heavily you'd like to weight the semantic masks as compared to other sources of
    semantic information obtained through passing the image through vgg network. Default is 1.0.
    :param semantic_masks_num_layers: The number of semantic masks each image have.
    :param do_restore_and_train: If true, the model would load a previously saved checkpoint in the "save_dir" and
    continue training from there.
    :param do_restore_and_generate: If true, it will not train the model, but instead read from a previously saved
    checkpoint in the "save_dir" and generate a new image using some extra parameters provided below.
    :param from_screenshot: If true, the content image would be taken from the screenshot of the current screen.
    :param from_webcam: If true, the content image would be the image taken from the webcam.
    :param test_img_dir: If neither "from_screenshot" nor "from_webcam" is true, or if use_semantic_masks is true, then
    the content image (or the semantic masks) would come from this variable.
    :param one_hot_vector_for_restore_and_generate: If the model is trained using multiple styles, then this variable
    is provided to specify which style (or a mixure of styles) to use when do_restore_and_generate is true.
    :param content_img_style_weight_mask: This is EXPERIMENTAL! see stylize for more documentation.
    :param style_weight_mask_for_training: This is EXPERIMENTAL! This is the np array containing random masks to be
    used for training.
    :return:iterator[tuple[int|None,List[image]]]

    """
    # TODO: delete use_mrf if it is guaranteed not to work using feed forward mode.

    # Before training, make sure everything is set correctly.
    global STYLE_LAYERS
    if (not use_johnson and not use_skip_noise_4) or (use_skip_noise_4 and use_johnson):
        raise AssertionError("Please select one generator network, either johnson or skip_noise_4.")

    if use_mrf:
        STYLE_LAYERS = STYLE_LAYERS_MRF  # MRF loss consumes much more memory compared to gramian loss.
    if use_semantic_masks:
        assert mask_folder is not None
        print("use_semantic_masks is True. Automatically turning into style only mode. I don't know how to make "
              "semantic masks work with content image in the feed forward mode yet.")


    if len(styles) < 1:
        raise AssertionError('You must feed in at least one style image.')

    if content_img_style_weight_mask is not None:
        if do_restore_and_train or not do_restore_and_generate:
            assert style_weight_mask_for_training is not None
        if do_restore_and_generate and (height != content_img_style_weight_mask.shape[1] or width != content_img_style_weight_mask.shape[2]):
            raise AssertionError("The shape of style_weight_mask is incorrect. It must have the same height and width "
                                 "as the output image. The output image has shape: %s and the style weight mask has "
                                 "shape: %s" % (str((height, width)), str(content_img_style_weight_mask.shape)))
        if content_img_style_weight_mask.dtype!=np.float32:
            raise AssertionError('The dtype of style_weight_mask must be float32. it is now %s'
                                 % str(content_img_style_weight_mask.dtype))

        print('content_img_style_weight_mask is not None. Note that this is only an experimental feature that is very '
              'likely not working. Proceed with caution!!!')

    input_shape = (1, height, width, 3)
    print('The input shape of the content image is: %s' % (str(input_shape)))
    # Append a (1,) in front of the shapes of the style images. So the style_shapes contains (1, height, width, 3).
    # 3 corresponds to rgb.
    style_shapes = [(1,) + style.shape for style in styles]

    if use_mrf:
        for style_shape in style_shapes:
            if style_shape != input_shape:
                raise AssertionError("In order to use mrf loss, the content and style images must have the same "
                                     "shapes.")


    content_features = {}
    style_features = [{} for _ in styles]
    output_semantic_mask_features = {}
    content_img_preprocessed = None
    prev_content_preprocessed_file_i = 0

    # Read the vgg net
    vgg_data, mean_pixel = vgg.read_net(path_to_network)
    print('Finished loading VGG.')

    if not do_restore_and_generate:
        # # Compute style features in feedforward mode.
        for i in range(len(styles)):
            style_features[i] = precompute_image_features(styles[i], STYLE_LAYERS, style_shapes[i], vgg_data, mean_pixel, use_mrf, use_semantic_masks)
        print('Finished passing style images to VGG for precomputing features.')

        if content_preprocessed_folder is not None and content_preprocessed_folder != '' and not style_only:
            if not os.path.isfile(content_preprocessed_folder + 'record.txt'):
                raise AssertionError('No preprocessed content images found in %s. To use this feature, first use some '
                                     'other file to call read_resize_and_save_all_imgs_in_dir.'
                                     % (content_preprocessed_folder))
            content_preprocessed_record = read_preprocessed_npy_record(content_preprocessed_folder)
            if content_preprocessed_record[0][1] != batch_size or content_preprocessed_record[0][2] != height or \
                            content_preprocessed_record[0][3] != width :
                raise AssertionError('The height, width, and batch size of the preprocessed numpy files does not '
                                     'match those of the current setting.')
            # Read the first file
            print('Reading preprocessed content images.')
            content_img_preprocessed = np.load(content_preprocessed_record[prev_content_preprocessed_file_i][0])


    # Define tensorflow placeholders and variables.
    with tf.Graph().as_default():
        if len(styles) == 1:
            one_hot_style_vector = None
        else:
            print("Detected multiple style image inputs. Entering multi-style mode.")
            one_hot_style_vector = tf.placeholder(tf.float32, [1, len(styles)], name='input_style_placeholder')
        if use_johnson:
            if use_semantic_masks:
                inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], semantic_masks_num_layers])
            else:
                # Else, the input is the content images.
                inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 3])
            if content_img_style_weight_mask is not None:
                content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 1], name='content_img_style_weight_mask')
                input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(inputs, content_img_style_weight_mask_placeholder)
                image = johnson_feedforward_net_util.net(input_concatenated, one_hot_style_vector=one_hot_style_vector)
            else:
                image = johnson_feedforward_net_util.net(inputs, one_hot_style_vector=one_hot_style_vector)
        elif use_skip_noise_4:
            if use_semantic_masks:
                inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], semantic_masks_num_layers])
            else:
                inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 3])
            if content_img_style_weight_mask is not None:
                content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 1], name='content_img_style_weight_mask')
                input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(inputs, content_img_style_weight_mask_placeholder)
                image, skip_noise_list = skip_noise_4_feedforward_net.net(input_concatenated)
            else:
                image, skip_noise_list = skip_noise_4_feedforward_net.net(inputs)
        else:
            raise AssertionError("You were supposed to select either johnson or skip_noise_4 generator network.")
        # To my understanding, preprocessing the images generated can make sure that their gram matrices will look
        # similar to the preprocessed content/style images. The image generated is in the normal rgb, not the
        # preprocessed/shifted version. Same reason applies to the other generator network below.
        image = vgg.preprocess(image, mean_pixel)

        # Feed the generated images, content images, and style images to vgg network and get the vgg features for each
        # layer to compute loss.
        net = vgg.pre_read_net(vgg_data, image)
        net_layer_sizes = vgg.get_net_layer_sizes(net)
        if not do_restore_and_generate:
            learning_rate_decayed_init = tf.constant(learning_rate)
            learning_rate_decayed = tf.get_variable(name='learning_rate_decayed', trainable=False,
                                                    initializer=learning_rate_decayed_init)
            # compute content features in feed-forward mode.
            content_images = tf.placeholder(tf.float32, [batch_size, input_shape[1], input_shape[2], 3],
                                            name='content_images_placeholder')
            content_pre = vgg.preprocess(content_images, mean_pixel)
            content_net = vgg.pre_read_net(vgg_data, content_pre)
            content_features[CONTENT_LAYER] = content_net[CONTENT_LAYER]

            if use_semantic_masks:
                output_semantic_mask_features, style_features, content_semantic_mask, style_semantic_masks_images = neural_doodle_util.construct_masks_and_features(style_semantic_masks, styles, style_features, batch_size, input_shape[1], input_shape[2], semantic_masks_num_layers, STYLE_LAYERS, net_layer_sizes, semantic_masks_weight, vgg_data, mean_pixel, mask_resize_as_feature, use_mrf)


            # content loss
            if not (style_only or use_semantic_masks):
                content_features_size = neural_util.get_tensor_num_elements(content_features[CONTENT_LAYER])
                content_loss = content_weight * (2 * tf.nn.l2_loss(
                    net[CONTENT_LAYER] - content_features[CONTENT_LAYER]) / content_features_size)

                content_loss_summary = scalar_summary("content_loss_summary", content_loss)

            if content_img_style_weight_mask is not None:
                # *** TESTING
                # Compute average pooled style weight masks for each feature layer in vgg.
                style_weight_mask_layer_dict = neural_doodle_util.masks_average_pool(content_img_style_weight_mask_placeholder)
                # *** END TESTING

            # style loss
            style_loss_for_each_style = []
            style_loss_summary_for_each_style = []
            for i in range(len(styles)):
                style_losses_for_each_style_layer = []
                for style_layer in STYLE_LAYERS:
                    layer = net[style_layer]
                    if content_img_style_weight_mask is not None:
                        # Apply style_weight_mask to each feature layer, then normalize with average of that style
                        # weight mask.
                        layer = neural_doodle_util.vgg_layer_dot_mask(style_weight_mask_layer_dict[style_layer], layer) \
                                / (tf.reduce_mean(style_weight_mask_layer_dict[style_layer]) + 0.000001)
                    if use_mrf:
                        if use_semantic_masks:
                            # If we use mrf for the style loss, we concatenate the mask layer to the features and
                            # essentially just treat it as another addditional feature that we added.
                            layer = neural_doodle_util.concatenate_mask_layer_tf(
                                output_semantic_mask_features[style_layer], layer)
                        print('mrfing %d %s' % (i, style_layer))
                        style_losses_for_each_style_layer.append(
                            mrf_loss(style_features[i][style_layer], layer, name='%d%s' % (i, style_layer)))
                        print('mrfed %d %s' % (i, style_layer))
                    else:
                        if use_semantic_masks:
                            gram = neural_doodle_util.gramian_with_mask(layer, output_semantic_mask_features[style_layer])
                        else:
                            gram = gramian(layer)
                        style_gram = style_features[i][style_layer]
                        if use_semantic_masks:
                            # Dividing by semantic_masks_num_layers because the masks should have one 1 in each pixel
                            # and we should not divide by the number of extra elements with 0.
                            style_gram_num_elements = neural_util.get_tensor_num_elements(style_gram) / semantic_masks_num_layers
                        else:
                            style_gram_num_elements = get_np_array_num_elements(style_gram)
                        style_losses_for_each_style_layer.append(
                            2 * tf.nn.l2_loss(gram - style_gram) / style_gram_num_elements)
                current_style_loss =  style_weight * style_blend_weights[i] * reduce(tf.add, style_losses_for_each_style_layer) / batch_size
                style_loss_for_each_style.append(current_style_loss)
                style_loss_summary_for_each_style.append(scalar_summary("style_loss_%d_summary" % i,
                                                                        style_loss_for_each_style[-1]))
            # According to https://arxiv.org/abs/1610.07629 when "zero-padding is replaced with mirror-padding,
            # and transposed convolutions (also sometimes called deconvolutions) are replaced with nearest-neighbor
            # upsampling followed by a convolution.", tv is no longer needed.
            # But in other papers I've seen tv-loss still applicable, like in https://arxiv.org/abs/1603.08155.
            # TODO: side task: find out the difference between having tv loss and not.
            tv_loss = tv_weight * total_variation(image)
            tv_loss_summary = scalar_summary('tv_loss_summary', tv_loss)

            # overall loss
            if style_only or use_semantic_masks:
                losses_for_each_style = [style_loss + tv_loss for style_loss in style_loss_for_each_style]
            else:
                losses_for_each_style = [style_loss + content_loss + tv_loss for style_loss in
                                         style_loss_for_each_style]
            overall_loss = 0
            for loss_for_each_style in losses_for_each_style:
                overall_loss += loss_for_each_style
                # TODO: There might be a bug here because it is not possible to feed multiple styles all at the same
                # time, so the overall loss would be impossible to calculate and the current result is wrong.
            # optimizer setup
            # Training using adam optimizer. Setting comes from https://arxiv.org/abs/1610.07629.
            if multiple_styles_train_scale_offset_only:
                # If the variable above is set to be True, then training is only done on the scale and offset of the
                # instance normalizations in the generator network. It will in theory increase the speed of training
                # but at the price of sacrificing the quality of the output (from what I've seen the quality is better
                # when it trains on all variable instead of just scale and offset).
                if use_johnson:
                    scale_offset_var = johnson_feedforward_net_util.get_johnson_scale_offset_var()
                elif use_skip_noise_4:
                    raise NotImplementedError("Did not implement multiple style training on skip_noise_4 yet.")
                else:
                    raise AssertionError("You were supposed to select either johnson or skip_noise_4 generator network.")
                train_step_for_each_style = [
                    tf.train.AdamOptimizer(learning_rate_decayed, beta1=0.9,
                                           beta2=0.999).minimize(loss, var_list=scale_offset_var)
                    if i != 0 else
                    tf.train.AdamOptimizer(learning_rate_decayed, beta1=0.9,
                                           beta2=0.999).minimize(loss)
                    for i, loss in
                    enumerate(losses_for_each_style)]
            else:
                train_step_for_each_style = [
                    tf.train.AdamOptimizer(learning_rate_decayed, beta1=0.9,
                                           beta2=0.999).minimize(loss)
                    for i, loss in
                    enumerate(losses_for_each_style)]

            def print_progress(i, feed_dict, last=False):
                stderr.write(
                    'Iteration %d/%d\n' % (i + 1, iterations))
                if last or (print_iterations and i % print_iterations == 0):
                    stderr.write('Learning rate %f\n' % (learning_rate_decayed.eval()))
                    # Assume that the feed_dict is for the last content and style image.
                    if not (style_only or use_semantic_masks):
                        stderr.write('  content loss: %g\n' % content_loss.eval(feed_dict=feed_dict))
                    stderr.write('    style loss: %g\n' % style_loss_for_each_style[-1].eval(feed_dict=feed_dict))
                    stderr.write('       tv loss: %g\n' % tv_loss.eval(feed_dict=feed_dict))
                    stderr.write('    total loss: %g\n' % overall_loss.eval(feed_dict=feed_dict))

        # Optimization
        # It used to track and record only the best one with lowest loss. This is no longer necessary and I think
        # just recording the one generated at each round will make it easier to debug.
        output_for_each_style = [None for style_i in range(len(styles))]

        saver = tf.train.Saver()
        with tf.Session() as sess:
            if do_restore_and_generate:
                ckpt = tf.train.get_checkpoint_state(save_dir)
                if ckpt and ckpt.model_checkpoint_path:
                    saver.restore(sess, ckpt.model_checkpoint_path)
                else:
                    stderr("No checkpoint found at %s. Exiting program" %(save_dir))
                    return

                if from_screenshot:
                    # This is the x and y offset, the coordinate where we start capturing screen shot.
                    kScreenX = 300
                    kScreenY = 300
                elif from_webcam:
                    cap = cv2.VideoCapture(0)
                    # Set width and height.
                    ret = cap.set(3, 1280)
                    ret = cap.set(4, 960)
                    ret, frame = cap.read()
                    print('The dimension of this camera is : %d x %d' % (frame.shape[1], frame.shape[0]))
                else:
                    assert test_img_dir is not None

                if use_johnson:
                    if use_semantic_masks:
                        inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2],
                                                                   semantic_masks_num_layers])
                    else:
                        inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 3])

                    if content_img_style_weight_mask is not None:
                        content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 1], name='content_img_style_weight_mask')
                        input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(inputs, content_img_style_weight_mask_placeholder)
                        image = johnson_feedforward_net_util.net(input_concatenated, one_hot_style_vector=one_hot_style_vector, reuse=True)
                    else:
                        image = johnson_feedforward_net_util.net(inputs, one_hot_style_vector=one_hot_style_vector, reuse=True)
                elif use_skip_noise_4:
                    if use_semantic_masks:
                        inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], semantic_masks_num_layers])
                    else:
                        inputs = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 3])
                    if content_img_style_weight_mask is not None:
                        content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, input_shape[1], input_shape[2], 1], name='content_img_style_weight_mask')
                        input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(inputs, content_img_style_weight_mask_placeholder)
                        image, skip_noise_list = skip_noise_4_feedforward_net.net(input_concatenated, reuse=True)
                    else:
                        image, skip_noise_list = skip_noise_4_feedforward_net.net(inputs, reuse=True)
                else:
                    raise AssertionError
                image = vgg.preprocess(image, mean_pixel)
                iterator = 0

                while from_screenshot or from_webcam or (iterator == 0):
                    if from_screenshot:
                        raise ImportError("I commented out this part because I forgot how to install/import gtk.gdk")
                        # w = gtk.gdk.get_default_root_window()
                        # sz = w.get_size()
                        # print "The size of the window is %d x %d" % sz
                        # pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, input_shape[1], input_shape[2])
                        # pb = pb.get_from_drawable(w, w.get_colormap(), kScreenX, kScreenY, 0, 0, input_shape[1],
                        #                           input_shape[2])
                        # content_image = pb.pixel_array
                    elif from_webcam:
                        ret, frame = cap.read()
                        content_image = scipy.misc.imresize(frame, (input_shape[1], input_shape[2]))
                    elif use_semantic_masks:
                        # Dummy content image.
                        content_image = np.zeros((batch_size, input_shape[1], input_shape[2], 3))
                    else:
                        content_image = imread(test_img_dir, (input_shape[1], input_shape[2]))

                    content_pre = np.array([vgg.preprocess(content_image, mean_pixel)])
                    feed_dict = {}

                    if use_semantic_masks:
                        # Read semantic masks.
                        mask_dirs = get_all_image_paths_in_dir(test_img_dir)

                        if not len(mask_dirs) >= (batch_size * semantic_masks_num_layers):
                            print('ERROR: The number of images in mask_dirs has to be larger than batch size times '
                                  'number of semantic masks. Path to test_img_dir is: %s. '
                                  'number of images in mask dirs is : %d' % (test_img_dir, len(mask_dirs)))
                            raise AssertionError
                        if len(mask_dirs) > (batch_size * semantic_masks_num_layers):
                            mask_dirs = mask_dirs[:batch_size * semantic_masks_num_layers]

                        for semantic_masks_i in range(semantic_masks_num_layers):
                            expected_end_str=  '%d.png' %semantic_masks_i
                            if mask_dirs[semantic_masks_i][-5:] != expected_end_str:
                                print('%s did not end with %s' %(mask_dirs[semantic_masks_i],expected_end_str))
                                raise AssertionError
                            if semantic_masks_i != 0 and mask_dirs[semantic_masks_i - 1][:-5] != mask_dirs[semantic_masks_i][:-5]:
                                print('%s did not start with %s' %(mask_dirs[semantic_masks_i],mask_dirs[semantic_masks_i - 1][:-5]))
                                raise AssertionError

                        mask_pre_list = read_and_resize_bw_mask_images(mask_dirs, input_shape[1], input_shape[2],
                                                                       batch_size, semantic_masks_num_layers)

                    if one_hot_style_vector is not None:
                        if from_webcam:
                            # Since webcam is updating the one_hot_vector_for_restore_and_generate constantly,
                            # I must do something different.
                            assert one_hot_vector_for_restore_and_generate is not None and isinstance(
                                one_hot_vector_for_restore_and_generate,one_hot_vector_container)
                            feed_dict[one_hot_style_vector] = one_hot_vector_for_restore_and_generate.vec
                        else:
                            assert one_hot_vector_for_restore_and_generate is not None
                            feed_dict[one_hot_style_vector] = one_hot_vector_for_restore_and_generate



                    if use_johnson:
                        if use_semantic_masks:
                            feed_dict[inputs] = mask_pre_list
                        elif style_only:
                            feed_dict[inputs] = np.random.uniform(size=(input_shape[0], input_shape[1], input_shape[2], input_shape[3]))
                        else:
                            feed_dict[inputs] = content_pre
                    elif use_skip_noise_4:
                        if use_semantic_masks:
                            feed_dict[inputs] = mask_pre_list
                        elif style_only:
                            feed_dict[inputs] = np.random.uniform(size=(input_shape[0], input_shape[1], input_shape[2], input_shape[3]))
                        else:
                            feed_dict[inputs] = content_pre
                        for noise_i, skip_noise in enumerate(skip_noise_list):
                            skip_noise_shape = map(lambda i: i.value, skip_noise.get_shape())


                            feed_dict[skip_noise] = np.random.uniform(
                                size=(skip_noise_shape[0], skip_noise_shape[1], skip_noise_shape[2], skip_noise_4_feedforward_net.nums_noise[noise_i]))
                    else:
                        raise AssertionError

                    if content_img_style_weight_mask is not None:
                        feed_dict[content_img_style_weight_mask_placeholder] = content_img_style_weight_mask
                    generated_image = image.eval(feed_dict=feed_dict)
                    iterator += 1
                    # Can't return because we are in a generator in python 2.7. So do a one-time yield instead.
                    # No need to unprocess the generated image because we've preprocessed the generated image before
                    # feeding it to the network.
                    yield (iterator, scipy.misc.imresize(generated_image[0, :, :, :], (input_shape[1], input_shape[2])))

            else:
                # Initialize log writer
                log_path = save_dir + "logs"
                if not os.path.exists(log_path):
                    os.makedirs(log_path)
                summary_writer = SummaryWriter(log_path, sess.graph)

                # Do Training.
                iter_start = 0
                if do_restore_and_train:
                    ckpt = tf.train.get_checkpoint_state(save_dir)
                    if ckpt and ckpt.model_checkpoint_path:
                        saver.restore(sess, ckpt.model_checkpoint_path)
                        iter_start = get_global_step_from_save_dir(ckpt.model_checkpoint_path)
                    else:
                        stderr("No checkpoint found. Exiting program")
                        return
                else:
                    sess.run(tf.initialize_all_variables())

                if not (style_only or use_semantic_masks or content_preprocessed_folder is None or
                                content_preprocessed_folder == ''):
                    # Get path to all content images.
                    content_dirs = get_all_image_paths_in_dir(content_folder)
                    # Ignore the ones at the end.
                    if batch_size != 1:
                        content_dirs = content_dirs[:-(len(content_dirs) % batch_size)]

                if use_semantic_masks:
                    # Get path to all mask images.
                    mask_dirs = get_all_image_paths_in_dir(mask_folder)
                    if len(mask_dirs) < batch_size * semantic_masks_num_layers:
                        print('ERROR: The number of images in mask_folder has to be larger than batch size times '
                              'number of semantic masks. Path to mask_folder is: %s. '
                              'number of images in mask dirs is : %d' % (mask_folder, len(mask_dirs)))
                        raise AssertionError
                    # Ignore the ones at the end.
                    if batch_size * semantic_masks_num_layers != 1 and len(mask_dirs) % (
                        batch_size * semantic_masks_num_layers) != 0:
                        mask_dirs = mask_dirs[:-(len(mask_dirs) % (batch_size * semantic_masks_num_layers))]

                for i in range(iter_start, iterations):
                    # First decay the learning rate if we need to
                    if (i % lr_decay_steps == 0):
                        current_lr = learning_rate_decayed.eval()
                        sess.run(learning_rate_decayed.assign(max(min_lr, current_lr * lr_decay_rate)))

                    if not style_only:
                        if content_preprocessed_folder is not None and content_preprocessed_folder != '':
                            current_content_preprocessed_file_i, index_within_preprocessed =  \
                                find_corresponding_npy_from_record(
                                content_preprocessed_record, i * batch_size)
                            if prev_content_preprocessed_file_i != current_content_preprocessed_file_i:
                                prev_content_preprocessed_file_i = current_content_preprocessed_file_i
                                content_img_preprocessed = np.load(content_preprocessed_record[
                                                                       current_content_preprocessed_file_i][0])
                            content_pre_list = content_img_preprocessed[
                                               index_within_preprocessed:index_within_preprocessed+batch_size,
                                               ...].astype(np.float32)
                        else:
                            # Load content images
                            current_content_dirs = get_batch_paths(content_dirs, i * batch_size, batch_size)
                            content_pre_list = read_and_resize_batch_images(current_content_dirs, input_shape[1],
                                                                            input_shape[2])

                    # Load mask images
                    if use_semantic_masks:
                        current_mask_dirs = get_batch_paths(mask_dirs, i * batch_size * semantic_masks_num_layers,
                                                            batch_size * semantic_masks_num_layers)
                        # DEBUG
                        for semantic_masks_i in range(semantic_masks_num_layers):
                            expected_end_str=  '%d.png' %semantic_masks_i
                            if current_mask_dirs[semantic_masks_i][-5:] != expected_end_str:
                                print('%s did not end with %s' %(current_mask_dirs[semantic_masks_i],expected_end_str))
                                raise AssertionError
                            if semantic_masks_i != 0 and current_mask_dirs[semantic_masks_i - 1][:-5] != current_mask_dirs[semantic_masks_i][:-5]:
                                print('%s did not start with %s' %(current_mask_dirs[semantic_masks_i],current_mask_dirs[semantic_masks_i - 1][:-5]))
                                raise AssertionError

                        mask_pre_list = read_and_resize_bw_mask_images(current_mask_dirs, input_shape[1],
                                                                       input_shape[2], batch_size,
                                                                       semantic_masks_num_layers)
                    for style_i in range(len(styles)):
                        last_step = (i == iterations - 1)
                        # Feed the content image.
                        feed_dict = {content_images: content_pre_list} if not style_only else {}

                        if one_hot_style_vector is not None:
                            feed_dict[one_hot_style_vector] = np.array([[1.0 if style_i == style_j else 0.0 for style_j in range(len(styles))]])

                        if use_johnson:
                            if use_semantic_masks:
                                feed_dict[inputs] = mask_pre_list
                                feed_dict[content_semantic_mask] = mask_pre_list
                                for styles_iter in range(len(styles)):
                                    feed_dict[style_semantic_masks_images[styles_iter]] = np.expand_dims(
                                        style_semantic_masks[styles_iter], axis=0)
                            else:
                                if style_only:
                                    feed_dict[inputs] = np.random.uniform(size=(input_shape[0], input_shape[1], input_shape[2], input_shape[3]))
                                else:
                                    feed_dict[inputs] = content_pre_list
                        elif use_skip_noise_4:
                            if use_semantic_masks:
                                # Note: the following comment may not be directly related to the code. Please ignore
                                # this unless you want to find out where I get the skip_noise_4 generator network.
                                # According to github.com/DmitryUlyanov/online-neural-doodle/blob/master/src/utils.lua
                                # The first # semantic_masks_num_layers layers will be filled with the mask itself
                                # The second # semantic_masks_num_layers*num_mask_noise_times will be filled with mask dot
                                # uniform noise
                                # And the last # num_mask_noise_times layers will be filled with uniform noise.
                                # Then I realized that although that git repo implemented this feature, it did not
                                # actually used it.
                                feed_dict[inputs] = mask_pre_list
                                feed_dict[content_semantic_mask] = mask_pre_list
                                for styles_iter in range(len(styles)):
                                    feed_dict[style_semantic_masks_images[styles_iter]] = np.expand_dims(
                                        style_semantic_masks[styles_iter], axis=0)
                            elif style_only:
                                feed_dict[inputs] = np.random.uniform(
                                    size=(input_shape[0], input_shape[1], input_shape[2], input_shape[3]))
                            else:
                                feed_dict[inputs] = content_pre_list
                            for noise_i, skip_noise in enumerate(skip_noise_list):
                                skip_noise_shape = map(lambda i: i.value, skip_noise.get_shape())
                                feed_dict[skip_noise] = np.random.uniform(size=(skip_noise_shape[0], skip_noise_shape[1], skip_noise_shape[2], skip_noise_4_feedforward_net.nums_noise[noise_i]))
                        else:
                            raise NotImplementedError

                        if content_img_style_weight_mask is not None:
                            content_img_style_weight_mask_shape = map(lambda s: s.value, content_img_style_weight_mask_placeholder.get_shape())
                            style_weight_mask_for_training_shape = style_weight_mask_for_training.shape
                            if content_img_style_weight_mask_shape[1] != style_weight_mask_for_training_shape[1] or content_img_style_weight_mask_shape[2] != style_weight_mask_for_training_shape[2]:
                                print("The training masks' shape does not correspond with the place holder's shape. The training mask shape is: %s and the place holder shape is: %s. They should have the same height and width." %(str(style_weight_mask_for_training_shape), str(content_img_style_weight_mask_shape)))
                            content_img_style_weight_mask_batch_i = get_batch_indices(style_weight_mask_for_training_shape[0], i * batch_size, batch_size)
                            feed_dict[content_img_style_weight_mask_placeholder] = style_weight_mask_for_training[content_img_style_weight_mask_batch_i, :, :, :]

                        if style_only or use_semantic_masks:
                            _, style_loss_summary_str, tv_loss_summary_str = sess.run(
                                [train_step_for_each_style[style_i],
                                 style_loss_summary_for_each_style[style_i], tv_loss_summary], feed_dict=feed_dict)

                        else:
                            _, content_loss_summary_str, style_loss_summary_str, tv_loss_summary_str = sess.run([train_step_for_each_style[style_i], content_loss_summary, style_loss_summary_for_each_style[style_i], tv_loss_summary], feed_dict=feed_dict)

                        if not (style_only or use_semantic_masks):
                            summary_writer.add_summary(content_loss_summary_str, i)
                        summary_writer.add_summary(style_loss_summary_str, i)
                        summary_writer.add_summary(tv_loss_summary_str, i)

                        # train_step_for_each_style[style_i].run(feed_dict=feed_dict)

                        if style_i == len(styles) - 1:
                            print_progress(i, feed_dict=feed_dict, last=last_step)

                        if (checkpoint_iterations and i % checkpoint_iterations == 0) or last_step:
                            # Do checkpoint only when it reached the last style image.
                            if style_i == len(styles) - 1:
                                saver.save(sess, save_dir + 'model.ckpt', global_step=i)

                                if test_img_dir is not None:
                                    if use_semantic_masks:
                                        test_mask_dirs = get_all_image_paths_in_dir(test_img_dir)
                                        test_image = imread(test_mask_dirs[0])
                                        test_image_shape = test_image.shape
                                    else:
                                        test_image = imread(test_img_dir)
                                        test_image_shape = test_image.shape

                                    for generate_style_i in range(len(styles)):
                                        current_one_hot_vector_for_restore_and_generate=np.array([[1.0 if generate_style_i == style_j else 0.0 for style_j in range(len(styles))]])
                                        # The checkpoint is done through reading the checkpoint that was just saved and
                                        # use that to generate the checkpoint image.

                                        # The for loop will run once and terminate. Can't use return and yield in the
                                        # same function in python 2 so this is a hacky way to do it.
                                        for _, generated_image in style_synthesis_net(path_to_network,
                                                                                      test_image_shape[0],
                                                                                      test_image_shape[1], styles,
                                                                                      iterations, 1, content_weight,
                                                                                      style_weight, tv_weight,
                                                                                      style_blend_weights,
                                                                                      learning_rate,
                                                                                      style_only=style_only,
                                                                                      multiple_styles_train_scale_offset_only=multiple_styles_train_scale_offset_only,
                                                                                      use_mrf=use_mrf,
                                                                                      use_johnson=use_johnson,
                                                                                      use_skip_noise_4=use_skip_noise_4,
                                                                                      save_dir=save_dir,
                                                                                      use_semantic_masks=use_semantic_masks,
                                                                                      mask_folder=mask_folder,
                                                                                      mask_resize_as_feature=mask_resize_as_feature,
                                                                                      style_semantic_masks=style_semantic_masks,
                                                                                      semantic_masks_weight=semantic_masks_weight,
                                                                                      semantic_masks_num_layers=semantic_masks_num_layers,
                                                                                      do_restore_and_train=False,
                                                                                      do_restore_and_generate=True,
                                                                                      from_screenshot=False,
                                                                                      from_webcam=False,
                                                                                      test_img_dir=test_img_dir,
                                                                                      one_hot_vector_for_restore_and_generate=current_one_hot_vector_for_restore_and_generate,
                                                                                      content_img_style_weight_mask=content_img_style_weight_mask):
                                            pass

                                        output_for_each_style[generate_style_i] = generated_image

                                # Because we now have batch, choose the first one in the batch as our sample image.
                                yield (
                                    (None if last_step else i),
                                    [None if test_img_dir is None else
                                     output_for_each_style[style_j] for style_j in range(len(styles))]
                                )
