import unittest

from mcp.client.stdio import StdioServerParameters

from src.main import sub_mcp


class MainModuleTests(unittest.TestCase):
    def test_sub_mcp_is_configured_with_stdio_parameters(self):
        self.assertIn("supabase", sub_mcp)
        self.assertIsInstance(sub_mcp["supabase"], StdioServerParameters)


if __name__ == "__main__":
    unittest.main()
