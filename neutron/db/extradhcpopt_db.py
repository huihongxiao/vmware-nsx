# Copyright (c) 2013 OpenStack Foundation.
# All Rights Reserved.
#
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
#
# @author: Don Kehn, dekehn@gmail.com
#
import sqlalchemy as sa
from sqlalchemy import orm

from neutron.api.v2 import attributes
from neutron.db import db_base_plugin_v2
from neutron.db import model_base
from neutron.db import models_v2
from neutron.extensions import extra_dhcp_opt as edo_ext
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class ExtraDhcpOpt(model_base.BASEV2, models_v2.HasId):
    """Represent a generic concept of extra options associated to a port.

    Each port may have none to many dhcp opts associated to it that can
    define specifically different or extra options to DHCP clients.
    These will be written to the <network_id>/opts files, and each option's
    tag will be referenced in the <network_id>/host file.
    """
    port_id = sa.Column(sa.String(36),
                        sa.ForeignKey('ports.id', ondelete="CASCADE"),
                        nullable=False)
    opt_name = sa.Column(sa.String(64), nullable=False)
    opt_value = sa.Column(sa.String(255), nullable=False)
    __table_args__ = (sa.UniqueConstraint('port_id',
                                          'opt_name',
                                          name='uidx_portid_optname'),)

    # Add a relationship to the Port model in order to instruct SQLAlchemy to
    # eagerly load extra_dhcp_opts bindings
    ports = orm.relationship(
        models_v2.Port,
        backref=orm.backref("dhcp_opts", lazy='joined', cascade='delete'))


class ExtraDhcpOptMixin(object):
    """Mixin class to add extra options to the DHCP opts file
    and associate them to a port.
    """
    def _process_port_create_extra_dhcp_opts(self, context, port,
                                             extra_dhcp_opts):
        if not extra_dhcp_opts:
            return port
        with context.session.begin(subtransactions=True):
            for dopt in extra_dhcp_opts:
                db = ExtraDhcpOpt(
                    port_id=port['id'],
                    opt_name=dopt['opt_name'],
                    opt_value=dopt['opt_value'])
                context.session.add(db)
        return self._extend_port_extra_dhcp_opts_dict(context, port)

    def _extend_port_extra_dhcp_opts_dict(self, context, port):
        port[edo_ext.EXTRADHCPOPTS] = self._get_port_extra_dhcp_opts_binding(
            context, port['id'])

    def _get_port_extra_dhcp_opts_binding(self, context, port_id):
        query = self._model_query(context, ExtraDhcpOpt)
        binding = query.filter(ExtraDhcpOpt.port_id == port_id)
        return [{'opt_name': r.opt_name, 'opt_value': r.opt_value}
                for r in binding]

    def _update_extra_dhcp_opts_on_port(self, context, id, port,
                                        updated_port=None):
        # It is not necessary to update in a transaction, because
        # its called from within one from ovs_neutron_plugin.
        dopts = port['port'].get(edo_ext.EXTRADHCPOPTS)

        if dopts:
            opt_db = self._model_query(
                context, ExtraDhcpOpt).filter_by(port_id=id).all()
            # if there are currently no dhcp_options associated to
            # this port, Then just insert the new ones and be done.
            if not opt_db:
                with context.session.begin(subtransactions=True):
                    for dopt in dopts:
                        db = ExtraDhcpOpt(
                            port_id=id,
                            opt_name=dopt['opt_name'],
                            opt_value=dopt['opt_value'])
                        context.session.add(db)
            else:
                for upd_rec in dopts:
                    with context.session.begin(subtransactions=True):
                        for opt in opt_db:
                            if opt['opt_name'] == upd_rec['opt_name']:
                                if opt['opt_value'] != upd_rec['opt_value']:
                                    opt.update(
                                        {'opt_value': upd_rec['opt_value']})
                                break
                        # this handles the adding an option that didn't exist.
                        else:
                            db = ExtraDhcpOpt(
                                port_id=id,
                                opt_name=upd_rec['opt_name'],
                                opt_value=upd_rec['opt_value'])
                            context.session.add(db)

            if updated_port:
                edolist = self._get_port_extra_dhcp_opts_binding(context, id)
                updated_port[edo_ext.EXTRADHCPOPTS] = edolist

        return bool(dopts)

    def _extend_port_dict_extra_dhcp_opt(self, res, port):
        res[edo_ext.EXTRADHCPOPTS] = [{'opt_name': dho.opt_name,
                                       'opt_value': dho.opt_value}
                                      for dho in port.dhcp_opts]
        return res

    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORTS, ['_extend_port_dict_extra_dhcp_opt'])
