from pyVmomi import vim
from pyVim import connect
from .helpers import VmHelper
import time
# tests
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


# used by canvas script
class Machines:
    def __init__(self):
        # init helper
        self._vm_helper = VmHelper()

    @staticmethod
    def print_host_info(obj, host):
        try:
            summary = obj.summary
            config = summary.config
            if config.name == host:
                response = config.sslThumbprint
                status = "success"
            else:
                response = "Not able to fetch the information about the host"
                status = "error"

            _json  = {
                'res': response,
                'status': status
            }
            return _json
        except Exception as e:
            logger_message = f"Exception occurred while fetching information about the host: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': "Exception occurred while fetching information about the host." + str(e),
                'status': "error"
            }
            return _json

    # get_dc() function for delete and rename VM functions
    @staticmethod
    def get_dc(si, name):
        """
        TODO: optimize and add to common_params(), or inside helpers.py.
        Find out if this is a better way to search for DC
        """
        try:
            for dc in si.content.rootFolder.childEntity:
                if dc.name == name:
                    _json = {
                        'res': dc,
                        'status': "success"
                    }
                    return _json

            _json = {
                'res': 'Failed to find datacenter named ' + name,
                'status': "error"
            }
            logger_message = f"Failed to find datacenter {str(name)} object"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as e:
            logger_message = f"Exception occurred while fetching the datacenter object: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': "Exception occurred while fetching the datacenter." + str(e),
                'status': "error"
            }
            return _json

    # get_dc() function for delete and rename VM functions
    @staticmethod
    def get_vm(obj, vm_name):
        """
        TODO: optimize and add to common_params()
        or inside helpers.py
        """
        try:
            for i in range(len(obj)):
                vm_obj = obj[i]
                if vm_obj.config.name == vm_name and not vm_obj.config.template:
                    _json = {
                        'res': vm_obj,
                        'status': "success"
                    }
                    return _json

            _json = {
                'res': 'Failed to find the vm ' + vm_name,
                'status': "error"
            }

            logger_message = f"Failed to find VM {str(vm_name)} object"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as e:
            logger_message = f"Exception occurred while fetching the VM object: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': "Exception occurred while fetching the vm." + str(e),
                'status': "error"
            }
            return _json

    def create_vm(self, service_instance, vm_name, cpu, ram, guest_id, defaults):
        try:
            cpu = int(cpu)
            datacenter_name = defaults['data_center']
            vm_folder = defaults['folder']
            datastore_name = defaults['data_store_name']
            resource_pool = defaults['resource_pool']
            vm_version = defaults['vm_version']

            content = service_instance.RetrieveContent()

            if datacenter_name is not "":
                datacenter_response = self._vm_helper.get_obj(content, [vim.Datacenter], datacenter_name)
                if datacenter_response['status'] == "success":
                    datacenter = datacenter_response['res']
                else:
                    return datacenter_response
            else:
                datacenter = content.rootFolder.childEntity[0]

            if vm_folder is not None:
                folder_response = self._vm_helper.get_obj(content, [vim.Folder], vm_folder)
                if folder_response['status'] == "success":
                    folder = folder_response['res']
                else:
                    return folder_response
            else:
                folder = datacenter.vmFolder

            resource_pool_res = self._vm_helper.get_obj(content, [vim.ResourcePool], resource_pool)
            if resource_pool_res['status'] == "success":
                resource_pool = resource_pool_res['res']
            else:
                return resource_pool_res

            datastore_path = '[' + datastore_name + '] ' + vm_name

            # bare minimum VM shell, no disks. Feel free to edit
            vmx_file = vim.vm.FileInfo(logDirectory=None,
                                       snapshotDirectory=None,
                                       suspendDirectory=None,
                                       vmPathName=datastore_path)

            # convert GB to MB
            ram = ram*1024
            config = vim.vm.ConfigSpec(name=vm_name,
                                       memoryMB=ram,
                                       numCPUs=cpu,
                                       files=vmx_file,
                                       guestId=guest_id,
                                       version=vm_version)

            print("Creating VM {}...".format(vm_name))
            task = folder.CreateVM_Task(config=config, pool=resource_pool)
            task_res_cr = VmHelper.wait_for_tasks(service_instance, [task])
            if task_res_cr['status'] == "error":
                _json = {
                    'res': 'Exception occurred while creating ' + str(vm_name) + ', ' + str(task_res_cr['res']),
                    'status': "error"
                }
                return _json

            _json = {
                'res': str(vm_name) + ' created successfully.',
                'status': "success"
            }

            logger_message = f"The {vm_name} VM created successfully!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as e:
            logger_message = f"Exception occurred while Creating the VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while creating the VM.' + str(e),
                'status': "error"
            }
            return _json


    def clone_from_template(self, service_instance, vm_name, template_name, defaults):
        """
        Clone a VM from a template/VM, datacenter_name, vm_folder, datastore_name
        cluster_name, resource_pool, and power_on are all optional.

        :param defaults:
        :param template_name:
        :param vm_name:
        :param service_instance: ServiceInstance connection
        """

        try:
            # default parameters from DB
            datacenter_name = defaults['data_center']
            datastore_name = defaults['data_store_name']
            cluster_name = defaults['cluster_name']
            is_cluster = defaults['is_cluster']
            resource_pool = defaults['resource_pool']
            vm_folder = defaults['folder']


            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print("$$$$$$$$$$$$$$$$$$$$$$$$")
            print(vm_name)
            print("$$$$$$$$$$$$$$$$$$$$$$$$34")
            content = service_instance.RetrieveContent()


            # get the template object
            template_response = self._vm_helper.get_obj(content, [vim.VirtualMachine], template_name, True)
            if template_response['status'] == "success":
                print("here: template obj found: ", template_response)
                template = template_response['res']
            else:
                print("here: template obj not found: ", template_response)
                return template_response


            if is_cluster == 1:
                cluster_response = self._vm_helper.get_obj(content, [vim.ClusterComputeResource], cluster_name)
                if cluster_response['status'] == "success":
                    cluster = cluster_response['res']
                    resource_pool = cluster.resourcePool
                else:
                    return cluster_response
            else:

                # resource pool
                if resource_pool is not "NA":
                    resource_pool_res = self._vm_helper.get_obj(content, [vim.ResourcePool], resource_pool)
                    if resource_pool_res['status'] == "success":
                        resource_pool = resource_pool_res['res']
                    else:
                        return resource_pool
                else:
                    resource_pool_res = self._vm_helper.get_obj(content, [vim.ResourcePool], "Resources")
                    if resource_pool_res['status'] == "success":
                        resource_pool = resource_pool_res['res']
                    else:
                        return resource_pool
                    _json = {
                        "status": "error",
                        "res": "Resource pool not found while creating machine from template"
                    }
                    print(_json)

            print(resource_pool)

            # datacenter
            # datacenter = []
            # if datacenter_name is not "NA" and len(datacenter_name) > 0:
            #     for each_datacenter in datacenter_name:
            #         datacenter_response = self._vm_helper.get_obj(content, [vim.Datacenter], each_datacenter)
            #         if datacenter_response['status'] == "success":
            #             datacenter.append(datacenter_response['res'])
            #         else:
            #             return datacenter_response
            # else:
            #     datacenter = content.rootFolder.childEntity[0]


            # destination folder
            if vm_folder is not None:

                destfolder_response = self._vm_helper.get_obj(content, [vim.Folder], vm_folder)
                if destfolder_response['status'] == "success":

                    destfolder = destfolder_response['res']

                else:
                    return destfolder_response
            else:
                datacenter = content.rootFolder.childEntity[0]
                destfolder = datacenter.vmFolder


            vmconf = vim.vm.ConfigSpec()


            # Find the datastore
            # datastore = None
            # datastore_list = []
            # for each_ds in datastore_name:
            #     for datacenter in content.rootFolder.childEntity:
            #         if isinstance(datacenter, vim.Datacenter):
            #             for datastore_obj in datacenter.datastore:
            #                 if datastore_obj.name == each_ds:
            #                     datastore = datastore_obj
            #                     datastore_list.append(datastore)
            #                     break
            #         if datastore:
            #             break


            # If datastore is not found
            # if not datastore:
            #     print(f"Datastore '{datastore_name}' not found.")
            #     # Disconnect(si)
            #     # return

            # Prepare the clone specification
            clonespec = vim.vm.CloneSpec()
            clonespec.location = vim.vm.RelocateSpec(pool=resource_pool)
            # clonespec.location = vim.vm.RelocateSpec(folder=destfolder, datastore=datastore, pool=resource_pool)
            clonespec.powerOn = False  # Set to True if you want the VM powered on after cloning
            clonespec.template = False  # Make sure it's not a template
            # clonespec.customize = None  # Optional: Customize the VM if needed

            print("cloning VM...")
            print("cloning VM...")
            print("cloning VM...")
            print("cloning VM...")

            task = template.Clone(folder=destfolder, name=vm_name, spec=clonespec)

            # Monitor the task status
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(1)


            if task.info.state == vim.TaskInfo.State.success:
                res = {
                    "status": "success",
                    "res": vm_name + ' created successfully from the template.',
                }
                print(res)

                logger_message = f"The {vm_name} VM created successfully from template"
                logger.info(logger_message)
                audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

                return res
            else:

                res = {
                    "status": "error",
                    "res": 'Exception occurred while creating ' + str(vm_name) + ' from the template, ' + task.info.error
                }
                print(res)
                return res
        except Exception as vm_exception:
            logger_message = f"Exception occurred while creating/cloning the VM from template: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while creating the VM from template.' + str(vm_exception),
                'status': "error"
            }
            return _json



    def delete_vm(self, service_instance, vm_name, defaults):
        try:
            print("here: delete-vm defaults: ", vm_name, defaults)
            # datacenter_name = defaults['data_center']
            # host_name = defaults['host']
            # resource_pool = defaults['resource_pool']

            if isinstance(defaults["resource_pool"], list):
                str_resource_pool = defaults['resource_pool'][0]
            else:
                str_resource_pool = defaults['resource_pool']

            str_folder = defaults.get("folder", "")

            # ---------------Fetching VM object----------------
            # init helpers
            vm_helper = VmHelper()

            # Get the VM object
            vm_obj_response = vm_helper.get_vm_obj(vm_name, defaults['data_center'], defaults['host'],
                                                   str_resource_pool, str_folder, defaults['is_cluster'])

            print(f"here: delete-vm: vm_obj_response: {str(vm_obj_response)}")

            if vm_obj_response and vm_obj_response["status"] == "success" and vm_obj_response["res"] is not None:
                vm = vm_obj_response["res"]
            else:
                res = {"status": "error", "res": vm_obj_response["res"]}
                return res

            print(f"here: vm found: {str(vm)}")

            # -----------------------------------

            if format(vm.runtime.powerState) == "poweredOn":
                print("Attempting to power off {0}".format(vm.name))
                task = vm.PowerOffVM_Task()

                # Monitor the power-off task
                while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                    print("here: Monitor the power-off task ")
                    time.sleep(1)

                if task.info.state == vim.TaskInfo.State.success:
                    print("VM {} powered off successfully!".format(str(vm_name)))
                else:
                    print("Failed to power off VM: {}".format(task.info.error))
                    res = {
                        "status": "error",
                        "res": "Exception occurred while switching off the VM {}: {}".format(str(vm_name), task.info.error)
                    }
                    return res

            print(f"Destroying VM from vSphere. : {vm.name} ")
            task_res_del = vm.Destroy_Task()

            # Monitor the delete-vm task
            while task_res_del.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                print("here: Monitor the delete-vm task ")
                time.sleep(1)

            if task_res_del.info.state == vim.TaskInfo.State.success:
                print("VM {} deleted successfully!".format(str(vm_name)))
            else:
                print("Failed to delete VM: {}".format(task_res_del.info.error))
                res = {
                    "status": "error",
                    "res": "Exception occurred while deleting the VM {}: {}".format(str(vm_name), task.info.error)
                }
                return res

            _json = {
                'res': str(vm_name) + 'deleted successfully!',
                'status': "success"
            }

            logger_message = f"The {vm_name} VM deleted successfully!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as vm_exception:
            logger_message = f"Exception occurred while deleting the VM: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while deleting the VM.' + str(vm_exception),
                'status': "error"
            }
            print(_json)
            return _json

    
    
    def rename_vm(self, service_instance, vm_name, new_name, defaults):
        try:
            # default parameters from DB
            datacenter_name = defaults['data_center']
            host_name = defaults['esxi_host']
            resource_pool = defaults['resource_pool']

            # get DC
            dc_response = self.get_dc(service_instance, datacenter_name)
            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response

            # use DC, get host
            host = service_instance.content.searchIndex.FindChild(dc.hostFolder, host_name)

            # use host, get resource pool
            rs = service_instance.content.searchIndex.FindChild(host.resourcePool, resource_pool)

            # use resource pool, get VM
            vm_response = self.get_vm(rs.vm, vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            task = vm.Rename_Task(newName=new_name)
            task_res_rename = self._vm_helper.wait_for_tasks(service_instance, [task])
            if task_res_rename['status'] == "error":
                _json = {
                    'res': 'Exception occurred while renaming ' + str(vm_name) + ', ' + str(task_res_rename['res']),
                    'status': "error"
                }
                return _json

            _json = {
                'res': str(vm_name) + ' renamed successfully.',
                'status': "success"
            }

            logger_message = f"The {str(vm_name)} renamed successfully!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as unknown_exception:
            logger_message = f"Exception occurred while renaming the VM: {str(unknown_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while renaming the VM.' + str(unknown_exception),
                'status': "error"
            }
            return _json

    def edit_vm_settings(self, service_instance, vm_name, changes, defaults):
        try:
            # default parameters from DB
            datacenter_name = defaults['data_center']
            host_name = defaults['esxi_host']
            resource_pool = defaults['resource_pool']

            # get DC
            dc_response = self.get_dc(service_instance, datacenter_name)
            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response

            # use DC, get host
            host = service_instance.content.searchIndex.FindChild(dc.hostFolder, host_name)

            # use host, get resource pool
            rs = service_instance.content.searchIndex.FindChild(host.resourcePool, resource_pool)

            # use resource pool, get VM
            vm_response = self.get_vm(rs.vm, vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            vm_spec = vim.vm.ConfigSpec()

            # edit CPU of vm
            if "cpu" in changes:
                vm_spec.numCPUs = changes['cpu']

            # edit memory of vm
            if "ram" in changes:
                vm_spec.memoryMB = changes['ram'] * 1024

            task = vm.Reconfigure(vm_spec)
            task_res_edit = self._vm_helper.wait_for_tasks(service_instance, [task])
            if task_res_edit['status'] == "error":
                _json = {
                    'res': 'Exception occurred while editing ' + str(vm_name) + ', ' + str(task_res_edit['res']),
                    'status': "error"
                }
                return _json

            _json = {
                'res': str(vm_name) + ' edited successfully.',
                'status': "success"
            }

            logger_message = f"The {str(vm_name)} VM edited successfully!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json
        except Exception as unknown_exception:
            logger_message = f"Exception occurred while editing the VM: {str(unknown_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while editing the VM.' + str(unknown_exception),
                'status': "error"
            }
            return _json

    def open_browser_console(self, service_instance, vm_name, data_center, host, host_domain, resource_pool, vcenter_ip):
        try:
            serverguid = service_instance.content.about.instanceUuid
            sessionManager = service_instance.content.sessionManager
            sessionTicket = sessionManager.AcquireCloneTicket()
            thumbprint = ""
            content = service_instance.RetrieveContent()
            object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
            for obj in object_view.view:
                thumbprint_response = self.print_host_info(obj, host)
                if thumbprint_response['status'] == "success":
                    thumbprint = thumbprint_response['res']
                else:
                    return thumbprint_response

            object_view.Destroy()

            dc_response = self.get_dc(service_instance, data_center)
            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response

            host = service_instance.content.searchIndex.FindChild(dc.hostFolder, host)
            rs = service_instance.content.searchIndex.FindChild(host.resourcePool, resource_pool)
            vm_response = self.get_vm(rs.vm, vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                return vm_response

            if format(vm.runtime.powerState) != "poweredOn":
                task_power_on = vm.PowerOn()
                task_res_on = self._vm_helper.wait_for_task(task_power_on, "switching on machine : " + vm_name)
                if task_res_on['status'] == "error":
                    _json = {
                        'res': 'Exception occurred while switching on ' + str(vm_name) + ', ' + str(task_res_on['res']),
                        'status': "error"
                    }
                    return _json
            print(vm.runtime.powerState)
            vm_string = str(vm)
            vm_id = vm_string.replace("vim.VirtualMachine:", '')
            vm_id = vm_id.replace("'", '')

            ip = vcenter_ip

            url = "https://" + ip + "/ui/webconsole.html?vmId=" + vm_id + "&vmName=" + vm_name + \
                  "&serverGuid=" + serverguid + "&host=" + ip + "&sessionTicket=" + sessionTicket + "&thumbprint=" + thumbprint
                  # "&serverGuid=" + serverguid + "&host=" + host_domain + "&sessionTicket=" + sessionTicket + "&thumbprint=" + thumbprint
            # + "&locale=en-GB"

            _json = {
                'res': url,
                'status': "success"
            }

            logger_message = f"Successfully taken the browser console"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return _json['res']
        except Exception as unknown_exception:
            logger_message = f"Exception occurred while taking the console of VM: {str(unknown_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            _json = {
                'res': 'Exception occurred while taking the console.' + str(unknown_exception),
                'status': "error"
            }
            return _json


