import time
import ssl
from pyVim import connect
from pyVmomi import vim, vmodl
from django.conf import settings
from settingspage.models import VsphereDetails
import atexit
import requests

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'


class VmHelper:

    def vm_login(self, no_ssl=True):

        try:

            esxi_creds = list(
                VsphereDetails.objects.filter(enabled="enabled").values('server_ip', 'username', 'password'))

            if len(esxi_creds) == 1:

                for ele in esxi_creds:
                    server_ip = ele['server_ip']
                    user = ele['username']
                    password = ele['password']

            elif len(esxi_creds) > 1:
                logger_message = f"Error while logging in(login) into vSphere: More than 1 esxi server is enabled"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)
                return {'error': 'More than 1 esxi server is enabled.'}

            else:
                logger_message = f"Error while logging in(login) into vSphere: Please add details of esxi server. No server found"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)
                return {'error': 'Please add details of esxi server. No server found'}

            if no_ssl is True:
                # Disabling SSL certificate verification
                # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                # context.verify_mode = ssl.CERT_NONE
                # service_instance = connect.SmartConnectNoSSL(host=server_ip, user=user, pwd=password)

                # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                # context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                # context.check_hostname = False
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                context.verify_mode = ssl.CERT_NONE
                service_instance = connect.SmartConnect(host=server_ip, user=user, pwd=password, sslContext=context)

            else:
                service_instance = connect.SmartConnect(host=server_ip, user=user, pwd=password)

            # handle login failure
            if not service_instance:
                logger_message = f"Error while logging in(login) into vSphere: Could not connect to the specified host using specified username and password"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)
                return {'error': 'Unable to login'}

            print("Successfully logged in into the vSphere!")

            return service_instance
            # return {'error': "Error Occurred"}

        except vim.fault.InvalidLogin as login_exception:
            # log exception
            logger_message = f"Exception occurred while logging in(login) into vSphere: {str(login_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)
            return {'error': login_exception.msg}

            # raise login_exception.msg
            # raise login_exception
        except TimeoutError as connect_exception:
            # log exception
            logger_message = f"Exception occurred while logging in(login) into vSphere: {str(connect_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            return {'error': 'Failed! unable to connect'}

    @staticmethod
    def vm_logout(service_instance):
        try:
            connect.Disconnect(service_instance)
        except vim.fault as vm_exception:
            logger_message = f"Exception occurred while logging out(logout) from vSphere: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)
            return 'Unable to logout'

    @staticmethod
    def is_vnic(device):
        try:
            response = isinstance(device, vim.vm.device.VirtualEthernetCard)
            _json = {
                "status": "success",
                "res": response
            }
            return _json
        except Exception as vm_exception:
            logger_message = f"Exception occurred while working with virtual NIC: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)
            _json = {
                "status": "error",
                "res": "Exception occurred while working with virtual NIC." + str(vm_exception)
            }
            return _json

    @staticmethod
    def get_nic_by_name(vm, vm_name, name):
        try:
            for dev in vm.config.hardware.device:
                if VmHelper.is_vnic(dev) and dev.deviceInfo.label.lower() == name.lower():
                    json_ = {
                        'res': dev,
                        'status': "success"
                    }
                    return json_

            json_ = {
                'res': 'Exception occurred,' + str(vm_name) + " NIC " + name + " could not be found!",
                'status': "error"
            }

            logger_message = f"Error while fetching NIC for {str(vm_name)}: {str(vm_name)} NIC {str(name)} could not found!"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            return json_
        except Exception as e:
            logger_message = f"Exception occurred while fetching NIC for {str(vm_name)}: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching NIC for ' + str(vm_name) + ", " + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def get_obj(content, vimtype, name, is_template=False):
        try:
            container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
            for c in container.view:
                if c.name == name:

                    # If the object is a Virtual Machine, check if it is a template
                    if is_template is False and isinstance(c, vim.VirtualMachine):
                        if c.config.template:
                            continue  # Skip this and search for a non-template VM

                    json_ = {
                        "status": "success",
                        "res": c
                    }
                    return json_

            json_ = {
                "status": "error",
                "res": "Exception occurred, " + str(name) + " not found"
            }

            logger_message = f"Error while fetching the object of {str(name)}: {str(name)} not found"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)
            return json_
        except Exception as e:
            logger_message = f"Exception occurred while fetching the object of {str(name)}: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the object details. ' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def wait_for_task(task, actionName='job', hideResult=False):
        try:
            """
            Waits and provides updates on a vSphere task
            """

            print("...wait for task start......")
            print(task)
            print(task.info.state)
            print(vim.TaskInfo.State)

            while task.info.state == vim.TaskInfo.State.running or task.info.state == vim.TaskInfo.State.queued or task.info.state == "queued":
                time.sleep(15)

            if task.info.state == vim.TaskInfo.State.success:
                if task.info.result is not None and not hideResult:
                    out = '%s completed successfully, result: %s' % (actionName, task.info.result)
                    print(out)
                    json_ = {
                        'res': "Job completed successfully",
                        'status': "success"
                    }
                    return json_
                else:
                    out = '%s completed successfully.' % actionName
                    print(out)
                    json_ = {
                        'res': out,
                        'status': "success"
                    }
                    return json_

            else:

                out = '%s did not complete successfully: %s' % (actionName, task.info.error)
                print(out)
                # must be from base exception so commented line -
                # raise task.info.error  # error happens here
                json_ = {
                    'res': task.info.error,
                    'status': "error"
                }

                logger_message = f"Error while waiting for a `{str(actionName)}` task to complete: {str(task.info.error)}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                return json_
                # raise ValueError(task.info.error)
                # raise task.info.error  # error happens here

            # return task.info.result
        # except vim.fault as e:
        except Exception as e:
            logger_message = f"Exception occurred while waiting for a `{str(actionName)}` task to complete: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def wait_for_tasks(service_instance, tasks):
        pcfilter = None
        try:

            """Given the service instance si and tasks, it returns after all the
           tasks are complete
           """
            property_collector = service_instance.content.propertyCollector
            task_list = [str(task) for task in tasks]
            # Create filter
            obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                         for task in tasks]
            property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                                       pathSet=[],
                                                                       all=True)
            filter_spec = vmodl.query.PropertyCollector.FilterSpec()
            filter_spec.objectSet = obj_specs
            filter_spec.propSet = [property_spec]
            pcfilter = property_collector.CreateFilter(filter_spec, True)
            version, state = None, None

            # Loop looking for updates till the state moves to a completed state.
            while len(task_list):
                update = property_collector.WaitForUpdates(version)
                for filter_set in update.filterSet:
                    for obj_set in filter_set.objectSet:
                        task = obj_set.obj
                        for change in obj_set.changeSet:
                            if change.name == 'info':
                                state = change.val.state
                            elif change.name == 'info.state':
                                state = change.val
                            else:
                                continue

                            if not str(task) in task_list:
                                continue
                            if state == vim.TaskInfo.State.success:
                                # Remove task from taskList
                                task_list.remove(str(task))
                            elif state == vim.TaskInfo.State.error:
                                if pcfilter is not None:
                                    pcfilter.Destroy()
                                response_messages = str(task.info.error)
                                json_ = {
                                    'res': response_messages,
                                    'status': "error"
                                }
                                return json_
                    # Move to next version
                version = update.version
            json_ = {
                'res': "job completed successfully",
                'status': "success"
            }
            return json_
        except Exception as e:
            if pcfilter is not None:
                pcfilter.Destroy()
            response_messages = str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }

            logger_message = f"Exception occurred while waiting for tasks to complete: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            return json_

    def get_dc(self, service_instance, name):
        try:
            content = service_instance.RetrieveContent()

            if name is not "":
                datacenter_response = self.get_obj(content, [vim.Datacenter], name)
                if datacenter_response['status'] == "success":
                    datacenter = datacenter_response['res']
                else:
                    logger_message = f"Error while fetching Datacenter object for the `{name}` Datacenter: {str(datacenter_response)}"
                    logger.error(logger_message)
                    audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                    print(logger_message)

                    return datacenter_response
            else:
                datacenter = content.rootFolder.childEntity[0]

            json_ = {
                'res': datacenter,
                'status': "success"
            }
            return json_
        except Exception as e:
            logger_message = f"Exception occurred while fetching Datacenter object for the `{name}` Datacenter: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred, Unable to get the datacenter.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

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
                    json_ = {
                        'res': vm_obj,
                        'status': "success"
                    }
                    return json_

            json_ = {
                'res': "Exception occurred, VM object not found.",
                'status': "error"
            }
            logger_message = f"Error while fetching the VM object: VM `{str(vm_name)}` not found on vSphere"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            return json_
        except Exception as e:
            logger_message = f"Exception occurred while fetching the VM object fot the `{str(vm_name)}` VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the vm object.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def get_vm_obj(vm_name, datacenter, host, resource_pool, str_folder=None, is_cluster=False):
        try:
            print(f"here: get-vm_obj: {vm_name}, {datacenter}, {host}, {resource_pool}, {str_folder} {is_cluster}")

            # init helpers
            vm_helper = VmHelper()

            # init progress recorder
            si = vm_helper.vm_login()

            # disconnect vc
            atexit.register(connect.Disconnect, si)

            # Get the content
            content = si.RetrieveContent()

            # get the vm object
            vm = None

            # Fetching VMs for standalone server with resource pool
            if (is_cluster == 0 or is_cluster is False) and (resource_pool and resource_pool != "NA"):

                print(f"here: Fetching `{vm_name}` VM with {resource_pool} resource pool")

                dc_list = []
                host_list = []

                # get DC
                for datacenter_name in datacenter:
                    dc_response = vm_helper.get_dc(si, datacenter_name)
                    if dc_response['status'] == "success":
                        dc = dc_response['res']
                        dc_list.append(dc)

                if len(dc_list) == 0:
                    logger_message = f"Exception occurred while fetching the VM object: Datacenter not found on vSphere while fetching the VM {str(vm_name)}"
                    logger.error(logger_message)
                    audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                    res = {"status": "error", "res": f"Datacenter not found on vSphere while fetching the VM {vm_name}"}
                    return res

                # use DC, get host
                for host_name in host:
                    for dc in dc_list:
                        host = si.content.searchIndex.FindChild(dc.hostFolder, host_name)
                        if host:
                            host_list.append(host)

                if len(host_list) == 0:
                    logger_message = f"Exception occurred while fetching the VM object: Host not found on vSphere while fetching the VM {str(vm_name)}"
                    logger.error(logger_message)
                    audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                    res = {"status": "error", "res": f"Host not found on vSphere while fetching the VM {vm_name}"}
                    return res

                # use host, get resource pool
                for host in host_list:
                    rs = si.content.searchIndex.FindChild(host.resourcePool, resource_pool)
                    # all the child resource pool of kalinga
                    child_rs_obj_list = rs.resourcePool
                    child_vm_obj_list = rs.vm

                    # all the direct vms in resourcepool
                    for vms in child_vm_obj_list:
                        if vms.name == vm_name and not vms.config.template:
                            vm = vms
                            print(f"here: `{vm_name}` VM found from normal resource pool!")
                            _json = {'res': vm, 'status': "success"}
                            return _json

                    # all the vm machines object from all the child resource pool
                    for i in child_rs_obj_list:
                        vm_obj = i.vm
                        for j in vm_obj:
                            if j.name == vm_name and not j.config.template:
                                vm = j
                                print(f"here: `{vm_name}` VM found from nested resource pool!")
                                _json = {'res': vm, 'status': "success"}
                                return _json

            elif str_folder and str_folder != "NA":

                print(f"here: fetching `{vm_name}` VM with folder `{str_folder}`")

                for datacenter in content.rootFolder.childEntity:

                    if isinstance(datacenter, vim.Datacenter):
                        for folder in datacenter.vmFolder.childEntity:

                            # check the vm inside this folder
                            if isinstance(folder, vim.Folder) and folder.name == str_folder:

                                print(f"here: folder.name: `{folder.name}` ")
                                for child in folder.childEntity:

                                    if isinstance(child,
                                                  vim.VirtualMachine) and child.name == vm_name and not child.config.template:
                                        vm = child
                                        print(f"here: `{vm_name}` VM found from normal folder!")
                                        _json = {'res': vm, 'status': "success"}
                                        return _json

                                    elif isinstance(child, vim.Folder):

                                        for each_vm in child.childEntity:

                                            if isinstance(each_vm,
                                                          vim.VirtualMachine) and each_vm.name == vm_name and not each_vm.config.template:
                                                vm = each_vm
                                                print(f"here: `{vm_name}` VM found from nested folder!")
                                                _json = {'res': vm, 'status': "success"}
                                                return _json
                                    else:
                                        res = {"status": "error", "res": "VM {} Not Found".format(vm_name)}
                                        print(res)

            else:
                res = {"status": "error", "res": f"No Resource pool or Folder provided while fetching VM {vm_name}"}

                logger_message = f"Exception occurred while fetching the VM object: No Resource pool or Folder provided while fetching VM {str(vm_name)}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                return res

            if not vm:
                logger_message = f"Exception occurred while fetching the VM object: VM `{str(vm_name)}` not found on vSphere"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                res = {"status": "error", "res": "VM {} Not Found".format(vm_name)}
                print(res)
                return res
            else:
                _json = {'res': vm, 'status': "success"}
                return _json

        except Exception as e:
            logger_message = f"Exception occurred while fetching the VM object for the `{str(vm_name)}` VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the VM object.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def find_vm_anywhere(vm_name, arr_datacenter, arr_host, is_cluster=False):
        """
        Find a VM in specified Datacenters and Hosts.
        - If `is_cluster=True`, search only in Clusters.
        - If `is_cluster=False`, search only in Standalone Hosts.
        """

        try:
            print(f"here: find-vm_in_anywhere: {vm_name}, {arr_datacenter}, {arr_host}, {is_cluster}")

            # Initialize helpers
            vm_helper = VmHelper()
            si = vm_helper.vm_login()
            atexit.register(connect.Disconnect, si)  # Ensure vCenter disconnects

            # Get the vSphere content
            content = si.RetrieveContent()

            # vm = None  # Placeholder for VM object

            def search_vm_in_folder(folder):
                """ Recursively search VM inside folders. """
                for entity in folder.childEntity:
                    if isinstance(entity, vim.VirtualMachine) and entity.name == vm_name and not entity.config.template:
                        print(f"Found `{vm_name}` inside folder `{folder.name}`.")
                        return entity
                    elif isinstance(entity, vim.Folder):
                        found_vm = search_vm_in_folder(entity)
                        if found_vm:
                            return found_vm
                return None

            def search_vm_in_resource_pool(resource_pool):
                """ Recursively search VM inside resource pools. """
                for vm in resource_pool.vm:
                    if vm.name == vm_name and not vm.config.template:
                        print(f"Found `{vm_name}` inside resource pool `{resource_pool.name}`.")
                        return vm
                for child_pool in resource_pool.resourcePool:
                    found_vm = search_vm_in_resource_pool(child_pool)
                    if found_vm:
                        return found_vm
                return None

            # Iterate only through the specified Datacenters
            for datacenter in content.rootFolder.childEntity:
                if not isinstance(datacenter, vim.Datacenter) or datacenter.name not in arr_datacenter:
                    continue  # Skip Datacenters not in the allowed list

                print(f"Searching in Datacenter: {datacenter.name}")

                # **Search inside the Datacenter's VM Folder**
                vm = search_vm_in_folder(datacenter.vmFolder)
                if vm:
                    print("here: VM found in datacenter folders!")
                    return {'res': vm, 'status': "success"}

                # **Search inside Hosts (Standalone or Cluster based on `is_cluster`)**
                for compute_resource in datacenter.hostFolder.childEntity:

                    for host in compute_resource.host:
                        # Only check specified hosts
                        # Search for VMs inside the Standalone Host**

                        if host.name in arr_host:
                            for vm in host.vm:
                                if vm.name == vm_name and not vm.config.template:
                                    return {'res': vm, 'status': "success"}

                            if hasattr(host, 'vmFolder'):
                                vm = search_vm_in_folder(host.vmFolder)
                                if vm:
                                    return {'res': vm, 'status': "success"}

                            if is_cluster is False:
                                # Search inside Resource Pools inside this Standalone Host**
                                if hasattr(host, 'resourcePool'):
                                    vm = search_vm_in_resource_pool(host.resourcePool)
                                    if vm:
                                        return {'res': vm, 'status': "success"}

                    #
                    #
                    # # Standalone ESXi
                    # if is_cluster is False and isinstance(compute_resource, vim.ComputeResource):
                    #     for host in compute_resource.host:
                    #         if host.name in arr_host:  # Only check specified hosts
                    #             print(f"🔎 Searching in Standalone Host: {host.name}")
                    #
                    #             # 🔹 **Search for VMs inside the Standalone Host**
                    #             for vm in host.vm:
                    #                 if vm.name == vm_name and not vm.config.template:
                    #                     print(f"✅ Found `{vm_name}` in standalone host `{host.name}`.")
                    #                     return {'res': vm, 'status': "success"}
                    #
                    #             # 🔹 **Search inside folders inside this Standalone Host**
                    #             if hasattr(host, 'vmFolder'):
                    #                 vm = search_vm_in_folder(host.vmFolder)
                    #                 if vm:
                    #                     return {'res': vm, 'status': "success"}
                    #
                    #             # Search inside Resource Pools inside this Standalone Host**
                    #             if hasattr(host, 'resourcePool'):
                    #                 vm = search_vm_in_resource_pool(host.resourcePool)
                    #                 if vm:
                    #                     return {'res': vm, 'status': "success"}
                    #
                    # # If it is Cluster
                    # elif is_cluster is True and isinstance(compute_resource, vim.ClusterComputeResource):
                    #     print(f"🔎 Searching in Cluster: {compute_resource.name}")
                    #
                    #     # 3️⃣ **Search inside specific Hosts in Cluster**
                    #     for host in compute_resource.host:
                    #         if host.name in arr_host:  # Only check specified hosts
                    #             print(f"🔎 Searching in Cluster Host: {host.name}")
                    #
                    #             # 🔹 **Search for VMs inside the Cluster Host**
                    #             for vm in host.vm:
                    #                 if vm.name == vm_name and not vm.config.template:
                    #                     print(f"✅ Found `{vm_name}` inside cluster `{compute_resource.name}`, host `{host.name}`.")
                    #                     return {'res': vm, 'status': "success"}
                    #
                    #             # 🔹 **Search inside folders inside this Cluster Host**
                    #             if hasattr(host, 'vmFolder'):
                    #                 vm = search_vm_in_folder(host.vmFolder)
                    #                 if vm:
                    #                     return {'res': vm, 'status': "success"}

            print(f"VM `{vm_name}` not found in specified Datacenters/Hosts.")
            return {'status': "error", 'res': f"VM `{vm_name}` not found in the given scope."}

        except Exception as e:
            logger_message = f"Exception occurred while fetching the VM object for the `{str(vm_name)}` VM: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = f'Exception occurred while fetching the VM object: {str(e)}'
            return {'res': response_messages, 'status': "error"}

    @staticmethod
    def get_resource_pool_obj(arr_datacenter, arr_host, str_resource_pool, str_cluster_name=None, is_cluster=False):
        try:
            print(
                f"here: get-resource_pool_obj: {arr_datacenter}, {arr_host}, {str_resource_pool}, {str_cluster_name}, {is_cluster}")

            # init helpers
            vm_helper = VmHelper()

            # init progress recorder
            si = vm_helper.vm_login()

            # disconnect vc
            atexit.register(connect.Disconnect, si)

            # Get the content
            content = si.RetrieveContent()

            # get the resource pool object
            obj_resource_pool = None

            # Fetching VMs for standalone server with resource pool
            if (is_cluster == 0 or is_cluster is False) and (str_resource_pool and str_resource_pool != "NA"):

                print(f"here: Fetching `{str_resource_pool}` resource pool with it's name(standalone)")

                arr_obj_dc = []
                arr_obj_host = []

                # get DC
                for datacenter_name in arr_datacenter:
                    dc_response = vm_helper.get_dc(si, datacenter_name)
                    if dc_response['status'] == "success":
                        dc = dc_response['res']
                        arr_obj_dc.append(dc)

                if len(arr_obj_dc) == 0:
                    logger_message = f"Error while fetching the resource pool object for the `{str(str_resource_pool)}` resource pool: Datacenter not found on vSphere"
                    logger.error(logger_message)
                    audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                    print(logger_message)

                    res = {"status": "error",
                           "res": f"Datacenter not found on vSphere while fetching the `{str_resource_pool}` resource pool!"}
                    return res

                # use DC, get host obj
                for host_name in arr_host:
                    for dc in arr_obj_dc:
                        host = si.content.searchIndex.FindChild(dc.hostFolder, host_name)
                        if host:
                            arr_obj_host.append(host)

                if len(arr_obj_host) == 0:
                    logger_message = f"Error while fetching the resource pool object for the `{str(str_resource_pool)}` resource pool: Host not found on vSphere"
                    logger.error(logger_message)
                    audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                    print(logger_message)

                    res = {"status": "error",
                           "res": f"Host not found on vSphere while fetching the {str_resource_pool}` resource pool!"}
                    return res

                # use host, get resource pool
                for host in arr_obj_host:
                    obj_resource_pool = si.content.searchIndex.FindChild(host.resourcePool, str_resource_pool)
                    if obj_resource_pool:
                        _json = {'res': obj_resource_pool, 'status': "success"}
                        return _json

            elif str_cluster_name and str_cluster_name != "NA":
                print(f"here: Fetching resource pool with the `{str_cluster_name}` cluster")
                cluster_response = vm_helper.get_obj(content, [vim.ClusterComputeResource], str_cluster_name)
                if cluster_response['status'] == "success":
                    cluster = cluster_response['res']
                    obj_resource_pool = cluster.resourcePool
                    _json = {'res': obj_resource_pool, 'status': "success"}
                    return _json
            else:
                logger_message = f"Error while fetching the resource pool object for the `{str(str_resource_pool)}` resource pool: No Resource pool or Cluster name provided"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                res = {"status": "error", "res": f"No Resource pool or Cluster name provided while fetching object"}
                return res

            if not obj_resource_pool:
                logger_message = f"Error while fetching the resource pool object for the `{str(str_resource_pool)}` resource pool: Resource pool object not found on vSphere"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                res = {"status": "error", "res": f"Resource pool object not found on vSphere"}
                return res
            else:
                _json = {'res': obj_resource_pool, 'status': "success"}
                return _json

        except Exception as e:
            logger_message = f"Exception occurred while fetching the resource pool object for the `{str(str_resource_pool)}` resource pool: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the resource pool object.' + str(e)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_

    @staticmethod
    def get_folder_obj(str_folder):
        try:
            print(f"here: get-folder_obj: {str_folder}")

            # init helpers
            vm_helper = VmHelper()

            # init progress recorder
            si = vm_helper.vm_login()

            # disconnect vc
            atexit.register(connect.Disconnect, si)

            # Get the content
            content = si.RetrieveContent()

            if str_folder and str_folder != "NA":
                for datacenter in content.rootFolder.childEntity:
                    if isinstance(datacenter, vim.Datacenter):
                        for folder in datacenter.vmFolder.childEntity:
                            if isinstance(folder, vim.Folder) and folder.name == str_folder:
                                print(f"Folder `{folder.name}` found!")
                                return {'res': folder, 'status': "success"}

                logger_message = f"Error while fetching the folder object for the `{str(str_folder)}` folder: Folder `{str_folder}` not found in any datacenter"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                # Fallback if folder is not found
                return {'status': "error", 'res': f"Folder `{str_folder}` not found in any datacenter."}
            else:
                logger_message = f"Error while fetching the folder object for the `{str(str_folder)}` folder: Folder name not provided"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                return {'status': "error", 'res': f"Folder name not provided to fetch the folder object."}

        except Exception as e:
            logger_message = f"Exception occurred while fetching the folder object for the `{str(str_folder)}` folder: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the folder object.' + str(e)
            json_ = {'res': response_messages, 'status': "error"}
            return json_

    @staticmethod
    def get_vm_template_obj(str_template_folder, str_template_name):
        try:
            print(f"here: get-vm_template_obj: {str_template_folder} {str_template_name}")

            # Check for folder name
            if not str_template_folder or str_template_folder is None or str_template_folder == "NA":
                logger_message = f"Exception occurred while fetching the template object for the `{str(str_template_name)}` template: Template folder name not provided"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                return {'status': "error", 'res': f"Template folder name not provided to fetch the template object."}

            # Check for template name
            if not str_template_name or str_template_name is None or str_template_name == "NA":
                logger_message = f"Exception occurred while fetching the template object for the `{str(str_template_name)}` template: Template name not provided"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                return {'status': "error", 'res': f"Template name not provided to fetch the template object."}

            # init helpers
            vm_helper = VmHelper()

            # init progress recorder
            si = vm_helper.vm_login()

            # disconnect vc
            atexit.register(connect.Disconnect, si)

            # Get the content
            content = si.RetrieveContent()

            # Get the VM object
            for datacenter in content.rootFolder.childEntity:
                if isinstance(datacenter, vim.Datacenter):
                    for folder in datacenter.vmFolder.childEntity:
                        print(f"Here: folder: {folder.name}")
                        if isinstance(folder, vim.Folder) and folder.name == str_template_folder:
                            print(f"Folder `{folder.name}` found!")
                            for child in folder.childEntity:
                                # print("here: child.config.template: ", child.config.template)
                                if isinstance(child,
                                              vim.VirtualMachine) and child.config and child.config.template and child.name == str_template_name:
                                    return {'res': child, 'status': "success"}

                            return {
                                'res': f"The `{str_template_name}` template not found in `{str_template_folder}` template folder on vSphere",
                                'status': "error"}

            # Fallback if template object is not found

            logger_message = f"Exception occurred while fetching the template object for the `{str(str_template_name)}` template: Template not found on vSphere"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            return {'status': "error", 'res': f"Template not found on vSphere"}

        except Exception as e:
            logger_message = f"Exception occurred while fetching the template object for the `{str(str_template_name)}` template: {str(e)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while fetching the template object.' + str(e)
            json_ = {'res': response_messages, 'status': "error"}
            return json_


