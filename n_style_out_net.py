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

CONTENT_LAYER = 'relu4_2'  # Same setting as in the paper https://arxiv.org/abs/1603.03417.
STYLE_LAYERS = ('relu1_1', 'relu2_1', 'relu3_1', 'relu4_1', 'relu5_1') # According to http://arxiv.org/abs/1603.03417
STYLE_LAYERS_MRF = ('relu3_1', 'relu4_1')  # According to https://arxiv.org/abs/1601.04589.

# This class is only used to pass a variable one_hot_vector to the style_synthesis_net function.
class one_hot_vector_container:
    def __init__(self,vec):
        self.vec = vec

class Stylizer:
    
    def __init__(self,path_to_network, height, width, num_styles, batch_size = 1, content_weight=5.0,
                        style_weight=100.0, tv_weight=100.0, style_blend_weights=None, learning_rate=0.001,
                        lr_decay_steps=200, min_lr=0.001, lr_decay_rate=0.7, style_only=False,
                        multiple_styles_train_scale_offset_only=False, use_mrf=False, use_johnson=False,
                        use_skip_noise_4=False, print_iterations=None, checkpoint_iterations=None, save_dir="model/",
                        content_folder=None, content_preprocessed_folder = None,
                        use_semantic_masks=False, mask_folder=None, mask_resize_as_feature=True,
                        style_semantic_masks=None, semantic_masks_weight=1.0, semantic_masks_num_layers=1,
                        do_restore_and_train=False, do_restore_and_generate=False, from_screenshot=False,
                        from_webcam=False, one_hot_vector_for_restore_and_generate=None,
                        content_img_style_weight_mask=None, style_weight_mask_for_training=None, gpu_id = -1, gpu_fraction = 0.5):
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
        :param img_dir: If neither "from_screenshot" nor "from_webcam" is true, or if use_semantic_masks is true, then
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
        self.use_johnson = use_johnson
        self.use_skip_noise_4 = use_skip_noise_4
        self.style_only = style_only
    
        if use_mrf:
            STYLE_LAYERS = STYLE_LAYERS_MRF  # MRF loss consumes much more memory compared to gramian loss.
        if use_semantic_masks:
            assert mask_folder is not None
            print("use_semantic_masks is True. Automatically turning into style only mode. I don't know how to make "
                  "semantic masks work with content image in the feed forward mode yet.")
        self.use_semantic_masks = use_semantic_masks
        self.num_styles = num_styles
        self.batch_size = batch_size
        self.semantic_masks_num_layers = semantic_masks_num_layers
        self.content_img_style_weight_mask = content_img_style_weight_mask
        if self.num_styles < 1:
            raise AssertionError('You must feed in at least one style image.')
    
        self.input_shape = (1, height, width, 3)
        print('The input shape of the content image is: %s' % (str(self.input_shape)))
        # Append a (1,) in front of the shapes of the style images. So the style_shapes contains (1, height, width, 3).
        # 3 corresponds to rgb.
    
        # Read the vgg net
        vgg_data, self.mean_pixel = vgg.read_net(path_to_network)
        print('Finished loading VGG.')
    
        # Define tensorflow placeholders and variables.
        self.graph = tf.Graph()
        # self.device_string = '/cpu:0' if gpu_id < 0 else ("/gpu:%d" %gpu_id) # This one won't work for some reason
        self.device_string = '/cpu:0' if gpu_id < 0 else ''
        with self.graph.as_default(), tf.device(self.device_string):
            if self.num_styles == 1:
                self.one_hot_style_vector = None
            else:
                print("Detected multiple style image inputs. Entering multi-style mode.")
                self.one_hot_style_vector = tf.placeholder(tf.float32, [1, self.num_styles], name='input_style_placeholder')
            if self.use_johnson:
                if self.use_semantic_masks:
                    self.inputs = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], semantic_masks_num_layers])
                else:
                    # Else, the input is the content images.
                    self.inputs = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], 3])
                if content_img_style_weight_mask is not None:
                    content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], 1], name='content_img_style_weight_mask')
                    input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(self.inputs, content_img_style_weight_mask_placeholder)
                    self.image = johnson_feedforward_net_util.net(input_concatenated, one_hot_style_vector=self.one_hot_style_vector)
                else:
                    self.image = johnson_feedforward_net_util.net(self.inputs, one_hot_style_vector=self.one_hot_style_vector)
            elif self.use_skip_noise_4:
                if self.use_semantic_masks:
                    self.inputs = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], semantic_masks_num_layers])
                else:
                    self.inputs = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], 3])
                if content_img_style_weight_mask is not None:
                    content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[batch_size, self.input_shape[1], self.input_shape[2], 1], name='content_img_style_weight_mask')
                    input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(self.inputs, content_img_style_weight_mask_placeholder)
                    self.image, self.skip_noise_list = skip_noise_4_feedforward_net.net(input_concatenated)
                else:
                    self.image, self.skip_noise_list = skip_noise_4_feedforward_net.net(self.inputs)
            else:
                raise AssertionError("You were supposed to select either johnson or skip_noise_4 generator network.")
            # To my understanding, preprocessing the images generated can make sure that their gram matrices will look
            # similar to the preprocessed content/style images. The image generated is in the normal rgb, not the
            # preprocessed/shifted version. Same reason applies to the other generator network below.
            self.image = vgg.preprocess(self.image, self.mean_pixel)
    
            # Feed the generated images, content images, and style images to vgg network and get the vgg features for each
            # layer to compute loss.
            net = vgg.pre_read_net(vgg_data, self.image)
            net_layer_sizes = vgg.get_net_layer_sizes(net)
            # Optimization
            # It used to track and record only the best one with lowest loss. This is no longer necessary and I think
            # just recording the one generated at each round will make it easier to debug.
            output_for_each_style = [None for style_i in range(self.num_styles)]
    
            saver = tf.train.Saver()
            config = tf.ConfigProto()
            config.gpu_options.per_process_gpu_memory_fraction = min(0.0,max(1.0,gpu_fraction))
            self.sess = tf.Session(config=config)

            ckpt = tf.train.get_checkpoint_state(save_dir)
            if ckpt and ckpt.model_checkpoint_path:
                saver.restore(self.sess, ckpt.model_checkpoint_path)
            else:
                print("No checkpoint found at " + str(save_dir)+ "! Program still running for debugging mode.")
                self.sess.run(tf.initialize_all_variables())

    def stylize(self, img_dir, one_hot_vector_for_restore_and_generate):
        with self.graph.as_default(), tf.device(self.device_string):


            content_image = imread(img_dir)

            content_pre = np.array([vgg.preprocess(content_image, self.mean_pixel)])

            if content_pre.shape != self.input_shape:

                self.input_shape = content_pre.shape

                if self.use_johnson:
                    if self.use_semantic_masks:
                        self.inputs = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2],
                                                                        self.semantic_masks_num_layers])
                    else:
                        self.inputs = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2], 3])

                    if self.content_img_style_weight_mask is not None:
                        content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2], 1], name='content_img_style_weight_mask')
                        input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(self.inputs, content_img_style_weight_mask_placeholder)
                        self.image = johnson_feedforward_net_util.net(input_concatenated, one_hot_style_vector=self.one_hot_style_vector, reuse=True)
                    else:
                        self.image = johnson_feedforward_net_util.net(self.inputs, one_hot_style_vector=self.one_hot_style_vector, reuse=True)
                elif self.use_skip_noise_4:
                    if self.use_semantic_masks:
                        self.inputs = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2], self.semantic_masks_num_layers])
                    else:
                        self.inputs = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2], 3])
                    if self.content_img_style_weight_mask is not None:
                        content_img_style_weight_mask_placeholder = tf.placeholder(tf.float32, shape=[self.batch_size, self.input_shape[1], self.input_shape[2], 1], name='content_img_style_weight_mask')
                        input_concatenated = neural_util.concat_content_img_style_weight_mask_to_input(self.inputs, content_img_style_weight_mask_placeholder)
                        self.image, self.skip_noise_list = skip_noise_4_feedforward_net.net(input_concatenated, reuse=True)
                    else:
                        self.image, self.skip_noise_list = skip_noise_4_feedforward_net.net(self.inputs, reuse=True)
                else:
                    raise AssertionError
                self.image = vgg.preprocess(self.image, self.mean_pixel)

            feed_dict = {}

            if self.one_hot_style_vector is not None:
                assert one_hot_vector_for_restore_and_generate is not None
                feed_dict[self.one_hot_style_vector] = one_hot_vector_for_restore_and_generate

            if self.use_johnson:
                if self.use_semantic_masks:
                    raise NotImplementedError
                    # feed_dict[self.inputs] = mask_pre_list
                elif self.style_only:
                    feed_dict[self.inputs] = np.random.uniform(size=(self.input_shape[0], self.input_shape[1], self.input_shape[2], self.input_shape[3]))
                else:
                    feed_dict[self.inputs] = content_pre
            elif self.use_skip_noise_4:
                if self.use_semantic_masks:
                    raise NotImplementedError
                    # feed_dict[self.inputs] = mask_pre_list
                elif self.style_only:
                    feed_dict[self.inputs] = np.random.uniform(size=(self.input_shape[0], self.input_shape[1], self.input_shape[2], self.input_shape[3]))
                else:
                    feed_dict[self.inputs] = content_pre
                for noise_i, skip_noise in enumerate(self.skip_noise_list):
                    skip_noise_shape = map(lambda i: i.value, skip_noise.get_shape())


                    feed_dict[skip_noise] = np.random.uniform(
                        size=(skip_noise_shape[0], skip_noise_shape[1], skip_noise_shape[2], skip_noise_4_feedforward_net.nums_noise[noise_i]))
            else:
                raise AssertionError

            generated_image = self.image.eval(feed_dict=feed_dict, session=self.sess)
            # No need to unprocess the generated image because we've preprocessed the generated image before
            # feeding it to the network.
            return scipy.misc.imresize(generated_image[0, :, :, :], (self.input_shape[1], self.input_shape[2]))