#!/usr/bin/env python
from general_util import *
import n_style_out_net


class Painter(object):
    def __init__(self, save_dir, gpu=0, gpu_fraction = 0.5, mat_dir = 'imagenet-vgg-verydeep-19.mat'):

        print u"start"
        self.root = u"./static/images/"
        self.batchsize = 1
        self.outdir = self.root + u"out/"
        self.painter = n_style_out_net.Stylizer(mat_dir,128,128,38, use_johnson=True, save_dir=save_dir,gpu_id=gpu, gpu_fraction=gpu_fraction)
        print u"load model"


    def colorize(self, id_str,style_weights):
        one_hot_style_vector = np.array([style_weights])
        output = self.painter.stylize(os.path.join('./static/images/line/', id_str + '.png'), one_hot_style_vector)
        imsave(self.outdir + id_str + u"_" + unicode(0) + u".jpg", output[0])


if __name__ == u'__main__':
    painter = Painter(None)
