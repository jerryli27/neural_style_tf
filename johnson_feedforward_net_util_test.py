from johnson_feedforward_net_util import *


class JohnsonTest(tf.test.TestCase):
    def test_get_johnson_scale_offset_var(self):
        with self.test_session():
            batch_size = 1
            height = 24
            width = 32
            num_features = 2

            input_layer = tf.placeholder(dtype=tf.float32, shape=(batch_size, height, width, num_features))
            johnson_net = net(input_layer)
            scale_offset_var = get_johnson_scale_offset_var()
            self.assertEqual(len(scale_offset_var), 32)
            for var in scale_offset_var:
                if 'scale' in var.name or 'shift' in var.name:
                    continue
                else:
                    raise AssertionError

if __name__ == '__main__':
    tf.test.main()
