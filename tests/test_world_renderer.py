import unittest
from dimensional_sim.world.models import Cell
from dimensional_sim.world.renderer import Camera, Frame, camera_for, compose_layers, to_ansi, to_text


class RendererTests(unittest.TestCase):
    def test_all_six_layers_override_and_none_is_transparent(self):
        layers = [((Cell(str(i)),),) for i in range(6)]
        for top in range(6):
            frame = compose_layers(*layers[:top+1], ((None,),))
            self.assertEqual(frame[0][0].glyph, str(top))
        self.assertEqual(compose_layers(layers[0], ((Cell(" "),),))[0][0].glyph, " ")

    def test_both_colors_and_plain_output(self):
        frame = Frame(((Cell("@", "#010203", "#040506"),),), Camera(0,0,1,1))
        ansi = to_ansi(frame)
        self.assertIn("\x1b[38;2;1;2;3m", ansi)
        self.assertIn("\x1b[48;2;4;5;6m", ansi)
        self.assertEqual(to_text(frame), "@")
        self.assertTrue(ansi.endswith("\x1b[0m"))

    def test_camera_clamps_and_invalid_sizes_fail(self):
        self.assertEqual(camera_for(0,0,32,16,10,8), Camera(0,0,10,8))
        self.assertEqual(camera_for(31,15,32,16,10,8), Camera(22,8,10,8))
        self.assertEqual(camera_for(15,8,32,16,100,100), Camera(0,0,32,16))
        with self.assertRaises(ValueError): camera_for(0,0,32,16,0,8)
        with self.assertRaises(ValueError): camera_for(-1,0,32,16,10,8)
        with self.assertRaises(ValueError): compose_layers(((Cell("."),),), ((None,None),))
