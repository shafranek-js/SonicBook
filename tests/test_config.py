import unittest
import copy
from config import _deep_merge

class TestDeepMerge(unittest.TestCase):
    def test_defaults_not_dict(self):
        """If defaults is not a dict, it should return a deepcopy of override."""
        defaults = "not a dict"
        override = {"a": 1, "b": {"c": 2}}
        result = _deep_merge(defaults, override)
        self.assertEqual(result, override)
        self.assertIsNot(result, override)
        self.assertIsNot(result["b"], override["b"])

    def test_override_is_none_or_empty(self):
        """If override is None or empty, it should return a deepcopy of defaults."""
        defaults = {"a": 1, "b": {"c": 2}}

        # Test with None
        result_none = _deep_merge(defaults, None)
        self.assertEqual(result_none, defaults)
        self.assertIsNot(result_none, defaults)
        self.assertIsNot(result_none["b"], defaults["b"])

        # Test with empty dict
        result_empty = _deep_merge(defaults, {})
        self.assertEqual(result_empty, defaults)
        self.assertIsNot(result_empty, defaults)
        self.assertIsNot(result_empty["b"], defaults["b"])

    def test_flat_merge(self):
        """Simple flat dictionary merging."""
        defaults = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        expected = {"a": 1, "b": 3, "c": 4}
        result = _deep_merge(defaults, override)
        self.assertEqual(result, expected)

    def test_deep_merge(self):
        """Recursive merge of nested dictionaries."""
        defaults = {
            "a": 1,
            "nested": {
                "b": 2,
                "c": 3
            }
        }
        override = {
            "nested": {
                "c": 4,
                "d": 5
            },
            "e": 6
        }
        expected = {
            "a": 1,
            "nested": {
                "b": 2,
                "c": 4,
                "d": 5
            },
            "e": 6
        }
        result = _deep_merge(defaults, override)
        self.assertEqual(result, expected)

    def test_type_mismatch_override_with_primitive(self):
        """Overriding a dictionary with a primitive value."""
        defaults = {"nested": {"a": 1}}
        override = {"nested": 2}
        expected = {"nested": 2}
        result = _deep_merge(defaults, override)
        self.assertEqual(result, expected)

    def test_type_mismatch_override_with_dict(self):
        """Overriding a primitive value with a dictionary."""
        defaults = {"nested": 1}
        override = {"nested": {"a": 2}}
        expected = {"nested": {"a": 2}}
        result = _deep_merge(defaults, override)
        self.assertEqual(result, expected)

    def test_immutability(self):
        """Ensure that the merging process does not mutate the input dictionaries."""
        defaults = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        defaults_copy = copy.deepcopy(defaults)
        override_copy = copy.deepcopy(override)

        _deep_merge(defaults, override)

        self.assertEqual(defaults, defaults_copy)
        self.assertEqual(override, override_copy)

    def test_deep_copy_result_from_defaults(self):
        """Verify that nested objects from defaults are deep copied."""
        defaults = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = _deep_merge(defaults, override)

        # Modify the result
        result["a"]["b"] = 99

        # Ensure defaults is unchanged
        self.assertEqual(defaults["a"]["b"], 1)

    def test_deep_copy_result_from_override(self):
        """Verify that nested objects from override are deep copied."""
        defaults = {"a": 1}
        override = {"b": {"c": 2}}
        result = _deep_merge(defaults, override)

        # Modify the override
        override["b"]["c"] = 99

        # Ensure result is unchanged
        self.assertEqual(result["b"]["c"], 2)

if __name__ == "__main__":
    unittest.main()
