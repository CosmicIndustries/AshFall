import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ashfall_perception import image_observation, system_observation


class PerceptionTests(unittest.TestCase):
    def test_system_observation_shape(self):
        obs = system_observation()
        self.assertEqual(obs["schema"], "ashfall.perception.system.v1")
        self.assertIn("cpu", obs)
        self.assertIn("memory", obs)
        self.assertIn("thermal", obs)

    def test_image_observation_shape(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow unavailable")
        with TemporaryDirectory() as td:
            path = Path(td) / "sample.png"
            Image.new("RGB", (16, 8), (128, 64, 32)).save(path)
            obs = image_observation(path)
            self.assertEqual(obs["schema"], "ashfall.perception.vision.v1")
            self.assertEqual(obs["image"]["width"], 16)
            self.assertEqual(obs["image"]["height"], 8)
            self.assertRegex(obs["source"]["sha256"], r"^[0-9a-f]{64}$")
            json.dumps(obs)


if __name__ == "__main__":
    unittest.main()
