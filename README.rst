====================================
VMware integrated with 3rd-party SDN
====================================

This forked repository will provide solution to integrate VMware with
3rd-party SDN solution in an OpenStack enviroment.

Problems Description
====================

VMware has its own well-known SDN product, NSX. NSX works well with or
without OpenStack. To use NSX with OpenStack, Github repository
vmware-nsx_ provides plugins to integrate NSX with OpenStack Neutron.

.. _vmware-nsx: https://github.com/openstack/vmware-nsx

Like most pure sofeware SDN products, NSX can be used in a greenfield
or a brownfield. The case in greenfield is much easier.

For brownfield, how dose VMware products co-work with existing
networking facilities? If the existing facilities just provides an IP
network, then NSX can build SDN on top of that. An overlay VXLAN will
be built and some virtual networking devices will be created. It is a
common use case and it is where software SDNs live nowadays.

But what if the existing networking facilities are some SDN devices
already? I mean, customer already has a hardware SDN solution, and
customer doesn't want to throw away these *expensive* hardware SDN
devices. All he/she wants to do, is to just use VMware virtualization
products. How can VMware products work with 3rd-party SDN solution?

Plus, customer wants to use OpenStack as IaaS platform. VMware has its
own OpenStack product(VMware Integrated OpenStack), but it is all about
integrating VMware products into OpenStack. It seems like VIO can't
solve the issue above.

So, in a nutshell, customer wants to use his/her existing hardware SDN
solution as well as VMware products. And customer wants to use OpenStack
to manage its IaaS. How can we satisfy customer this time?

Proposed Change
===============

Before explain the solution, I would like to go through the so called
"hardware SDN solution" a little bit.

In a pure software SDN solution, things are built in software in
Operation System, like OpenFlow in OpenvSwitch, iptables and etc. In a
hardware SDN solution, things are built in networking hardware boxes,
like leaf switch, spine switch, or some other hardware. Hardware SDN
solution usually has good performance verse a pure software solution,
because of dedicated hardware or usage of ASIC or some other magic
things.

Take a spine-leaf network architecture as example, the VTEP(VxLAN
Tunnel Endpoint) are build at leaf switch. And VTEP usually changes
VLAN packets to VXLAN packets. So the southbound network of VTEP is
usually VLAN networks.

VMware provides the ablity to do Virtual Switch VLAN Tagging, VMware
managed VM can send normal Ethernet frame to Virtual Switch, and
Virtual Switch can send VLAN Tagged frame to Physical Switch.

So, if the VLAN Tagged frame can be sent to leaf switch, which has VTEP
in it, the frame can be encapsulated to VxLAN packet and sent to
underlay network for transmission.

So, the feasible integration solution might looks like::

              +-------+      +-------+
        +-----+ spine +------+ spine +----+
        |     +-------+      +-------+    |
        |          |            |         |
        |          |VXLAN       |         |
     +------+   +------+   +------+   +------+
     | leaf/|   | leaf/|   | leaf/|   | leaf/|
     | VTEP |   | VTEP |   | VTEP |   | VTEP |
     +------+   +------+   +------+   +------+
                  |
                  |VLAN
            +-------------+
            |     |       |
            | +---------+ |
            | | vSwitch | |
            | +---------+ |
            |    |        |
            | +----+      |
            | | VM |      |
            | +----+      |
            |             |
            |     ESXi    |
            +-------------+

This might reminds you of the Cisco ACI with VMware VDS integration,
where the Cisco APIC will call vCenter API to create VMware VDS.
Details can be found at reference_.

.. _reference: https://www.cisco.com/c/en/us/solutions/collateral/data-center-virtualization/application-centric-infrastructure/white-paper-c11-731961.html

To accomplish similar things in OpenStack, this repository will use
OpenStack Neutron to call the 3rd-party SDN controller and vCenter API.

Several things need to be considered.

#. The VLAN Tag from vSwitch should be passed to VTEP(or leaf switch), so
   that the VTEP can build its VLAN-VxLAN mapping table.
#. Creating a Neutron network should both create VDS in VMWare and
   logical network in 3rd-party SDN.
#. ML2 port binding should be taken care of, to make the VM created by
   OpenStack have a feasible network in such architecture.
#. VM migration should be take cared of.

For now, the vmware-nsx project only provides core plugin for Neutron
server, while the ML2 plugin became a de-facto way for SDN integrating
with Neutron server. We can assume 3rd-party SDN already has Neutron ML2
mechanism driver. The first problem in integration will be how to make
vmware-nsx core plugin work with 3rd-party SDN's ML2 mech_driver.

There will be 2 solutions:
#. Change vmware-nsx core plugin to ML2 mech_driver. And do the
   integration under Neutron ML2 framework.
#. Add ML2 framework to vmware-nsx core plugin, and add 3rd-party SDN's
   mech_driver in this framework.

Anyway, the management framework will look like::

    +--------------------------------------+
    |  OpenStack Neutron Server            |
    |                                      |
    |                                      |
    |  +------------+   +----------------+ |
    |  | VDS driver |   | 3rd SDN driver | |
    |  +------------+   +----------------+ |
    +--------------------------------------+


Workflow
========

Create network
--------------

#. User triggers creating network
#. OpenStack Neutron calls 3rd-SDN driver to create logical network in
   3rd-SDN.
#. OpenStack Neutron calls VDS driver to create VLAN port group in
   vCenter.
#. OpenStack Neutron gets the VLAN id from VMware VDS, and sends the
   VLAN ID to 3rd-SDN to build the VLAN-VxLAN mapping.


Boot VM
-------

#. User triggers booting VM.
#. Nova creates VM.
#. Nova calls Neutron to do port-binding.
#. Neutron pass the actual host to 3rd-SDN to let it know which leaf
   switch manages the VM.


Migrate VM
----------

Similar to boot VM, I will come back with more details.
