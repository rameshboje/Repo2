import atexit
from pyVim import connect
from .helpers import VmHelper
from pyVmomi import vim, vmodl
from vm_scripts import resource_utilizations as resource_utilizations_script
from django.http import HttpResponse, Http404, JsonResponse

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'



def get_summary(vm_obj_list):
    try:
        vm_dict_data = []

        for vm_obj in vm_obj_list:
            data = dict()
            data['vm_name'] = vm_obj.name
            summary = vm_obj.summary
            stats = summary.quickStats
            storage = summary.storage
            data['powerstate'] = vm_obj.runtime.powerState


            # for CPU utilizations
            total_cpu_usage  = stats.overallCpuUsage + stats.overallCpuDemand
            data['total_cpu'] = total_cpu = vm_obj.runtime.maxCpuUsage
            if total_cpu_usage == 0 or total_cpu_usage is None or total_cpu == 0 or total_cpu is None:
               data['percentage_cpu'] = 0
               data['total_cpu_usage'] = 0
            else:
                data['total_cpu_usage'] = average_usage = total_cpu_usage/2
                data['percentage_cpu'] = round((average_usage/total_cpu) * 100,2)

            if data['percentage_cpu'] > 100:
                data['percentage_cpu'] = 100

            # for memory utilizations
            total_memory_usage = stats.guestMemoryUsage + stats.hostMemoryUsage
            total_memory = vm_obj.runtime.maxMemoryUsage
            if total_memory_usage == 0 or total_memory_usage is None or total_memory == 0 or total_memory is None:
                data['percentage_memory'] = 0
                data['total_memory_usage'] = 0
                data['total_memory'] = 0
            else:
                data['total_memory'] = round((total_memory/1024),2)
                data['total_memory_usage'] = round((total_memory_usage/1024),2)
                data['percentage_memory'] = round((total_memory_usage/total_memory) * 100,2)

            if data['percentage_memory'] > 100:
                data['percentage_memory'] = 100

            if data['total_memory_usage'] > data['total_memory']:
                data['total_memory_usage'] = data['total_memory']

            # for storage utilizations
            total_storage_utilization = storage.unshared

            # taking care of multiple hard disk
            # loop to sum up the total disk
            total_storage = 0
            for device in vm_obj.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    capacityInGB = device.capacityInKB / 1024 / 1024  # Convert KB to GB    return disk_capacity
                    total_storage += capacityInGB

            if total_storage_utilization == 0 or total_storage_utilization is None or total_storage == 0 or total_storage is None:
                data['total_storage_utilization'] = total_storage_utilization
                data['percentage_storage'] = 0
            else:
                total_storage_utilization = total_storage_utilization/(1024*1024*1024)
                data['total_storage_utilization'] = round(total_storage_utilization,2)
                data['total_storage'] = round(total_storage,0)
                data['percentage_storage'] = round((total_storage_utilization/total_storage) * 100,2)

            if data['percentage_storage'] > 100:
                data['percentage_storage'] = 100

            vm_dict_data.append(data)
        res = {
            'message':vm_dict_data,
            'status': 'success'
        }

        return res

    except Exception as e:
        logger_message = f"Exception occurred while fetching the resources of VMs: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        res = {
            'message': "Error while fetching the resources of VMs {}".format(str(e)),
            'status': 'error'
        }
        return res

def get_resource_utilizations_cluster(si, cluster_name,vm_list,host_list):
    try:
        # init helpers
        vm_helper = VmHelper()

        vm_obj_list = []
        existing_vm = []

        # for cluster_obj in vm_helper.get_obj(si, vim.ComputeResource, cluster_name):
        content = si.RetrieveContent()
        cluster_response = vm_helper.get_obj(content, [vim.ComputeResource], cluster_name)

        if cluster_response['status'] == "success":
            cluster_obj = cluster_response['res']
        else:
            return cluster_response['res']

        if cluster_obj.name == cluster_name:
            for host in cluster_obj.host:

                # fetch vms only from the hosts mentioned in the settings page
                # if host.name in host_list:
                raw_obj_list = host.vm
                for vm_obj in raw_obj_list:
                    if vm_obj.name in vm_list and not vm_obj.config.template:
                        vm_obj_list.append(vm_obj)
                        existing_vm.append(vm_obj.name)


        res = {
            'message': vm_obj_list,
            'existing_vm': existing_vm,
            'status': "success"
        }
        return res

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching machines from cluster: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        response = 'Exception occurred while fetching machines from cluster ' + str(unknown_exception)
        logger.info(response)
        res = {
            'message': 'response',
            'status': "error"
        }
        return res


