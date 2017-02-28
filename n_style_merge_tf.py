import argparse
import os
import numpy as np

from n_style_out_net import Stylizer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=u'Fast Neural Style server.')
    parser.add_argument(u'--main_checkpoint_path', u'-mcp',
                        help=u'directory to trained feed forward network.')
    parser.add_argument(u'--main_checkpoint_num_styles', type=int,
                        help=u'TODO')
    parser.add_argument(u'--style_checkpoint_paths', u'-scp', default=[], nargs='+',
                        help=u'directory to trained feed forward network.')
    parser.add_argument(u'--style_checkpoint_num_styles', default=[], nargs='+',
                        help=u'TODO')
    parser.add_argument(u'--save_npy_path', u'-snp', default=u'n_style_combined.npy',
                        help=u'directory to trained feed forward network.')
    parser.add_argument(u'--mat_dir', u'-mat', default=u'imagenet-vgg-verydeep-19.mat',
                        help=u'directory to vgg 19 net')
    
    args = parser.parse_args()
    num_styles = len(args.style_checkpoint_num_styles)
    assert num_styles == len(args.style_checkpoint_num_styles)

    stylizer = Stylizer(args.mat_dir,128,128,args.main_checkpoint_num_styles, use_johnson=True, save_dir=args.main_checkpoint_path, do_save_npy=True, npy_path='main.npy')
    del stylizer

    for i in range(num_styles):
        stylizer = Stylizer(args.mat_dir,128,128,int(args.style_checkpoint_num_styles[i]), use_johnson=True, save_dir=args.style_checkpoint_paths[i], do_save_npy=True, npy_path='style_%d.npy' %(i))
        del stylizer

    main_npy = np.load('main.npy').item()
    style_npys = [np.load('style_%d.npy' %(i)).item() for i in range(num_styles)]

    variable_names = main_npy.keys()

    for var_name in variable_names:
        if "/scale" in var_name or "/shift" in var_name or var_name == "input_style_placeholder":
            additional_vars = []
            for i in range(num_styles):
                additional_vars.append(style_npys[i][var_name])
            # Combine style variables.
            main_npy[var_name] = np.concatenate([main_npy[var_name]] + additional_vars, axis=1 if var_name == "input_style_placeholder" else 0)
            print('merged %s' %var_name)
    np.save(args.save_npy_path, main_npy)

    os.remove('main.npy')
    for i in range(num_styles):
        os.remove('style_%d.npy' % (i))

    print("Successfully combined npy files.")
