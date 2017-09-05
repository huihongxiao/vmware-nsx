#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron.db import segments_db
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api as api
from neutron_lib.api.definitions import provider_net as pnet
from oslo_log import log

from vmware_nsx.dvs import dvs

LOG = log.getLogger(__name__)

# We assume that all leaf switch are in one physical network, which
# means they will all share one VLAN ID pool, which also means that
# tenant network under different leaf switch will have same VLAN ID.
PHYSICAL_NET = "physical_net"


class VDSMechDriver(api.MechanismDriver):

    """VMware VDS Mechaisam Driver for Neutron"""

    def initialize(self):
        LOG.info("Starting VDS mech driver")
        try:
            self._dvs = dvs.SingleDvsManager()
        except Exception:
            # backward compatibility
            self._dvs = dvs.DvsManager()

    def create_network_postcommit(self, context):
        # Get information from NetworkContext.
        plugin_context = context._plugin_context
        network = context.current
        if network.get(pnet.NETWORK_TYPE) != constants.TYPE_VXLAN:
            # Only handle vxlan for hierarchical port binding.
            return

        # Create dynamic vlan segment.
        # NOTE(xiaohhui): set the vlan id the same as vxlan id, so that
        # dhcp server can work without change. dhcp server will use the
        # network segmentation id as its vlan tag, and we are vlan underlying
        # same vlan tag/id can make the underlying network work.
        segment = {api.NETWORK_TYPE: constants.TYPE_VLAN,
                   api.PHYSICAL_NETWORK: PHYSICAL_NET,
                   api.SEGMENTATION_ID: network.get(pnet.SEGMENTATION_ID)}
        vlan_segment = context._plugin.type_manager.allocate_dynamic_segment(
            plugin_context, network['id'], segment)

        self._dvs_create_network(network, vlan_segment)

    def delete_network_precommit(self, context):
        plugin_context = context._plugin_context
        network = context.current
        # release dynamic segment id
        dynamic_segment = segments_db.get_dynamic_segment(
            plugin_context, network['id'], PHYSICAL_NET)
        if not dynamic_segment:
            return

        context._plugin.type_manager.release_dynamic_segment(
            plugin_context, dynamic_segment['id'])

    def delete_network_postcommit(self, context):
        network = context.current
        # Dynamic segment should be deleted along with network.
        self._dvs_delete_network(network)

    def bind_port(self, context):
        context.set_binding(context._segments_to_bind[0][api.ID], "dvs", {})

    def _dvs_create_network(self, network, vlan_segment):
        vlan_tag = vlan_segment.get(api.SEGMENTATION_ID)
        dvs_id = self._dvs_get_id(network)
        self._dvs.add_port_group(dvs_id, vlan_tag)

    def _dvs_get_id(self, net_data):
        if net_data['name'] == '':
            return net_data['id']
        else:
            # Maximum name length is 80 characters. 'id' length is 36
            # maximum prefix for name is 43
            return '%s-%s' % (net_data['name'][:43], net_data['id'])

    def _dvs_delete_network(self, network):
        dvs_id = self._dvs_get_id(network)
        try:
            self._dvs.delete_port_group(dvs_id)
        except Exception:
            LOG.exception('Unable to delete DVS port group %s', id)
