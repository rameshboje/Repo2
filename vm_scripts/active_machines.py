import atexit
from pyVim.task import WaitForTask
from pyVim import connect
from pyVmomi import vim, vmodl
from .helpers import VmHelper
from vm_scripts import active_machines as activate_machine_script

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'


def active_machines_on_cluster(si, vm_name, cluster_name,host_list):
    try:
        # init helpers
        vm_helper = VmHelper()

        existing_vm = []
        vm_obj_list = []
        active_machine = []
        inactive_machine = []
        other_status = []

        # for cluster_obj in vm_helper.get_obj(si, vim.ComputeResource, cluster_name):
        content = si.RetrieveContent()
        cluster_response = vm_helper.get_obj(content, [vim.ComputeResource], cluster_name)

        if cluster_response['status'] == "success":
            cluster_obj = cluster_response['res']
        else:
            return cluster_response['res']

        if cluster_obj.name == cluster_name:
            for host in cluster_obj.host:
                if host.name in host_list:
                    raw_obj_list = host.vm
                    for vm_obj in raw_obj_list:
                        vm_obj_list.append(vm_obj)
                        existing_vm.append(vm_obj.name)

        # check it against vm name coming from request
        for i in range(len(vm_name)):

            if vm_name[i] in existing_vm:
                index = existing_vm.index(vm_name[i])
                vm_obj = vm_obj_list[index]

                if format(vm_obj.runtime.powerState) == "poweredOn":
                    active_machine.append(vm_name[i])
                elif format(vm_obj.runtime.powerState) == "poweredOff":
                    inactive_machine.append(vm_name[i])
                else:
                    other_status.append(vm_name[i])
            else:
                logger.info("Machine " + vm_name[i] + " does not exist in the lab")

        content = {
            'active_machines': active_machine,
            'inactive_machine': inactive_machine,
            'percent': round((len(active_machine) / len(vm_name)) * 100, 0)
        }

        return content
    except vmodl.MethodFault as vm_exception:
        logger_message = f"Exception occurred while fetching all active and inactive machines from cluster: {str(vm_exception)}"
        # logger.error(logger_message)
        # audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return vm_exception.msg

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching all active and inactive machines from cluster: {str(unknown_exception)}"
        # logger.error(logger_message)
        # audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return "Exception occurred while fetching live machines." + str(unknown_exception)


# fetches all the machines in power on state in kalinga
# used in health check functionality
def active_machines(vm_list, vsphere_details):
    try:

        # init helpers
        vm_helper = VmHelper()

        # login
        si = vm_helper.vm_login()

        # disconnect vc
        atexit.register(connect.Disconnect, si)

        is_cluster = vsphere_details['is_cluster']
        cluster_name = vsphere_details['cluster_name']
        host_list = vsphere_details['host']

        if is_cluster == 1:
            res = activate_machine_script.active_machines_on_cluster(si, vm_list, cluster_name, host_list)
            return res

        dc_list = vsphere_details['data_center']

        existing_vm = []
        active_machine = []
        inactive_machine = []
        other_status = []
        vm_obj_list = []

        for i in range(len(dc_list)):

            dc_response = vm_helper.get_dc(si, dc_list[i])
            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response['res']

            for compute_resource in dc.hostFolder.childEntity:
                for host in compute_resource.host:
                    print("&&&&&&&&&&&&&&&&&&777")

                    if host.name in host_list:
                        print(host)
                        for vm in host.vm:

                            if vm.name in vm_list and not vm.config.template:
                                vm_obj_list.append(vm)
                                existing_vm.append(vm.name)



            # host = si.content.searchIndex.FindChild(dc.hostFolder, host_list[i])
            # rs = si.content.searchIndex.FindChild(host.resourcePool, rp_list[i])

            # vm_obj_list = rs.vm

            # all the child resource pool of kalinga
            # child_rs_obj_list = rs.resourcePool

            # all the vm machines object from all the child resource pool
            # for i in child_rs_obj_list:
            #     temp_vm_obj = i.vm
            #     for j in temp_vm_obj:
            #         vm_obj_list.append(j)

        # fetch vm names from the vm object from all the resource pool
        for vm in vm_obj_list:
            existing_vm.append(vm.name)

        # check it against vm name coming from request
        for i in range(len(vm_list)):
            if vm_list[i] in existing_vm:
                index = existing_vm.index(vm_list[i])
                vm_obj = vm_obj_list[index]
                if format(vm_obj.runtime.powerState) == "poweredOn":
                    active_machine.append(vm_list[i])
                elif format(vm_obj.runtime.powerState) == "poweredOff":
                    inactive_machine.append(vm_list[i])
                else:
                    other_status.append(vm_list[i])
            else:
                logger.info("Machine " + vm_list[i] + " does not exist in the lab")
                # return "Machine " + vm_name[i] + " does not exist in the lab"

        content = {
            'active_machines': active_machine,
            'inactive_machine': inactive_machine,
            'percent': round((len(active_machine) / len(vm_list)) * 100, 0)
        }

        return content

    except vmodl.MethodFault as vm_exception:
        logger_message = f"Exception occurred while fetching all active and inactive machines from cluster: {str(vm_exception)}"
        # logger.error(logger_message)
        # audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return vm_exception.msg

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching all active and inactive machines from cluster: {str(unknown_exception)}"
        # logger.error(logger_message)
        # audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return "Exception occurred while fetching live machines." + str(unknown_exception)


