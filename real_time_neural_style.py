"""
This file is used to run feed-forward style transfer nets on real time inputs such as the camera or the screen.
You must provide a path to a pretrained network as well as the style images it used.
"""

import time
from argparse import ArgumentParser

from matplotlib import pyplot as plt
from matplotlib.widgets import Slider

import n_style_feedforward_net
from general_util import *

# default arguments
CONTENT_WEIGHT = 5e0
STYLE_WEIGHT = 1e2
TV_WEIGHT = 1e2
LEARNING_RATE = 1e1
STYLE_SCALE = 1.0
ITERATIONS = 1000
BATCH_SIZE = 1
VGG_PATH = 'imagenet-vgg-verydeep-19.mat'




def build_parser():
    parser = ArgumentParser()
    parser.add_argument('--styles', dest='styles', nargs='+',
                        help='One or more style images.',
                        metavar='STYLE', required=True)
    parser.add_argument('--texture_synthesis_only', dest='texture_synthesis_only',
                        help='If true, we only generate the texture of the style images. '
                             'No content image will be used.',
                        action='store_true')
    parser.set_defaults(texture_synthesis_only=False)
    parser.add_argument('--height', type=int, dest='height',
                        help='Input and output height. All content images should be automatically scaled accordingly.',
                        metavar='HEIGHT', default=256)
    parser.add_argument('--width', type=int, dest='width',
                        help='Input and output width. All content images should be automatically scaled accordingly.',
                        metavar='WIDTH', default=256)
    parser.add_argument('--network',
                        dest='network', help='path to pre-trained vgg 19 network (default %(default)s).',
                        metavar='VGG_PATH', default=VGG_PATH)
    parser.add_argument('--use_johnson', dest='use_johnson',
                        help='If true, we use the johnson generator network. (default %(default)s). Please see '
                             'johnson_feedforward_net_util.py for more details.',
                        action='store_true')
    parser.set_defaults(use_johnson=False)
    parser.add_argument('--use_skip_noise_4', dest='use_skip_noise_4',
                        help='If true, we use the skip_noise_4 generator network (default %(default)s). Please see '
                             'skip_noise_4_feedforward_net.py for more details.',
                        action='store_true')
    parser.set_defaults(use_skip_noise_4=False)
    parser.add_argument('--model_save_dir', dest='model_save_dir',
                        help='The directory to save trained model and its checkpoints.',
                        metavar='MODEL_SAVE_DIR', default='model/feed_forward_example_1/')
    parser.add_argument('--from_screenshot',
                        dest='from_screenshot', help='If true, the content image is the screen shot',
                        action='store_true')
    parser.set_defaults(from_screenshot=False)
    parser.add_argument('--from_webcam',
                        dest='from_webcam', help='If true, the content image is the webcam', action='store_true')
    parser.set_defaults(from_webcam=False)
    return parser


def main():
    parser = build_parser()
    options = parser.parse_args()

    if not os.path.isfile(options.network):
        parser.error("Network %s does not exist. (Did you forget to download it?)" % options.network)
    if not os.path.isfile(options.model_save_dir + 'checkpoint'):
        parser.error("Pretrained model %s does not exist.)" % options.network)
    if not options.from_webcam or options.from_screenshot:
        parser.error("You must choose either getting the image from webcam or from screen shot." % options.network)

    style_images = [imread(style) for style in options.styles]

    # Start with the first one with 1.0 weight and 0.0 for all other ones.
    current_style_blend_weights = [1.0 if i == 0 else 0.0 for i,_ in enumerate(style_images)]
    one_hot_vector_container = n_style_feedforward_net.one_hot_vector_container(np.array([current_style_blend_weights]))

    plt.ion()
    fig, ax = plt.subplots()
    plt.subplots_adjust(left=0.25, bottom=0.25)
    ax.set_title("Real Time Neural Style")
    im = ax.imshow(np.zeros((options.height, options.width, 3)) + 128,vmin=0,vmax=255)  # Blank starting image
    axcolor = 'lightgoldenrodyellow'
    slider_axes = [plt.axes([0.25, 0.21 - i * 0.02, 0.65, 0.02], axisbg=axcolor) for i, style in enumerate(
        options.styles)]
    sliders = [Slider(slider_axes[i], style, 0.0, 1.0, valinit=current_style_blend_weights[i]) for i, style in enumerate(options.styles)]
    fig.show()
    im.axes.figure.canvas.draw()
    plt.pause(0.001)
    tstart = None

    def update(val):
        for i, slider in enumerate(sliders):
            current_style_blend_weights[i] = slider.val
        one_hot_vector_container.vec = np.array([current_style_blend_weights])

    for slider in sliders:
        slider.on_changed(update)


    for iteration, image in n_style_feedforward_net.style_synthesis_net(path_to_network=options.network,
                                                                        height=options.height, width=options.width,
                                                                        styles=style_images, iterations=None,
                                                                        batch_size=1,
                                                                        one_hot_vector_for_restore_and_generate=one_hot_vector_container,
                                                                        style_only=options.texture_synthesis_only,
                                                                        use_johnson=options.use_johnson,
                                                                        use_skip_noise_4=options.use_skip_noise_4,
                                                                        save_dir=options.model_save_dir,
                                                                        do_restore_and_generate=True,
                                                                        from_screenshot=options.from_screenshot,
                                                                        from_webcam=options.from_webcam):
        # We must do this clip step before we display the image. Otherwise the color will be off.
        image = np.clip(image, 0, 255).astype(np.uint8)
        if tstart is None:
            tstart = time.time()
        # Change the data in place instead of create a new window.
        ax.set_title(str(iteration))
        im.set_data(image)
        im.axes.figure.canvas.draw()
        plt.pause(0.001)
        print ('FPS:', iteration / (time.time() - tstart + 0.001))
    plt.ioff()
    plt.show()


if __name__ == '__main__':
    main()