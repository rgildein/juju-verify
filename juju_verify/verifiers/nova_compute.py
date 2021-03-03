# Copyright 2021 Canonical Limited.
#
# This file is part of juju-verify.
#
# juju-verify is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# juju-verify is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see https://www.gnu.org/licenses/.
"""nova-compute verification."""
import json
import logging
import os

from juju_verify.verifiers.base import BaseVerifier, Result

logger = logging.getLogger()


class NovaCompute(BaseVerifier):
    """Implementation of verification checks for the nova-compute charm."""

    NAME = 'nova-compute'

    def check_no_running_vms(self) -> Result:
        """Check that none of the units have VMs running on them."""
        result = Result(success=True)
        instance_count_action = 'instance-count'
        instance_count_results = self.run_action_on_all(instance_count_action)

        for unit_id, action in instance_count_results.items():
            running_vms = int(self.data_from_action(action, 'instance-count'))
            if running_vms != 0:
                result.success = False
                result.reason += 'Unit {} is running {} VMs.' \
                                 '{}'.format(unit_id, running_vms, os.linesep)

        return result

    def check_no_empty_az(self) -> Result:
        """Check that removing units wont cause empty availability zone."""
        def is_active(node: dict) -> bool:
            return node['state'] == 'up' and node['status'] == 'enabled'
        result = Result(True)

        node_name_actions = self.run_action_on_all('node-name')
        target_nodes = [self.data_from_action(action, 'node-name')
                        for _, action in node_name_actions.items()]

        nova_unit = self.units[0].entity_id
        action = self.run_action_on_unit(nova_unit, 'list-compute-nodes')
        compute_nodes = json.loads(self.data_from_action(action,
                                                         'compute-nodes'))

        affected_zones = {node['zone'] for node in compute_nodes
                          if node['host'] in target_nodes}
        zones_after_change = {node['zone'] for node in compute_nodes
                              if node['host'] not in target_nodes and
                              is_active(node)}

        empty_zones = affected_zones - zones_after_change

        if empty_zones:
            result.success = False
            result.reason += 'Removing these units would leave ' \
                             'these availability zones empty: ' \
                             '{}'.format(empty_zones)

        return result

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected nova-compute units."""
        return self.aggregate_results(self.check_no_running_vms(),
                                      self.check_no_empty_az())

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected nova-compute units."""
        return self.verify_reboot()
