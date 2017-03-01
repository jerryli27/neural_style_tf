import tensorflow as tf
import tensorflow.contrib.slim as slim
import numpy as np

def content_extractor(images, reuse=False, mode = '', num_classes = None):
    # images: (batch, 32, 32, 3) or (batch, 32, 32, 1)

    if images.get_shape()[3] == 1:
        # For mnist dataset, replicate the gray scale image 3 times.
        images = tf.image.grayscale_to_rgb(images)

    with tf.variable_scope('content_extractor', reuse=reuse):
        with slim.arg_scope([slim.conv2d], padding='SAME', activation_fn=None,
                            weights_initializer=tf.contrib.layers.xavier_initializer()):
            with slim.arg_scope([slim.batch_norm], decay=0.95, center=True, scale=True,
                                activation_fn=tf.nn.relu,
                                is_training=(mode == 'train' or mode == 'pretrain')):
                layers = {}
                conv1_1 = slim.conv2d(images, 64, [3, 3], stride=1, scope='conv1_1')  # (batch_size, 32, 32, 64)
                conv1_1 = slim.batch_norm(conv1_1, scope='bn1_1')
                layers['conv1_1'] = conv1_1
                conv1_2 = slim.conv2d(conv1_1, 64, [3, 3], stride=2, scope='conv1_2')  # (batch_size, 16, 16, 64)
                conv1_2 = slim.batch_norm(conv1_2, scope='bn1_2')
                layers['conv1_2'] = conv1_2
                conv2_1 = slim.conv2d(conv1_2, 128, [3, 3], stride=1, scope='conv2_1')  # (batch_size, 16, 16, 128)
                conv2_1 = slim.batch_norm(conv2_1, scope='bn2_1')
                layers['conv2_1'] = conv2_1
                conv2_2 = slim.conv2d(conv2_1, 128, [3, 3], stride=2, scope='conv2_2')  # (batch_size, 8, 8, 128)
                conv2_2 = slim.batch_norm(conv2_2, scope='bn2_2')
                layers['conv2_2'] = conv2_2
                conv3_1 = slim.conv2d(conv2_2, 256, [3, 3], stride=1, scope='conv3_1')  # (batch_size, 8, 8, 256)
                conv3_1 = slim.batch_norm(conv3_1, scope='bn3_1')
                layers['conv3_1'] = conv3_1
                conv3_2 = slim.conv2d(conv3_1, 256, [3, 3], stride=2, scope='conv3_2')  # (batch_size, 4, 4, 256)
                conv3_2 = slim.batch_norm(conv3_2, scope='bn3_2')
                layers['conv3_2'] = conv3_2
                conv4_1 = slim.conv2d(conv3_2, 512, [3, 3], stride=1, scope='conv4_1')  # (batch_size, 4, 4, 512)
                conv4_1 = slim.batch_norm(conv4_1, scope='bn4_1')
                layers['conv4_1'] = conv4_1
                net = slim.conv2d(conv4_1, 512, [4, 4], stride=2, padding='VALID',
                                  scope='conv4_2')  # (batch_size, 1, 1, 512)
                net = slim.batch_norm(net, activation_fn=tf.nn.tanh, scope='bn4_2')
                layers['conv4_2'] = net
                if mode == 'pretrain':
                    net = slim.conv2d(net, num_classes, [1, 1], padding='VALID', scope='out')
                    net = slim.flatten(net)
                return net, layers

def compute_image_features(img, layers, net, image_ph, use_mrf, use_semantic_masks):
    features_dict = {}
    g = tf.Graph()
    # Choose to use cpu here because we only need to compute this once and using cpu would provide us more memory
    # than the gpu and therefore allow us to process larger style images using the extra memory. This will not have
    # an effect on the training speed later since the gram matrix size is not related to the size of the image.
    # with g.as_default(), g.device('/cpu:0'), tf.Session() as curr_sess:
    style_pre = np.array([img])
    for layer in layers:
        if use_mrf or use_semantic_masks:
            features = net[layer].eval(feed_dict={image_ph: style_pre})
            features_dict[layer] = features
        else:
            # Calculate and store gramian.
            features = net[layer].eval(feed_dict={image_ph: style_pre})
            features = np.reshape(features, (-1, features.shape[3]))
            gram = np.matmul(features.T, features) / features.size
            features_dict[layer] = gram
    return features_dict


def get_net_all_variables():
    if '0.12.0' in tf.__version__:
        return tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='content_extractor')
    else:
        return tf.get_collection(tf.GraphKeys.VARIABLES, scope='content_extractor')