# Added because we are using raise "error" so it must be from base exception
class CustomError(Exception):
    pass


def acquire_mks_ticket(vm_name=""):
    try:
        print("here: acquire-mks_ticket")

        if not vm_name or vm_name is None or vm_name == "":
            logger_message = f"Error while fetching the MKS ticket(needed for Take Browser Console) for the `{str(vm_name)}` VM: VM name not found"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            data = "VM name not found! Please send VM name"
            print("here: ", data)

            temp = {"status": "error", "data": str(data)}
            return temp

        server_ip = None
        username = None
        password = None

        esxi_creds = list(VsphereDetails.objects.filter(enabled="enabled").values('server_ip', 'username', 'password'))

        if len(esxi_creds) == 1:

            for ele in esxi_creds:
                server_ip = ele['server_ip']
                username = ele['username']
                password = ele['password']

        elif len(esxi_creds) > 1:
            logger_message = f"Error while fetching the MKS ticket(needed for Take Browser Console) for the `{str(vm_name)}` VM: More than 1 esxi server is enabled"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            temp = {
                "status": "error",
                "data": 'More than 1 esxi server is enabled.'
            }
            return temp


        else:
            logger_message = f"Error while fetching the MKS ticket(needed for Take Browser Console) for the `{str(vm_name)}` VM: EXSI server details not found!"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            temp = {
                "status": "error",
                "data": 'Please add details of esxi server. No server found'
            }
            return temp

        # api_session_url = "https://172.22.1.100/api/session"
        # username = "administrator@vsphere.local"
        # password = "P@ssw0rd@PurPl159"
        api_session_url = f"https://{server_ip}/api/session"
        print(api_session_url)
        print("**************************")
        print("****************************")
        username = username
        password = password
        response_session_data = requests.post(api_session_url, auth=(username, password), verify=False)
        # print("here: api_session_url response: ", api_session_url, response_session_data)
        obj_resp_session_data = response_session_data.json()

        if response_session_data.status_code == 200 or response_session_data.status_code == 201:
            # print("here: obj_resp_session_data: session id: ", obj_resp_session_data)
            payload = {
                "type": "WEBMKS"
            }
            headers = {
                'vmware-api-session-id': str(obj_resp_session_data),
            }
            api_ticket_url = f"https://{server_ip}/api/vcenter/vm/{vm_name}/console/tickets"
            response_ticket_data = requests.post(api_ticket_url, json=payload, headers=headers, verify=False)
            # print("here: ", api_ticket_url, payload, headers)
            obj_response_ticket_data = response_ticket_data.json()
            # print("here: obj_response_ticket_data: ", obj_response_ticket_data)

            if response_ticket_data.status_code == 200 or response_ticket_data.status_code == 201:
                # print("here: obj_response_ticket_data : ", obj_response_ticket_data['ticket'])
                temp = {
                    "status": "success",
                    "data": obj_response_ticket_data
                }
                return temp
            else:
                temp = {
                    "status": "error",
                    "data": obj_response_ticket_data
                }
                return temp
        else:
            temp = {
                "status": "error",
                "data": obj_resp_session_data
            }
            return temp

    except Exception as e:
        logger_message = f"Exception occurred while fetching the MKS ticket(needed for Take Browser Console) for the `{str(vm_name)}` VM: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        print("here: Exception occurred at acquire-mks_ticket: ", e)
        temp = {"status": "error", "data": str(e)}
        return temp
