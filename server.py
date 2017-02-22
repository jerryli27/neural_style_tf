#!/usr/bin/env python

"""
The overall server structure is mainly taken from https://github.com/pfnet/PaintsChainer
"""


from __future__ import absolute_import
import CGIHTTPServer, SimpleHTTPServer, BaseHTTPServer
import SocketServer

import os, sys
import base64
import json
import numpy as np

import argparse

from cgi import parse_header, parse_multipart
from urlparse import parse_qs
from io import open

# sys.path.append('./cgi-bin/wnet')
sys.path.append(u'./cgi-bin/paint_x2_unet')
import painter
from neural_style_slow_online import slow_stylize


class MyHandler(CGIHTTPServer.CGIHTTPRequestHandler):
    def __init__(self, req, client_addr, server):
        CGIHTTPServer.CGIHTTPRequestHandler.__init__(self, req, client_addr, server)

    def parse_POST(self):
        ctype, pdict = parse_header(self.headers[u'content-type'])
        pdict[u'boundary'] = str(pdict['boundary']).encode("utf-8")
        if ctype == u'multipart/form-data':
            postvars = parse_multipart(self.rfile, pdict)
        elif ctype == u'application/x-www-form-urlencoded':
            length = int(self.headers[u'content-length'])
            postvars = parse_qs(
                self.rfile.read(length),
                keep_blank_values=1)
        else:
            postvars = {}
        return postvars

    def do_POST(self):
        form = self.parse_POST()

        if u"id" in form:
            id_str = form[u"id"][0]
            id_str = id_str.decode()
        else:
            id_str = u"test"


        content_dir = None
        style_dirs = []
        output_dir = './static/images/out/'+id_str+'_0.jpg'
        if u"line" in form:
           bin1 = form[u"line"][0]
           bin1 = bin1.decode().split(u",")[1]
           bin1 = base64.b64decode(bin1.encode())
           content_dir = u"./static/images/line/"+id_str+u".png"
           fout1 = open (content_dir, u'wb')
           fout1.write (bin1)
           fout1.close()
        if u"style" in form:
            bin2 = form[u"style"][0]
            bin2 = bin2.decode().split(u",")[1]
            bin2 = base64.b64decode(bin2.encode())
            style_dirs.append(u"./static/images/style/" + id_str + u".png")
            fout2 = open(style_dirs[-1], u'wb')
            fout2.write(bin2)
            fout2.close()

        assert "mode" in form

        if form["mode"][0].decode() == "slow":
            current_image_dir = None
            for current_image_dir in slow_stylize(content_dir,style_dirs,output_dir):
                # # TODO: can it send multiple response to one request?? No...
                # content = str(
                #     "{ 'message':'Still generating' , 'Status':'200 OK','success':true , 'used':%s, 'output_dir':'%s'}"
                #     % (str(args.gpu), current_image_dir)).encode("UTF-8")
                # self.send_response(200)
                # self.send_header(u"Content-type", u"application/json")
                # self.send_header(u"Content-Length", len(content))
                # self.end_headers()
                # self.wfile.write(content)
                pass
            if current_image_dir is None:
                # TODO: Send error message instead of raising an error.
                raise AssertionError('Failed to do slow stylize.')
            else:
                content = str(
                    "{ 'message':'The command Completed Successfully' , 'Status':'200 OK','success':true , 'used':%s, 'output_dir':'%s'}"
                    % (str(args.gpu), current_image_dir)).encode("UTF-8")
                self.send_response(200)
                self.send_header(u"Content-type", u"application/json")
                self.send_header(u"Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)

        else:
            if form["mode"][0].decode() == "batch":
                p.batch_colorize(id_str)
            elif form["mode"][0].decode() == "single":
                if "style_weights" in form:
                    style_weights = form["style_weights"][0].split(',')
                    if len(style_weights) != 38:
                        print('incorrect style_weights format. resume to default')
                        style_weights = [1] + [0]* 37
                else:
                    style_weights = [1] + [0]* 37
                style_weights = np.array(style_weights, dtype=np.float32)
                if np.sum(style_weights) != 0:
                    style_weights = style_weights / (np.sum(style_weights))

                p.colorize(id_str,style_weights)
            else:
                raise AttributeError("Unacceptable input mode in post request")

            # TODO: add fail mode.
            content = str(
                "{ 'message':'The command Completed Successfully' , 'Status':'200 OK','success':true , 'used':" + str(
                    args.gpu) + "}").encode("UTF-8")
            self.send_response(200)
            self.send_header(u"Content-type", u"application/json")
            self.send_header(u"Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)


        return


parser = argparse.ArgumentParser(description=u'chainer line drawing colorization server')
parser.add_argument(u'--gpu', u'-g', type=int, default=-1,
                    help=u'GPU ID (negative value indicates CPU)')
parser.add_argument(u'--gpu_fraction', u'-gf', type=float, default=0.5,
                    help=u'Fraction of gpu memory to use. CPU mode is unaffected by this option.')
parser.add_argument(u'--port', u'-p', type=int, default=8000,
                    help=u'using port')
parser.add_argument(u'--host', u'-ho', default=u'localhost',
                    help=u'using host')
parser.add_argument(u'--save_dir', u'-sv', default=u'model/',
                    help=u'directory to trained feed forward network.')
args = parser.parse_args()

print u'GPU: {}'.format(args.gpu)

p = painter.Painter(save_dir=args.save_dir, gpu=args.gpu, gpu_fraction=args.gpu_fraction)

httpd = BaseHTTPServer.HTTPServer((args.host, args.port), MyHandler)
print u'serving at', args.host, u':', args.port
httpd.serve_forever()

"""
python server.py --gpu=0 --save_dir=model/feed_forward_first_38_imgs-1024 --host
"""