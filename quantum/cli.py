# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Nicira Networks, Inc.
# Copyright 2011 Citrix Systems
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
# @author: Somik Behera, Nicira Networks, Inc.
# @author: Brad Hall, Nicira Networks, Inc.

import Cheetah.Template as cheetah_template
import httplib
import logging as LOG
import json
import socket
import sys
import urllib

from client import Client
from manager import QuantumManager
from optparse import OptionParser
from quantum.api.views.networks import ViewBuilder as NetworkBuilder
from quantum.api.views.ports import ViewBuilder as PortBuilder

FORMAT = "json"
CLI_TEMPLATE = "../quantum/cli_output.template"
#TODO(salvatore-orlando): do proper logging!

def prepare_output(cmd, tenant_id, response):
    """ Fills a cheetah template with the response """
    #add command and tenant to response for output generation
    response['cmd'] = cmd
    response['tenant_id'] = tenant_id
    template_file = open(CLI_TEMPLATE).read()
    output = str(cheetah_template.Template(template_file,
                                           searchList=response))
    return output    

def list_nets(manager, *args):
    tenant_id = args[0]
    networks = manager.get_all_networks(tenant_id)
    builder=NetworkBuilder()
    nw_list = [builder.build(network, net_detail=True, port_detail=False)['network']
               for network in networks]
    res = dict(networks=nw_list)    
    output = prepare_output("list_nets", tenant_id, res)
    print output


def api_list_nets(client, *args):
    tenant_id = args[0]
    res = client.list_networks()
    output = prepare_output("list_nets", tenant_id, res)
    print output


def create_net(manager, *args):
    tenant_id, name = args
    new_net_id = manager.create_network(tenant_id, name)['net-id']
    output = prepare_output("create_net", tenant_id,
                            dict(network_id=new_net_id))
    print output


def api_create_net(client, *args):
    tenant_id, name = args
    data = {'network': {'net-name': name}}
    new_net_id = None
    try:
        res = client.create_network(data)
        new_net_id = res["networks"]["network"]["id"]
    except Exception as ex:
        status_code = None
        message = None
        #Retrieve dict at 1st element of tuple at last argument
        if ex.args and isinstance(ex.args[-1][0],dict):
            status_code = ex.args[-1][0].get('status_code', None)
            message = ex.args[-1][0].get('message', None)
        print "Failed to create network: %s" % status_code or '<missing>'
        print "Error message:%s" % message or '<missing>'
        return
    output = prepare_output("create_net", tenant_id,
                            dict(network_id=new_net_id))
    print output


def delete_net(manager, *args):
    tenant_id, network_id = args
    manager.delete_network(tenant_id, network_id)
    output = prepare_output("delete_net", tenant_id,
                            dict(network_id=network_id))
    print output


def api_delete_net(client, *args):
    tenant_id, network_id = args
    try:
        client.delete_network(network_id)
        output = prepare_output("delete_net", tenant_id,
                            dict(network_id=network_id))
        print output
    except Exception, e:
        print "Failed to delete network"
        LOG.error("Failed to delete network: %s" % e)


def detail_net(manager, *args):
    tid, nid = args
    iface_list = manager.get_network_details(tid, nid)
    output = prepare_output("detail_net", tenant_id,
                            dict(network=iface_list))
    #TODO(salvatore-orlando): delete here
    print "Remote Interfaces on Virtual Network:%s\n" % nid
    for iface in iface_list:
        print "\tRemote interface:%s" % iface


def api_detail_net(client, *args):
    tenant_id, network_id = args
    try:
        res = client.list_network_details(network_id)["networks"]["network"]
    except Exception, e:
        LOG.error("Failed to get network details: %s" % e)
        return
    try:
        ports = client.list_ports(network_id)
    except Exception, e:
        LOG.error("Failed to list ports: %s" % e)
        return

    res['ports'] = ports
    for port in ports["ports"]:
        att_data = client.list_port_attachments(network_id, port['id'])
        port['attachment'] = att_data["attachment"]

    output = prepare_output("detail_net", tenant_id,
                            dict(network=res))
    print output


def rename_net(manager, *args):
    tid, nid, name = args
    manager.rename_network(tid, nid, name)
    print "Renamed Virtual Network with ID:%s" % nid


