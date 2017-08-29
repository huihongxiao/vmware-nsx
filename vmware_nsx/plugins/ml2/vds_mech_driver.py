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

from neutron.db import api as db_api
from neutron.extensions import vlantransparent as vlan_ext
from neutron_lib.api.definitions import provider_net as pnet
from neutron_lib.plugins import directory
from neutron_lib.plugins.ml2 import api
from oslo_log import log
from oslo_utils import excutils

from vmware_nsx.common import utils as c_utils
from vmware_nsx.db import db as nsx_db
from vmware_nsx.dvs import dvs

LOG = log.getLogger(__name__)


class VDSMechDriver(api.MechanismDriver):

    """VMware VDS Mechaisam Driver for Neutron"""

    def initialize(self):
        LOG.info("Starting VDS mech driver")
        self.subscribe_registries()
        self._dvs = dvs.SingleDvsManager()

    def subscribe_registries(self):
        # TODO(xiaohhui): Anything we need to subscribe from Neutron server.
        pass

    @property
    def core_plugin(self):
        return directory.get_plugin()

    # TODO(xiaohhui): Just add placeholder methods here, will add more details
    # in following patches.
    def create_network_postcommit(self, context):
        # Get information from NetworkContext.
        plugin_context = context._plugin_context
        network = context.current
        self._dvs_create_network(plugin_context, network)

    def update_network_postcommit(self, context):
        # Do nothing, can be removed.
        pass

    def delete_network_postcommit(self, context):
        plugin_context = context._plugin_context
        network = context.current
        self._dvs_delete_network(plugin_context, network)

    def create_port_postcommit(self, context):
        pass

    def update_port_postcommit(self, context):
        pass

    def delete_port_postcommit(self, context):
        pass

    def bind_port(self, context):
        pass

    def _dvs_create_network(self, context, network):
        net_data = network

        if net_data['admin_state_up'] is False:
            LOG.warning("Network with admin_state_up=False are not yet "
                        "supported by this driver. Ignoring setting for "
                        "network %s", net_data.get('id'))

        if net_data.get(pnet.NETWORK_TYPE) == c_utils.NetworkTypes.PORTGROUP:
            # NOTE(xiaohhui): Don't intend to support this network type. As
            # it is impossible to have PORTGROUP network type in a integration
            # env.
            LOG.warning("Network type PORTGROUP not support!")
            return

        vlan_tag = 0
        if net_data.get(pnet.NETWORK_TYPE) == c_utils.NetworkTypes.VLAN:
            vlan_tag = net_data.get(pnet.SEGMENTATION_ID, 0)

        trunk_mode = False
        # vlan transparent can be an object if not set.
        if net_data.get(vlan_ext.VLANTRANSPARENT) is True:
            trunk_mode = True

        # TODO(xiaohhui): Add port group in VDS, the vlan id will be from
        # network data. But in hierarchical port binding, this might come
        # from a dynamic segment. So, this is a todo here.
        dvs_id = self._dvs_get_id(net_data)
        self._dvs.add_port_group(dvs_id, vlan_tag, trunk_mode=trunk_mode)

        try:
            # NOTE(xiaohhui): The Neutron segment binding in vds. Should take
            # care of in integration.
            nsx_db.add_network_binding(
                context.session, net_data['id'],
                net_data.get(pnet.NETWORK_TYPE),
                'dvs',
                vlan_tag)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception('Failed to create network')
                self._dvs.delete_port_group(dvs_id)

        # TODO(xiaohhui): Neutron will schedule dhcp in dhcp_rpc_agent_api. But
        # vmware-nsx has its own mechanism to schedule dhcp. Suppose neutron
        # can handle dhcp well, and after test, these 2 LOCs can be removed.
        # self.handle_network_dhcp_access(context, new_net,
        #                                 action='create_network')

    def _dvs_get_id(self, net_data):
        if net_data['name'] == '':
            return net_data['id']
        else:
            # Maximum name length is 80 characters. 'id' length is 36
            # maximum prefix for name is 43
            return '%s-%s' % (net_data['name'][:43], net_data['id'])

    def _dvs_delete_network(self, context, network):
        net_id = network['id']
        dvs_id = self._dvs_get_id(network)

        # TODO(xiaohhui): Try to remove it.
        with db_api.context_manager.writer.using(context):
            nsx_db.delete_network_bindings(context.session, net_id)

        try:
            self._dvs.delete_port_group(dvs_id)
        except Exception:
            LOG.exception('Unable to delete DVS port group %s', id)

        # TODO(xiaohhui): Neutron will schedule dhcp in dhcp_rpc_agent_api. But
        # vmware-nsx has its own mechanism to schedule dhcp. Suppose neutron
        # can handle dhcp well, and after test, these 1 LOC can be removed.
        # self.handle_network_dhcp_access(context, id, action='delete_network')
