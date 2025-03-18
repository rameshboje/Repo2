from pyVmomi import vim, vmodl
from .helpers import VmHelper
from .machines import Machines
import sys
import os

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'


class Networks:
    # init helper
    _vm_helper = VmHelper()
    _machine_helper = Machines()

    def add_nic(self, service_instance, vm_name, port_group):
        try:
            print("....adding nic.....")
            content = service_instance.RetrieveContent()

            vm_response = self._vm_helper.get_obj(content, [vim.VirtualMachine], vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            network_response = self._vm_helper.get_obj(content, [vim.Network], port_group)
            if network_response['status'] == "success":
                network = network_response['res']
            else:
                return network_response

            spec = vim.vm.ConfigSpec()

            # add Switch here
            dev_changes = []
            switch_spec = vim.vm.device.VirtualDeviceSpec()
            switch_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            switch_spec.device = vim.vm.device.VirtualVmxnet3()

            switch_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            switch_spec.device.backing.useAutoDetect = True
            switch_spec.device.backing.deviceName = network.name
            switch_spec.device.backing.network = network
            switch_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            switch_spec.device.connectable.startConnected = True
            switch_spec.device.connectable.connected = True

            dev_changes.append(switch_spec)

            spec.deviceChange = dev_changes
            task = vm.ReconfigVM_Task(spec=spec)

            task_res_nic = self._vm_helper.wait_for_task(task, "adding nic")
            if task_res_nic['status'] == "error":
                _json = {
                    'res': 'Exception occurred while adding the NIC to ' + str(vm_name) + ', ' + str(task_res_nic['res']),
                    'status': "error"
                }
                return _json

            json_ = {
                "status": "success",
                "res": "NIC added successfully to " + str(vm_name)
            }

            logger_message = f"NIC added successfully to {str(vm_name)} VM "
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as exp:
            logger_message = f"Exception occurred while adding the NIC to the VM: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while adding the NIC to the vm.' + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

        # except Exception as e:
        #     response_messages = 'Exception occurred: Unable to add NIC for vm ' + str(e)
        #     json_ = {
        #         'res': response_messages,
        #         'status': "error"
        #     }
        #     return json_
            # exc_type, exc_obj, exc_tb = sys.exc_info()
            # print(".......add nic exception........")
            # print(exc_type.__name__)
            # print(">>>>>>>>>>>>")
            # # print(type(sys.exc_info()))
            # # print(sys.exc_info())
            # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            # print(exc_type, fname, exc_tb.tb_lineno)
            # print('NIC - Exception!: ' + str(e))
            # return 'Failed: Unable to add NIC'

    def edit_nic(self, service_instance, nic_id, port_group_name, vm_name):
        try:
            content = service_instance.RetrieveContent()

            vm_response = self._vm_helper.get_obj(content, [vim.VirtualMachine], vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            network_response = self._vm_helper.get_obj(content, [vim.Network], port_group_name)
            if network_response['status'] == "success":
                network = network_response['res']
            else:
                return network_response

            nic_label = 'Network adapter ' + str(nic_id)

            virtual_nic_device_response = self._vm_helper.get_nic_by_name(vm, vm_name, nic_label)
            if virtual_nic_device_response['status'] == "success":
                virtual_nic_device = virtual_nic_device_response['res']
            else:
                return virtual_nic_device_response

            nic_spec = vim.vm.device.VirtualDeviceSpec()
            nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            nic_spec.device = virtual_nic_device

            if network:
                print("Changing PortGroup to: ", network.name)
                nic_spec.device.backing.network = network
                nic_spec.device.backing.deviceName = network.name
                # nic_spec.device.connectable.startConnected = True
                # nic_spec.device.backing.useAutoDetect = True
                nic_spec.device.connectable.connected = True

                # Apply change to VM
                config_spec = vim.vm.ConfigSpec(deviceChange=[nic_spec])
                task = vm.ReconfigVM_Task(config_spec)
                task_res_edit = self._vm_helper.wait_for_task(task, "editing nic")
                if task_res_edit['status'] == "error":
                    _json = {
                        'res': 'Exception occurred while editing the NIC of ' + str(vm_name) + ', ' + str(task_res_edit['res']),
                        'status': "error"
                    }
                    return _json
            json_ = {
                "status": "success",
                "res": "NIC edited successfully to " + vm_name
            }

            logger_message = f"NIC edited successfully to {str(vm_name)} VM "
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as exp:
            logger_message = f"Exception occurred while updating the NIC of the VM: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while editing the NIC of the vm.' + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

        # except Exception as e:
        #     response_messages = 'Exception occurred: Unable to edit NIC for vm ' + str(e)
        #     json_ = {
        #         'res': response_messages,
        #         'status': "error"
        #     }
        #     return json_

    def delete_nic(self, service_instance, vm_name, nic_index, defaults):
        try:
            # default parameters from DB
            datacenter_name = defaults['data_center']
            host_name = defaults['esxi_host']
            resource_pool = defaults['resource_pool']

            # get DC
            dc_response = self._machine_helper.get_dc(service_instance, datacenter_name)
            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response

            # use DC, get host and resource pool
            # use resource pool, get VM
            host = service_instance.content.searchIndex.FindChild(dc.hostFolder, host_name)
            rs = service_instance.content.searchIndex.FindChild(host.resourcePool, resource_pool)
            vm_response = self._machine_helper.get_vm(rs.vm, vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            # delete NIC
            nic_prefix_label = 'Network adapter '
            nic_label = nic_prefix_label + str(nic_index)
            virtual_nic_device = None
            for dev in vm.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualEthernetCard) \
                        and dev.deviceInfo.label == nic_label:
                    virtual_nic_device = dev

            if not virtual_nic_device:
                json_ = {
                    "status": "error",
                    "res": "Virtual " + str(nic_label) + " could not be found for " + vm_name
                }
                return json_

            virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()
            virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
            virtual_nic_spec.device = virtual_nic_device

            spec = vim.vm.ConfigSpec()
            spec.deviceChange = [virtual_nic_spec]
            task = vm.ReconfigVM_Task(spec=spec)
            task_res_del = self._vm_helper.wait_for_tasks(service_instance, [task])
            if task_res_del['status'] == "error":
                _json = {
                    'res': 'Exception occurred while deleting the NIC from ' + str(vm_name) + ', ' + str(task_res_del['res']),
                    'status': "error"
                }
                return _json

            json_ = {
                "status": "success",
                "res": "NIC deleted successfully from " + vm_name
            }

            logger_message = f"NIC deleted successfully from {str(vm_name)} VM "
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as e:
            logger_message = f"Exception occurred while deleting the NIC from the VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while deleting the NIC from vm.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    # not being used at this moment
    # this function will be used in future version
    def ip_assign(self, service_instance, vm_name,host_name, ip, default_values,type,username=None, password=None):
        try:
            
            content = service_instance.RetrieveContent()
            vm = self._vm_helper.get_obj(content, [vim.VirtualMachine], vm_name)

            if "folder" in default_values:
                vm_folder = default_values['folder']
            else:
                vm_folder = None


            print("##################3nkn")
            print("##################3nkn")
            print("##################3nkn")
            print("##################3nkn")
            print(default_values["folder"])
            print("##################3nkn")
            arr_resource_pools = default_values["resource_pool"] if "resource_pool" in default_values else []

            # Find the VM by name
            vm = None
            for datacenter in content.rootFolder.childEntity:
                print(datacenter)
                if isinstance(datacenter, vim.Datacenter):
                    for each_entry in datacenter.vmFolder.childEntity:

                        if vm_folder is not None and len(vm_folder) > 2:
                            if isinstance(each_entry, vim.Folder) and each_entry.name == vm_folder:

                                for child in each_entry.childEntity:
                                    print(child.name)
                                    if isinstance(child, vim.VirtualMachine) and child.name == vm_name and not child.config.template:
                                        vm = child
                                        print(dir(vm))
                                        break

                        else:
                            if isinstance(each_entry, vim.VirtualMachine) and each_entry.name == vm_name and not each_entry.config.template:
                                vm = each_entry
                                break  # Exit the folder loop

                if vm:
                    break

            # If VM is not found
            if not vm:
                res = {
                    "status": "error",
                    "res": f"VM '{vm_name}' not found."
                }
                print(res)
                return res


            # get DC
            # dc_response = self._machine_helper.get_dc(service_instance, default_values['data_center'])
            #
            # if dc_response['status'] == "success":
            #     dc = dc_response['res']
            # else:
            #     return dc_response

            # use DC, get host
            # host = service_instance.content.searchIndex.FindChild(dc.hostFolder, default_values['esxi_host'])


            guest_map = vim.vm.customization.AdapterMapping()
            guest_map.adapter = vim.vm.customization.IPSettings()

            """Static IP Configuration"""
            guest_map.adapter.ip = vim.vm.customization.FixedIp()
            guest_map.adapter.ip.ipAddress = ip
            guest_map.adapter.subnetMask = default_values['subnet']
            guest_map.adapter.gateway = default_values['gateway']
            guest_map.adapter.dnsServerList = default_values['dns']
            # guest_map.adapter.dnsDomain = domain

            # DNS settings
            globalip = vim.vm.customization.GlobalIPSettings()

            if type == "NA":
                _json = {
                    'res': 'Exception occurred while assign the IP to ' + str(vm_name) + ', ' + "No information regarding the OS of the machine",
                    'status': "error"
                }
                return _json

            # Hostname settings
            if type == "Linux":
            # for Linux
                ident = vim.vm.customization.LinuxPrep()
                ident.domain = default_values['domain']
                ident.hostName = vim.vm.customization.FixedName()
                hostname = host_name.replace(" ", "")
                ident.hostName.name = hostname.lower()

            if type == "Windows":
                # for windows
                p = password.split("/")
                usrname = username.split("/")
                ident = vim.vm.customization.Sysprep()
                ident.guiUnattended = vim.vm.customization.GuiUnattended()
                ident.guiUnattended.autoLogon = True  # the machine does not auto-logon
                ident.guiUnattended.password = vim.vm.customization.Password()
                ident.guiUnattended.password.value = p[0]
                ident.guiUnattended.password.plainText = True  # the password is not encrypted

                ident.guiUnattended.autoLogonCount = 1
                ident.userData = vim.vm.customization.UserData()
                ident.userData.fullName = usrname[0]
                ident.userData.orgName = "PurpleRange"
                ident.userData.computerName = vim.vm.customization.FixedName()
                ident.userData.computerName.name = host_name.lower()
                # ident.userData.computerName.name = host_name.lower()
                ident.identification = vim.vm.customization.Identification()

            customspec = vim.vm.customization.Specification()
            customspec.nicSettingMap = [guest_map]
            customspec.globalIPSettings = globalip
            customspec.identity = ident

            print("Reconfiguring VM Networks . . .")
            task = vm.Customize(spec=customspec)

            # Wait for Network Reconfigure to complete
            task_res_ip = self._vm_helper.wait_for_task(task, "config task")
            if task_res_ip['status'] == "error":
                _json = {
                    'res': 'Exception occurred while assign the IP to ' + str(vm_name) + ', ' + str(task_res_ip['res']),
                    'vm_obj': vm,
                    'status': "error"
                }
                return _json
            

            # power on the clone machine
            if format(vm.runtime.powerState) != "poweredOn":
                print("Attempting to power on {0}".format(vm.name))
                task = vm.PowerOnVM_Task()
                task_res_po = self._vm_helper.wait_for_tasks(service_instance, [task])
                if task_res_po['status'] == "error":
                    _json = {
                        'res': 'Exception occurred while switching off ' + str(vm_name) + ', ' + str(task_res_po['res']),
                        'status': "error"
                    }
                    return _json

            json_ = {
                "status": "success",
                "res": "IP Address assigned successfully to " + vm_name
            }

            logger_message = f"IP Address assigned successfully to {str(vm_name)} VM "
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as e:
            logger_message = f"Exception occurred while assigning the ip address to the VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while assigning the ip address ' + vm_name + ", " + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_


class Switches:
    @staticmethod
    def create_vswitch(host_network, vss_name, num_ports):
        try:
            vss_spec = vim.host.VirtualSwitch.Specification()
            vss_spec.numPorts = num_ports
            host_network.AddVirtualSwitch(vswitchName=vss_name, spec=vss_spec)
            print("vSwitch created  ", vss_name)
            json_ = {
                'res': "vSwitch created " + vss_name,
                'status': "success"
            }

            logger_message = f"Switch created successfully {str(vss_name)}"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as exp:
            logger_message = f"Exception occurred while creating the switch: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while creating the vSwitch ' + vss_name + ", " + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def create_port_group(host_network, pg_name, vss_name):
        try:
            port_group_spec = vim.host.PortGroup.Specification()
            port_group_spec.name = pg_name
            port_group_spec.vlanId = 0
            port_group_spec.vswitchName = vss_name

            security_policy = vim.host.NetworkPolicy.SecurityPolicy()
            security_policy.allowPromiscuous = True
            security_policy.forgedTransmits = True
            security_policy.macChanges = False

            port_group_spec.policy = vim.host.NetworkPolicy(security=security_policy)

            host_network.AddPortGroup(portgrp=port_group_spec)
            print("PortGroup created ", pg_name)
            json_ = {
                'res': "Port Group created " + pg_name,
                'status': "success"
            }

            logger_message = f"PortGroup created successfully {str(pg_name)}"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as exp:
            logger_message = f"Exception occurred while creating the PortGroup: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while creating the PortGroup ' + pg_name + ", " + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def del_host_switch(host, switch_name):
        try:
            host.configManager.networkSystem.RemoveVirtualSwitch(switch_name)
            json_ = {
                'res': "Host switch deleted " + switch_name,
                'status': "success"
            }

            logger_message = f"Host switch deleted successfully {str(switch_name)}"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as exp:
            logger_message = f"Exception occurred while deleting the host switch: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while deleting the host switch ' + switch_name + ", " + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    def main(self, method, service_instance, host_name, switch_name, num_ports=None, port_group_name=None):
        try:
            # retrieve content
            # init helper
            content = service_instance.RetrieveContent()
            vm_helper = VmHelper()

            # get host name/ip
            host_response = vm_helper.get_obj(content, [vim.HostSystem], host_name)
            if host_response['status'] == "success":
                host = host_response['res']
            else:
                return host_response

            if method is 'create':
                host_network = host.configManager.networkSystem

                # create switch
                v_switch_res = self.create_vswitch(host_network, switch_name, num_ports)
                if v_switch_res['status'] == "error":
                    return v_switch_res

                # create port group
                port_group_res = self.create_port_group(host_network, port_group_name, switch_name)
                if port_group_res['status'] == "error":
                    return port_group_res

            if method is 'delete':
                delete_res = self.del_host_switch(host, switch_name)
                return delete_res

            # on success
            json_ = {
                "status": "success",
                "res": "Switch created successfully " + switch_name
            }

            logger_message = f"Switch created successfully {str(switch_name)}"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))
            
            return json_
        except Exception as e:
            logger_message = f"Exception occurred while working with virtual switch: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while working with virtual switch.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_


