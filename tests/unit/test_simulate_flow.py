import unittest
from pathlib import Path

from ncplot7py.infrastructure.parsers.gcode_parser import GCodeParser
from ncplot7py.infrastructure.machines.generic_machine import GenericMachine


class TestSimulateFlow(unittest.TestCase):
    def test_parser_and_machine(self):
        sample = """
        G1 X1.0 Y2.0 Z0.0 F100
        G1 X2.5 Y3.5
        """
        parser = GCodeParser()
        nodes = parser.parse_text(sample)
        self.assertEqual(len(nodes), 2)

        machine = GenericMachine()
        points = machine.run(nodes)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].x, 1.0)
        self.assertEqual(points[1].x, 2.5)


if __name__ == "__main__":
    unittest.main()
