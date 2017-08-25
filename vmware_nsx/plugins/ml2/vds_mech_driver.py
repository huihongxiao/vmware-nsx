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


from neutron_lib.plugins import directory
from neutron_lib.plugins.ml2 import api
from oslo_log import log

LOG = log.getLogger(__name__)


class VDSMechDriver(api.MechanismDriver):

    """VMware VDS Mechaisam Driver for Neutron"""

    def initialize(self):
        LOG.info("Starting VDS mech driver")
        self.subscribe_registries()

    def subscribe_registries(self):
        # TODO(xiaohhui): Anything we need to subscribe from Neutron server.
        pass

    @property
    def core_plugin(self):
        return directory.get_plugin()

    # TODO(xiaohhui): Just add placeholder methods here, will add more details
    # in following patches.
    def create_network_postcommit(self, context):
        pass

    def update_network_postcommit(self, context):
        pass

    def delete_network_postcommit(self, context):
        pass

    def create_port_postcommit(self, context):
        pass

    def update_port_postcommit(self, context):
        pass

    def delete_port_postcommit(self, context):
        pass

    def bind_port(self, context):
        pass