def get_resource_utilizations(vm_list,_details):
    try:
        is_cluster = _details['is_cluster']
        cluster_name = _details['cluster_name']
        host_list = _details['host']


        # init helpers
        vm_helper = VmHelper()

        # login
        # disconnect vc
        si = vm_helper.vm_login()
        atexit.register(connect.Disconnect, si)
        vm_obj_list = []
        existing_vm = []
        existing_vm_obj = []

        if is_cluster == 1:

            res = resource_utilizations_script.get_resource_utilizations_cluster(si, cluster_name,vm_list,host_list)
            if res['status'] == "success":
                vm_obj_list = res["message"]
                existing_vm = res["existing_vm"]
            else:
                logger.info(res["message"])
                return res["message"]

        else:

            dc_list = _details['data_center']


            for i in range(len(dc_list)):
                dc_response = vm_helper.get_dc(si, dc_list[i])
                if dc_response['status'] == "success":
                    dc = dc_response['res']
                else:
                    return dc_response['res']

                for compute_resource in dc.hostFolder.childEntity:
                    for host in compute_resource.host:
                        # if host.name in host_list:
                        print(host)
                        for vm in host.vm:
                            if vm.name in vm_list and not vm.config.template:
                                vm_obj_list.append(vm)
                                existing_vm.append(vm.name)

        # total number of machines
        no_of_vms = len(vm_list)

        for i in range(no_of_vms):

            if vm_list[i] in existing_vm:
                index = existing_vm.index(vm_list[i])
                vm_obj = vm_obj_list[index]
                existing_vm_obj.append(vm_obj)



        utilization_report = resource_utilizations_script.get_summary(existing_vm_obj)
        # print(utilization_report)
        res={"status": 'success', "res": utilization_report }
        return res

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching the resource utilization for VM `{str(vm_list)}` : {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        msg="Exception occurred while fetching the resource utilization." + str(unknown_exception)
        res={"status": 'success', "res": msg }
        logger.info(msg)
        return res


def get_resource_utilization_host():
    try:
        # init helpers
        vm_helper = VmHelper()

        # login
        # disconnect vc
        si = vm_helper.vm_login()
        atexit.register(connect.Disconnect, si)

        # for cluster_obj in vm_helper.get_obj(si, vim.ComputeResource, cluster_name):
        content = si.RetrieveContent()
        cluster_response = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem] , True )
        children = cluster_response.view

        main_list = []

        # get details of host utilizations
        for host in children:
            try:
                temp_data = dict()
                summary = host.summary
                hardware = summary.hardware

                quickStats = summary.quickStats

                cpu_usage = quickStats.overallCpuUsage  # in MHz
                cpu_mhz_per_core = hardware.cpuMhz
                num_cpu_cores = hardware.numCpuCores
                total_memory = hardware.memorySize
                memory_usage = quickStats.overallMemoryUsage

                if cpu_mhz_per_core > 0:
                    cpu_mhz_per_core = cpu_mhz_per_core/1000 #in Ghz

                total_cpu = num_cpu_cores * cpu_mhz_per_core

                if cpu_usage > 0:
                    cpu_usage = cpu_usage/1000  #in GHz
                    cpu_per = (cpu_usage / total_cpu) * 100
                else:
                    cpu_per = 0


                if total_memory > 0:
                    total_memory = hardware.memorySize / (1024 * 1024 * 1024)  # Convert from Bytes to MB

                if memory_usage > 0:
                    memory_usage = memory_usage / 1024
                    memory_per = (memory_usage / total_memory) * 100
                else:
                    memory_per = 0


                temp_data["name"] = summary.config.name
                temp_data["cpu_usage"] = cpu_usage
                temp_data["cpu_total"] = total_cpu
                temp_data["cpu_per"] = cpu_per
                temp_data["memory_total"] = total_memory
                temp_data["memory_usage"] = memory_usage
                temp_data["memory_per"] = memory_per

                main_list.append(temp_data)
                status = "success"
                data = main_list

            except Exception as e:
                logger_message = f"Exception occurred while fetching the resource utilization for host : Unable to retrieve stats for host {str(host.summary.config.name)}: {str(e)}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                status = "error"
                data = f"Unable to retrieve stats for host {host.summary.config.name}: {e}"

        res = {
            "status": status,
            "data": data
        }
        return res

    except Exception as e:
        logger_message = f"Exception occurred while fetching the resource utilization for host : {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        res = {
            "status": "error",
            "data": "Exception Occurred While Fetching The Resource Utilization {}".format(e)
        }
        return res



def get_resource_utilization_datastore():
    try:
        # init helpers
        vm_helper = VmHelper()

        # login
        # disconnect vc
        si = vm_helper.vm_login()
        atexit.register(connect.Disconnect, si)

        # for cluster_obj in vm_helper.get_obj(si, vim.ComputeResource, cluster_name):
        content = si.RetrieveContent()
        containerView = content.viewManager.CreateContainerView(content.rootFolder, [vim.Datastore]  , True )
        children = containerView.view

        main_list = []

        # get the utilization for datastore
        for datastore in children :
            try:
                temp_data = dict()

                summary = datastore.summary
                capacity = summary.capacity
                free_space = summary.freeSpace

                if capacity > 0:
                    capacity = summary.capacity / (1024 * 1024 * 1024)  # Convert from Bytes to GB

                if free_space > 0:
                    free_space = summary.freeSpace / (1024 * 1024 * 1024)  # Convert from Bytes to GB

                used_space = capacity - free_space  # Calculate used space

                # percentage
                if used_space > 0:
                    perc = (used_space/capacity) * 100
                else:
                    perc = 0

                temp_data["name"] = summary.name
                temp_data["free_space"] = free_space
                temp_data["used_space"] = used_space
                temp_data["total_space"] = capacity
                temp_data["perc"] = perc
                main_list.append(temp_data)
                status = "success"
                data = main_list

            except Exception as e:
                logger_message = f"Exception occurred while fetching the resource utilization for datastore : Unable to retrieve stats for datastore {str(datastore.summary.name)}: {str(e)}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                print(logger_message)

                status = "error"
                data = f"Unable to retrieve stats for datastore {datastore.summary.name}: {e}"


        res = {
            "status": status,
            "data": data
        }
        return res

    except Exception as e:
        logger_message = f"Exception occurred while fetching the resource utilization for datastore : {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        res = {
            "status": "error",
            "data": "Exception Occurred While Fetching The Resource Utilization {}".format(e)
        }
        return res