def api_rename_net(client, *args):
    tid, nid, name = args
    data = {'network': {'net-name': '%s' % name}}
    try:
        res = client.update_network(nid, data)
    except Exception, e:
        LOG.error("Failed to rename network %s: %s" % (nid, e))
        return
    LOG.debug(res)
    print "Renamed Virtual Network with ID:%s" % nid


def list_ports(manager, *args):
    tid, nid = args
    ports = manager.get_all_ports(tid, nid)
    print "Ports on Virtual Network:%s\n" % nid
    for port in ports:
        print "\tVirtual Port:%s" % port["port-id"]


def api_list_ports(client, *args):
    tid, nid = args
    try:
        ports = client.list_ports(nid)
    except Exception, e:
        LOG.error("Failed to list ports: %s" % e)
        return

    LOG.debug(ports)
    print "Ports on Virtual Network:%s\n" % nid
    for port in ports["ports"]:
        print "\tVirtual Port:%s" % port["id"]


def create_port(manager, *args):
    tid, nid = args
    new_port = manager.create_port(tid, nid)
    print "Created Virtual Port:%s " \
          "on Virtual Network:%s" % (new_port, nid)


def api_create_port(client, *args):
    tid, nid = args
    try:
        res = client.create_port(nid)
    except Exception, e:
        LOG.error("Failed to create port: %s" % e)
        return
    new_port = res["ports"]["port"]["id"]
    print "Created Virtual Port:%s " \
          "on Virtual Network:%s" % (new_port, nid)


def delete_port(manager, *args):
    tid, nid, pid = args
    manager.delete_port(tid, nid, pid)
    LOG.info("Deleted Virtual Port:%s " \
          "on Virtual Network:%s" % (pid, nid))


def api_delete_port(client, *args):
    tid, nid, pid = args
    try:
        res = client.delete_port(nid, pid)
    except Exception, e:
        LOG.error("Failed to delete port: %s" % e)
        return
    LOG.info("Deleted Virtual Port:%s " \
          "on Virtual Network:%s" % (pid, nid))
    print "Deleted Virtual Port:%s " \
          "on Virtual Network:%s" % (pid, nid)


def detail_port(manager, *args):
    tid, nid, pid = args
    port_detail = manager.get_port_details(tid, nid, pid)
    print "Virtual Port:%s on Virtual Network:%s " \
          "contains remote interface:%s" % (pid, nid, port_detail)


def api_detail_port(client, *args):
    tid, nid, pid = args
    try:
        port = client.list_port_details(nid, pid)["ports"]["port"]
    except Exception, e:
        LOG.error("Failed to get port details: %s" % e)
        return

    id = port["id"]
    attachment = port["attachment"]
    LOG.debug(port)
    print "Virtual Port:%s on Virtual Network:%s " \
          "contains remote interface:%s" % (pid, nid, attachment)


def plug_iface(manager, *args):
    tid, nid, pid, vid = args
    manager.plug_interface(tid, nid, pid, vid)
    print "Plugged remote interface:%s " \
      "into Virtual Network:%s" % (vid, nid)


def api_plug_iface(client, *args):
    tid, nid, pid, vid = args
    try:
        data = {'port': {'attachment-id': '%s' % vid}}
        res = client.attach_resource(nid, pid, data)
    except Exception, e:
        LOG.error("Failed to plug iface \"%s\" to port \"%s\": %s" % (vid,
          pid, output))
        return
    LOG.debug(res)
    print "Plugged interface \"%s\" to port:%s on network:%s" % (vid, pid, nid)


def unplug_iface(manager, *args):
    tid, nid, pid = args
    manager.unplug_interface(tid, nid, pid)
    print "UnPlugged remote interface " \
      "from Virtual Port:%s Virtual Network:%s" % (pid, nid)


def api_unplug_iface(client, *args):
    tid, nid, pid = args
    try:
        res = client.detach_resource(nid, pid)
    except Exception, e:
        LOG.error("Failed to unplug iface from port \"%s\": %s" % (pid, e))
        return
    LOG.debug(res)
    print "Unplugged interface from port:%s on network:%s" % (pid, nid)


