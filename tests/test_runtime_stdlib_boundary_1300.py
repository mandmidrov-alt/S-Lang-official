import unittest

from slang.stdlib_runtime import execute_registered_stdlib, registered_stdlib_effect


class RuntimeStdlibBoundaryTests(unittest.TestCase):
    def test_registered_pure_call(self):
        handled, value = execute_registered_stdlib("abs_number", [-4])
        self.assertTrue(handled)
        self.assertEqual(value, 4)
        self.assertEqual(registered_stdlib_effect("abs_number"), "pure")

    def test_registered_io_call(self):
        handled, value = execute_registered_stdlib("platform_name", [])
        self.assertTrue(handled)
        self.assertTrue(isinstance(value, str) and value)
        self.assertEqual(registered_stdlib_effect("platform_name"), "IO")

    def test_unknown_function_is_not_handled(self):
        handled, value = execute_registered_stdlib("does_not_exist", [])
        self.assertFalse(handled)
        self.assertIsNone(value)
        self.assertIsNone(registered_stdlib_effect("does_not_exist"))

    def test_argument_count_is_normalized(self):
        with self.assertRaisesRegex(TypeError, "abs_number expects 1 argument"):
            execute_registered_stdlib("abs_number", [])

    def test_runtime_error_is_normalized(self):
        with self.assertRaisesRegex(RuntimeError, "sqrt failed"):
            execute_registered_stdlib("sqrt", ["not-a-number"])


if __name__ == "__main__":
    unittest.main()
