# Axis Twist Compensation with dockable probe support
#
# Klipper's stock [axis_twist_compensation] calibration wizard is not
# compatible with dockable probes (see the Klipper Axis_Twist_Compensation
# documentation warning): it keeps the probe attached during the manual
# "paper touch" phase, so the paper touches the probe pin instead of the
# nozzle and the measured offsets are constant (the resulting compensation is
# silently zero after normalization).
#
# This plugin replaces the AXIS_TWIST_COMPENSATION_CALIBRATE command with a
# dockable probe aware wizard that:
#   1. activates the probe (klicky style dockable probes)
#   2. automatically probes every calibration point with the probe attached
#   3. docks the probe
#   4. performs the manual (nozzle, paper touch) measurements with the nozzle
#      as the lowest point of the toolhead
#   5. re-activates the probe
#   6. computes and saves the exact same compensation values as the stock
#      wizard (z_offsets = probe_z - nozzle_z, normalized around the mean)
#
# The stock [axis_twist_compensation] module is left in charge of applying the
# compensation to every probe result (probe:update_results hook and linear
# interpolation). This plugin only replaces the calibration wizard and adds a
# CLEAR_AXIS_TWIST_COMPENSATION command (stock Klipper has no way to clear the
# compensation from gcode).
#
# This plugin is installed by the Klippain install script as
# klippy/extras/axis_twist_compensation_dockable.py and is loaded from the
# [axis_twist_compensation_dockable] section. It must be defined AFTER the
# [axis_twist_compensation] section in the config so that it can take over the
# stock command registration.

from . import manual_probe, probe

DEFAULT_SAMPLE_COUNT = 3


