import unittest
from unittest.mock import mock_open, patch

from ncplot7py.domain.cnc_state import CNCState
from ncplot7py.domain import machines
from ncplot7py.domain.machines import FANUC_GENERIC_CONFIG, MachineConfig, get_machine_config
from ncplot7py.infrastructure.machines.base_stateful_control import HANDLER_REGISTRY, UniversalConfigDrivenCanal


class TestMachineSetup(unittest.TestCase):
    def test_unknown_machine_name_falls_back_to_generic_config(self):
        config = get_machine_config("DOES_NOT_EXIST")

        self.assertIs(config, FANUC_GENERIC_CONFIG)
        self.assertEqual(config.name, "FANUC_GENERIC")

    def test_cnc_state_defaults_to_generic_machine_config(self):
        state = CNCState()

        self.assertIs(state.machine_config, FANUC_GENERIC_CONFIG)
        self.assertEqual(state.machine_config.name, "FANUC_GENERIC")

    def test_initial_plane_comes_from_machine_default_plane(self):
        custom_turn_mill = MachineConfig(
            name="TEST_TURN_MILL_G19",
            control_type="FANUC",
            variable_pattern=r'#(\d+)',
            variable_prefix='#',
            tool_range=(0, 99),
            machine_type="TURN_MILL",
            default_plane="G19",
            supported_gcode_groups=("motion",),
        )
        state = CNCState(machine_config=custom_turn_mill)

        canal = UniversalConfigDrivenCanal("C1", init_state=state)

        self.assertEqual(canal._state.extra["g_group_16_plane"], "Y_Z")

    def test_machine_config_can_define_rapid_feed_rate(self):
        custom_turn = MachineConfig(
            name="TEST_TURN_RAPID",
            control_type="FANUC",
            variable_pattern=r'#(\d+)',
            variable_prefix='#',
            tool_range=(0, 99),
            machine_type="TURN",
            supported_gcode_groups=("motion",),
            rapid_feed_rate=1200.0,
        )

        self.assertEqual(custom_turn.rapid_feed_rate, 1200.0)

    def test_load_machine_configs_prefers_package_local_config(self):
        mocked_open = mock_open(read_data='{}')

        with patch("ncplot7py.domain.machines.os.path.exists", return_value=True), patch(
            "builtins.open", mocked_open
        ):
            machines.load_machine_configs()

        package_config_path = machines.os.path.join(
            machines.os.path.dirname(machines.__file__), '..', 'config', 'machines.json'
        )
        mocked_open.assert_called_once_with(package_config_path, 'r', encoding='utf-8')

    def test_load_machine_configs_falls_back_to_legacy_config(self):
        mocked_open = mock_open(read_data='{}')

        with patch("ncplot7py.domain.machines.os.path.exists", return_value=False), patch(
            "builtins.open", mocked_open
        ):
            machines.load_machine_configs()

        legacy_config_path = machines.os.path.join(
            machines.os.path.dirname(machines.__file__), '..', '..', '..', 'config', 'machines.json'
        )
        mocked_open.assert_called_once_with(legacy_config_path, 'r', encoding='utf-8')

    def test_star_machine_group_aliases_are_registered(self):
        self.assertEqual(
            HANDLER_REGISTRY["spindle_speed"],
            ("ncplot7py.domain.handlers.modal", "ModalHandler"),
        )
        self.assertEqual(
            HANDLER_REGISTRY["wait_code"],
            ("ncplot7py.domain.handlers.modal", "ModalHandler"),
        )


if __name__ == '__main__':
    unittest.main()