commands = {
  "list_nets": {
    "func": list_nets,
    "api_func": api_list_nets,
    "args": ["tenant-id"]},
  "create_net": {
    "func": create_net,
    "api_func": api_create_net,
    "args": ["tenant-id", "net-name"]},
  "delete_net": {
    "func": delete_net,
    "api_func": api_delete_net,
    "args": ["tenant-id", "net-id"]},
  "detail_net": {
    "func": detail_net,
    "api_func": api_detail_net,
    "args": ["tenant-id", "net-id"]},
  "rename_net": {
    "func": rename_net,
    "api_func": api_rename_net,
    "args": ["tenant-id", "net-id", "new-name"]},
  "list_ports": {
    "func": list_ports,
    "api_func": api_list_ports,
    "args": ["tenant-id", "net-id"]},
  "create_port": {
    "func": create_port,
    "api_func": api_create_port,
    "args": ["tenant-id", "net-id"]},
  "delete_port": {
    "func": delete_port,
    "api_func": api_delete_port,
    "args": ["tenant-id", "net-id", "port-id"]},
  "detail_port": {
    "func": detail_port,
    "api_func": api_detail_port,
    "args": ["tenant-id", "net-id", "port-id"]},
  "plug_iface": {
    "func": plug_iface,
    "api_func": api_plug_iface,
    "args": ["tenant-id", "net-id", "port-id", "iface-id"]},
  "unplug_iface": {
    "func": unplug_iface,
    "api_func": api_unplug_iface,
    "args": ["tenant-id", "net-id", "port-id"]}, }

def help():
    print "\nCommands:"
    for k in commands.keys():
        print "    %s %s" % (k,
          " ".join(["<%s>" % y for y in commands[k]["args"]]))


def build_args(cmd, cmdargs, arglist):
    args = []
    orig_arglist = arglist[:]
    try:
        for x in cmdargs:
            args.append(arglist[0])
            del arglist[0]
    except Exception, e:
        LOG.error("Not enough arguments for \"%s\" (expected: %d, got: %d)" % (
          cmd, len(cmdargs), len(orig_arglist)))
        print "Usage:\n    %s %s" % (cmd,
          " ".join(["<%s>" % y for y in commands[cmd]["args"]]))
        return None
    if len(arglist) > 0:
        LOG.error("Too many arguments for \"%s\" (expected: %d, got: %d)" % (
          cmd, len(cmdargs), len(orig_arglist)))
        print "Usage:\n    %s %s" % (cmd,
          " ".join(["<%s>" % y for y in commands[cmd]["args"]]))
        return None
    return args


if __name__ == "__main__":
    usagestr = "Usage: %prog [OPTIONS] <command> [args]"
    parser = OptionParser(usage=usagestr)
    parser.add_option("-l", "--load-plugin", dest="load_plugin",
      action="store_true", default=False,
      help="Load plugin directly instead of using WS API")
    parser.add_option("-H", "--host", dest="host",
      type="string", default="127.0.0.1", help="ip address of api host")
    parser.add_option("-p", "--port", dest="port",
      type="int", default=9696, help="api poort")
    parser.add_option("-s", "--ssl", dest="ssl",
      action="store_true", default=False, help="use ssl")
    parser.add_option("-v", "--verbose", dest="verbose",
      action="store_true", default=False, help="turn on verbose logging")

    options, args = parser.parse_args()

    if options.verbose:
        LOG.basicConfig(level=LOG.DEBUG)
    else:
        LOG.basicConfig(level=LOG.WARN)

    if len(args) < 1:
        parser.print_help()
        help()
        sys.exit(1)

    cmd = args[0]
    if cmd not in commands.keys():
        LOG.error("Unknown command: %s" % cmd)
        help()
        sys.exit(1)

    args = build_args(cmd, commands[cmd]["args"], args[1:])
    if not args:
        sys.exit(1)
    LOG.debug("Executing command \"%s\" with args: %s" % (cmd, args))
    if not options.load_plugin:
        client = Client(options.host, options.port, options.ssl,
                        args[0], FORMAT)
        if "api_func" not in commands[cmd]:
            LOG.error("API version of \"%s\" is not yet implemented" % cmd)
            sys.exit(1)
        commands[cmd]["api_func"](client, *args)
    else:
        quantum = QuantumManager()
        manager = quantum.get_plugin()
        commands[cmd]["func"](manager, *args)
    sys.exit(0)