class AxisTwistCompensationDockable:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        # All calibration parameters are read from the [axis_twist_compensation]
        # section so that there is a single source of truth (the per-size
        # software configs in Klippain define them).
        self.compensation = None
        self.probe = None
        self.lift_speed = None
        self.gcmd = None
        self.is_dockable = False

        self.current_axis = None
        self.auto_z = []
        self.manual_z = []
        self.current_point_index = 0
        self.bed_points = []
        self.test_points = []

        self.printer.register_event_handler("klippy:connect",
                                            self._handle_connect)
        self._register_gcode_handlers()

    def _handle_connect(self):
        self.compensation = self.printer.lookup_object(
            'axis_twist_compensation')
        self.probe = self.printer.lookup_object('probe', None)
        if self.probe is None:
            raise self.printer.config_error(
                "AXIS_TWIST_COMPENSATION requires [probe] to be defined")
        self.lift_speed = self.probe.get_probe_params()['lift_speed']

        # Detect dockable probes from the Klippain probe framework
        try:
            user_vars = self.printer.lookup_object('gcode_macro _USER_VARIABLES')
            probe_type = user_vars.variables.get('probe_type_enabled', '')
            self.is_dockable = probe_type in ('dockable', 'dockable_virtual')
        except Exception:
            self.is_dockable = False

    def _register_gcode_handlers(self):
        # Take over the stock command (the stock wizard is not dockable probe
        # compatible). register_command(name, None) unregisters the stock
        # handler so ours can take its place; it is a no-op if the stock
        # module was not loaded, in which case our wizard still works standalone.
        self.gcode.register_command('AXIS_TWIST_COMPENSATION_CALIBRATE', None)
        self.gcode.register_command(
            'AXIS_TWIST_COMPENSATION_CALIBRATE',
            self.cmd_AXIS_TWIST_COMPENSATION_CALIBRATE,
            desc=self.cmd_AXIS_TWIST_COMPENSATION_CALIBRATE_help)
        self.gcode.register_command('CLEAR_AXIS_TWIST_COMPENSATION',
                                    self.cmd_CLEAR_AXIS_TWIST_COMPENSATION)

    cmd_AXIS_TWIST_COMPENSATION_CALIBRATE_help = """
    Performs the X or Y axis twist calibration wizard
    Measure the probe z offset at n points along the axis,
    and calculate the axis twist compensation.
    Dockable probes are docked during the manual (nozzle) measurement phase.
    """

    def cmd_AXIS_TWIST_COMPENSATION_CALIBRATE(self, gcmd):
        self.gcmd = gcmd
        probe_x_offset, probe_y_offset, _ = self.probe.get_offsets(gcmd)
        sample_count = gcmd.get_int('SAMPLE_COUNT', DEFAULT_SAMPLE_COUNT)
        axis = gcmd.get('AXIS', 'X')

        if sample_count < 2:
            raise gcmd.error("SAMPLE_COUNT to probe must be at least 2")

        if axis == 'X':
            self.compensation.clear_compensations('X')
            if not all([self.compensation.calibrate_start_x,
                        self.compensation.calibrate_end_x,
                        self.compensation.calibrate_y]):
                raise gcmd.error(
                    "AXIS_TWIST_COMPENSATION for X axis requires "
                    "calibrate_start_x, calibrate_end_x and calibrate_y "
                    "to be defined")
            start_point = (self.compensation.calibrate_start_x,
                           self.compensation.calibrate_y)
            end_point = (self.compensation.calibrate_end_x,
                         self.compensation.calibrate_y)
            axis_range = end_point[0] - start_point[0]
        elif axis == 'Y':
            self.compensation.clear_compensations('Y')
            if not all([self.compensation.calibrate_start_y,
                        self.compensation.calibrate_end_y,
                        self.compensation.calibrate_x]):
                raise gcmd.error(
                    "AXIS_TWIST_COMPENSATION for Y axis requires "
                    "calibrate_start_y, calibrate_end_y and calibrate_x "
                    "to be defined")
            start_point = (self.compensation.calibrate_x,
                           self.compensation.calibrate_start_y)
            end_point = (self.compensation.calibrate_x,
                         self.compensation.calibrate_end_y)
            axis_range = end_point[1] - start_point[1]
        else:
            raise gcmd.error(
                "AXIS_TWIST_COMPENSATION_CALIBRATE: Invalid axis.")

        interval_dist = axis_range / (sample_count - 1)
        self.current_axis = axis

        # Calculate the bed points to measure and the test points to move to
        # so that the probe is aligned with the bed points.
        bed_points = []
        for i in range(sample_count):
            if axis == 'X':
                bed_points.append((start_point[0] + i * interval_dist,
                                   start_point[1]))
            else:
                bed_points.append((start_point[0],
                                   start_point[1] + i * interval_dist))
        test_points = [(x - probe_x_offset, y - probe_y_offset)
                       for x, y in bed_points]

        # Verify no other manual probe is in progress
        manual_probe.verify_no_manual_probe(self.printer)

        self.auto_z = []
        self.manual_z = []
        self.current_point_index = 0
        self.bed_points = bed_points
        self.test_points = test_points

        self._auto_probe_phase()

    def _move_helper(self, target_coordinates, override_speed=None):
        # Pad target coordinates
        target_coordinates = (target_coordinates[0], target_coordinates[1],
                              None) if len(target_coordinates) == 2 \
            else target_coordinates
        toolhead = self.printer.lookup_object('toolhead')
        speed = self.speed if target_coordinates[2] is None \
            else self.lift_speed
        speed = override_speed if override_speed is not None else speed
        toolhead.manual_move(target_coordinates, speed)

    @property
    def speed(self):
        return self.compensation.speed

    @property
    def horizontal_move_z(self):
        return self.compensation.horizontal_move_z

    def _auto_probe_phase(self):
        # Activate (attach) the probe for the automatic probing phase
        if self.is_dockable:
            self.gcode.run_script_from_command("ACTIVATE_PROBE")

        self.auto_z = []
        for index, test_point in enumerate(self.test_points):
            self.gcmd.respond_info(
                "AXIS_TWIST_COMPENSATION_CALIBRATE: Probing point %d of %d"
                % (index + 1, len(self.test_points)))
            # horizontal_move_z to prevent the probe triggering or hitting the bed
            self._move_helper((None, None, self.horizontal_move_z))
            # Move to the point to probe
            self._move_helper((test_point[0], test_point[1], None))
            # Probe the point
            pos = probe.run_single_probe(self.probe, self.gcmd)
            self.auto_z.append(pos.bed_z)

        # Dock the probe so the nozzle is the lowest point of the toolhead for
        # the manual (paper touch) measurements.
        if self.is_dockable:
            self.gcode.run_script_from_command("DEACTIVATE_PROBE")

        self._manual_probe_phase()

    def _manual_probe_phase(self):
        index = self.current_point_index
        self.gcmd.respond_info(
            "AXIS_TWIST_COMPENSATION_CALIBRATE: Manual measurement at point "
            "%d of %d (X:%.3f, Y:%.3f). Place a piece of paper on the bed and "
            "jog the nozzle down until it just touches it, then send ACCEPT."
            % (index + 1, len(self.bed_points),
               self.bed_points[index][0], self.bed_points[index][1]))
        # horizontal_move_z to prevent the nozzle hitting the bed
        self._move_helper((None, None, self.horizontal_move_z))
        # Move the nozzle over the bed point
        self._move_helper((self.bed_points[index][0],
                           self.bed_points[index][1], None))
        # Start the manual (nozzle) probe
        manual_probe.ManualProbeHelper(self.printer, self.gcmd,
                                       self._manual_probe_callback)

    def _manual_probe_callback(self, mpresult):
        if mpresult is None:
            # Probe was cancelled
            self.gcmd.respond_info(
                "AXIS_TWIST_COMPENSATION_CALIBRATE: Probe cancelled, "
                "calibration aborted")
            if self.is_dockable:
                self.gcode.run_script_from_command("ACTIVATE_PROBE")
            return
        self.manual_z.append(mpresult.bed_z)
        if self.current_point_index == len(self.bed_points) - 1:
            # End of calibration
            self._finalize_calibration()
        else:
            # Move to the next point
            self.current_point_index += 1
            self._manual_probe_phase()

    def _finalize_calibration(self):
        # Finalize the calibration process
        # Calculate z offsets (probe z minus manual nozzle z for each point)
        z_offsets = [self.auto_z[i] - self.manual_z[i]
                     for i in range(len(self.auto_z))]
        # Calculate average of results
        avg = sum(z_offsets) / len(z_offsets)
        # Subtract average from each result so that they are independent of
        # the probe z_offset
        results = [avg - x for x in z_offsets]
        # Save the config
        configfile = self.printer.lookup_object('configfile')
        values_as_str = ', '.join(["{:.6f}".format(x) for x in results])

        if self.current_axis == 'X':
            configfile.set('axis_twist_compensation', 'z_compensations',
                           values_as_str)
            configfile.set('axis_twist_compensation', 'compensation_start_x',
                           self.compensation.calibrate_start_x)
            configfile.set('axis_twist_compensation', 'compensation_end_x',
                           self.compensation.calibrate_end_x)
            self.compensation.z_compensations = results
            self.compensation.compensation_start_x = \
                self.compensation.calibrate_start_x
            self.compensation.compensation_end_x = \
                self.compensation.calibrate_end_x
        else:
            configfile.set('axis_twist_compensation', 'zy_compensations',
                           values_as_str)
            configfile.set('axis_twist_compensation', 'compensation_start_y',
                           self.compensation.calibrate_start_y)
            configfile.set('axis_twist_compensation', 'compensation_end_y',
                           self.compensation.calibrate_end_y)
            self.compensation.zy_compensations = results
            self.compensation.compensation_start_y = \
                self.compensation.calibrate_start_y
            self.compensation.compensation_end_y = \
                self.compensation.calibrate_end_y

        # Re-attach the probe before finishing
        if self.is_dockable:
            self.gcode.run_script_from_command("ACTIVATE_PROBE")

        self.gcmd.respond_info(
            "AXIS_TWIST_COMPENSATION state has been saved for the current "
            "session.  The SAVE_CONFIG command will update the printer config "
            "file and restart the printer.")
        self.gcmd.respond_info(
            "AXIS_TWIST_COMPENSATION_CALIBRATE: Calibration complete, "
            "offsets: %s, mean z_offset: %f" % (results, avg))

    def cmd_CLEAR_AXIS_TWIST_COMPENSATION(self, gcmd):
        axis = gcmd.get('AXIS', 'BOTH')
        configfile = self.printer.lookup_object('configfile')
        if axis == 'BOTH':
            self.compensation.clear_compensations()
            configfile.set('axis_twist_compensation', 'z_compensations', '')
            configfile.set('axis_twist_compensation', 'zy_compensations', '')
        elif axis in ('X', 'x'):
            self.compensation.clear_compensations('X')
            configfile.set('axis_twist_compensation', 'z_compensations', '')
        elif axis in ('Y', 'y'):
            self.compensation.clear_compensations('Y')
            configfile.set('axis_twist_compensation', 'zy_compensations', '')
        else:
            raise gcmd.error(
                "CLEAR_AXIS_TWIST_COMPENSATION: Invalid axis, use AXIS=X, "
                "AXIS=Y or no axis to clear everything.")
        gcmd.respond_info(
            "Axis twist compensation cleared for the current session. "
            "The SAVE_CONFIG command will update the printer config file "
            "and restart the printer.")


def load_config(config):
    return AxisTwistCompensationDockable(config)