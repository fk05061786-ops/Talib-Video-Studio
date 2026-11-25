"""Headless tests for builtin effects registry."""

import unittest
from src.core.builtin_effects import create_default_registry

class TestBuiltinEffects(unittest.TestCase):
    def test_default_registry_contents(self):
        registry = create_default_registry()
        # Should have video, audio, transition, text
        self.assertTrue(registry.has("brightness"))
        self.assertTrue(registry.has("gain"))
        self.assertTrue(registry.has("crossfade"))
        self.assertTrue(registry.has("title"))
        self.assertEqual(len(registry.list_all()), 5) # 2 video + 1 audio + 1 trans + 1 text

    def test_categories(self):
        registry = create_default_registry()
        self.assertEqual(len(registry.get_by_category("video")), 2)
        self.assertEqual(len(registry.get_by_category("audio")), 1)

if __name__ == "__main__":
    unittest.main()
