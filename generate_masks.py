"""
This file is for generating random masks to be used by the feed forward neural style network.
Code is mainly taken from Dmitry's github https://github.com/DmitryUlyanov/online-neural-doodle
"""

import argparse

import numpy as np
import scipy.misc
from joblib import Parallel, delayed
from skimage.filters.rank import median
from skimage.morphology import disk
from skimage.transform import resize
from sklearn.cluster import KMeans
from sklearn.preprocessing import OneHotEncoder

import diamond_square as DS

parser = argparse.ArgumentParser()

parser.add_argument(
    '--n_colors', type=int, help='How many distinct colors does mask have.')
parser.add_argument('--height', help='Height of the generated mask.')
parser.add_argument('--width', help='Width of the generated mask.')
parser.add_argument(
    '--out_dir', default='random_masks/', help='Where to store generated mask images.')
parser.add_argument(
    '--n_jobs', type=int, default=4, help='Number of worker threads.')
parser.add_argument(
    '--n_masks', type=int, default=1000, help='Number of worker threads.')

args = parser.parse_args()

n_colors = args.n_colors

# get shape
dims = (int(args.height), int(args.width))


def generate():
    np.random.seed(None)
    ohe = OneHotEncoder(sparse=False)

    hmap = np.array(DS.diamond_square((200, 200), -1, 1, 0.35))
    + np.array(DS.diamond_square((200, 200), -1, 1, 0.55))
    + np.array(DS.diamond_square((200, 200), -1, 1, 0.75))

    hmap_flatten = np.array(hmap).ravel()[:, None]
    kmeans = KMeans(n_clusters=n_colors, random_state=0).fit(hmap_flatten)
    labels_hmap = kmeans.predict(hmap_flatten)[:, None]

    # Back to rectangular
    labels_hmap = labels_hmap.reshape([hmap.shape[0], hmap.shape[1]])
    labels_hmap = median(labels_hmap.astype(np.uint8), disk(5))
    labels_hmap = resize(labels_hmap, dims, order=0, preserve_range=True)

    labels_hmap = ohe.fit_transform(labels_hmap.ravel()[:, None])

    # Reshape
    hmap_masks = labels_hmap.reshape([dims[0], dims[1], n_colors])
    hmap_masks = hmap_masks.transpose([2, 0, 1])

    return hmap_masks


# Generate doodles

gen_masks = Parallel(n_jobs=args.n_jobs)(delayed(generate)()
                                         for i in range(args.n_masks))

# Save
for i, mask in enumerate(gen_masks):
    for j in range(n_colors):
        mask_rgb = np.transpose(np.repeat(np.array([mask[j,:,:]]), 3, axis=0),(1,2,0))
        scipy.misc.imsave('%strain_mask_%d_%d.png' % (args.out_dir, i, j), mask_rgb)

