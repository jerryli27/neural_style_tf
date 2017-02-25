import argparse
import numpy as np

import painter

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=u'Fast Neural Style server.')
    parser.add_argument(u'--main_npy_path', u'-mnp', default=u'n_style.npy',
                        help=u'directory to trained feed forward network.')
    parser.add_argument(u'--style_npy_paths', u'-snp', default=[],
                        help=u'directory to trained feed forward network.')
    parser.add_argument(u'--save_npy_path', u'-mnp', default=u'n_style_combined.npy',
                        help=u'directory to trained feed forward network.')
    args = parser.parse_args()

    p = painter.Painter(num_styles=args.num_styles, save_dir=args.save_dir)

    main_npy = np.load(args.main_npy_path)
    style_npys = [np.load(style_npy_path) for style_npy_path in args.style_npy_path]
    num_styles = len(style_npys)

    variable_names = main_npy.keys()

    for var_name in variable_names:
        if var_name.endswith("scale") or var_name.endswith("shift") or var_name == "input_style_placeholder":
            additional_vars = []
            for i in range(num_styles):
                additional_vars.append(style_npys[i][var_name])
            # Combine style variables.
            main_npy[var_name] = np.concatenate([main_npy[var_name]] + additional_vars, axis=1 if var_name == "input_style_placeholder" else 0)
    np.save(args.save_npy_path, main_npy)
    print("Successfully combined npy files.")