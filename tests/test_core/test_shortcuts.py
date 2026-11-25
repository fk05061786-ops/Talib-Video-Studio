"""Headless tests for keyboard shortcut resolution and dispatch."""

import unittest

from src.core.shortcuts import (
    SHORTCUTS,
    ShortcutAction,
    dispatch_shortcut,
    is_text_input_class,
    normalize_shortcut,
    resolve_shortcut,
)


class TestShortcutResolution(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_shortcut("control+shift+s"), "Ctrl+Shift+S")
        self.assertEqual(normalize_shortcut("shift+ctrl+s"), "Ctrl+Shift+S")
        self.assertEqual(normalize_shortcut("i"), "I")
        self.assertEqual(normalize_shortcut("space"), "Space")
        self.assertEqual(normalize_shortcut("shift+delete"), "Shift+Delete")
        self.assertEqual(normalize_shortcut(""), "")

    def test_resolve_by_key(self):
        self.assertEqual(resolve_shortcut("Space").action_id, "play_pause")
        self.assertEqual(resolve_shortcut("Left").action_id, "previous_frame")
        self.assertEqual(resolve_shortcut("Right").action_id, "next_frame")
        self.assertEqual(resolve_shortcut("Shift+Delete").action_id, "ripple_delete")
        self.assertEqual(resolve_shortcut("i").action_id, "set_in")

    def test_resolve_unknown(self):
        self.assertIsNone(resolve_shortcut("F23"))
        self.assertIsNone(resolve_shortcut(""))

    def test_context_and_custom_bindings(self):
        custom = (ShortcutAction("Space", "custom", "custom action", "custom"),)
        self.assertEqual(
            resolve_shortcut("Space", context="custom", bindings=custom).action_id,
            "custom",
        )
        found = resolve_shortcut("Space", context="custom")
        self.assertEqual(found.action_id, "play_pause")
        self.assertTrue(all(item.context == "nle" for item in SHORTCUTS))

    def test_no_duplicate_keys(self):
        keys = [item.key for item in SHORTCUTS]
        self.assertEqual(len(keys), len(set(keys)))


class TestShortcutDispatch(unittest.TestCase):
    def test_dispatch_calls_handler(self):
        calls = []
        action = resolve_shortcut("Space")
        self.assertTrue(
            dispatch_shortcut(action, {"play_pause": lambda: calls.append("ok")})
        )
        self.assertEqual(calls, ["ok"])

    def test_missing_handler(self):
        self.assertFalse(dispatch_shortcut(resolve_shortcut("Space"), {}))

    def test_handler_exception_propagates_to_caller(self):
        def broken():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            dispatch_shortcut(resolve_shortcut("Space"), {"play_pause": broken})

    def test_text_input_detection(self):
        for name in ("QLineEdit", "QTextEdit", "QSpinBox", "QDoubleSpinBox", "QComboBox"):
            self.assertTrue(is_text_input_class(name))
        for name in ("QGraphicsView", "QMainWindow", "TimelinePanel"):
            self.assertFalse(is_text_input_class(name))


if __name__ == "__main__":
    unittest.main()
