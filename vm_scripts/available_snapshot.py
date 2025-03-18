import atexit
from pyVim import connect
from pyVmomi import vim, vmodl
from .helpers import VmHelper
from vm_scripts import available_snapshot as available_snapshot_script

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'



# supporting function called by available_snapshot
# get snapshot object from v-sphere by using snapshot name
def get_snapshots_by_name_recursively(snapshots, snapname):
    snap_obj = []
    for snapshot in snapshots:
        if snapshot.name == snapname:
            snap_obj.append(snapshot)
        else:
            snap_obj = snap_obj + get_snapshots_by_name_recursively(
                                    snapshot.childSnapshotList, snapname)
    return snap_obj



def available_snapshot_on_cluster(si, vm_name, cluster_name):
    try:
        # init helpers
        vm_helper = VmHelper()

        existing_vm = []
        snapshot_list = []
        vm_obj_list = []

        # for cluster_obj in vm_helper.get_obj(si, vim.ComputeResource, cluster_name):
        content = si.RetrieveContent()
        cluster_response = vm_helper.get_obj(content, [vim.ComputeResource], cluster_name)

        if cluster_response['status'] == "success":
            cluster_obj = cluster_response['res']
        else:
            return cluster_response['res']

        if cluster_obj.name == cluster_name:
            for host in cluster_obj.host:
                raw_obj_list = host.vm
                for vm_obj in raw_obj_list:
                    vm_obj_list.append(vm_obj)
                    existing_vm.append(vm_obj.name)


        for i in range(len(vm_name)):
            if vm_name[i] in existing_vm:
                index = existing_vm.index(vm_name[i])
                # list of vm object
                vm_obj = vm_obj_list[index]

                if vm_obj.snapshot is None:
                    pass
                else:
                    snapshot_name = vm_name[i] + "_SS"
                    snap_obj = get_snapshots_by_name_recursively(
                        vm_obj.snapshot.rootSnapshotList, snapshot_name)

                    if len(snap_obj) == 1:
                        snapshot_list.append(snapshot_name)

        return len(snapshot_list)
    except vmodl.MethodFault as vm_exception:
        logger_message = f"Exception occurred while fetching snapshot from cluster: {str(vm_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return vm_exception.msg

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching snapshot from cluster: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return "Exception occurred while fetching the snapshot from cluster." + str(unknown_exception)






# called by health status script
def available_snapshot(vm_name,vsphere_details):
    try:

        # init helpers
        vm_helper = VmHelper()

        # login
        si = vm_helper.vm_login()

        # disconnect vc
        atexit.register(connect.Disconnect, si)

        is_cluster = vsphere_details['is_cluster']
        cluster_name = vsphere_details['cluster_name']

        if is_cluster == 1:
            res = available_snapshot_script.available_snapshot_on_cluster(si, vm_name, cluster_name)
            return res

        dc_list = vsphere_details['data_center']
        host_list = vsphere_details['host']
        rp_list = vsphere_details['resource_pool']
        existing_vm = []
        snapshot_list = []
        vm_obj_list = []

        # print(dc_list)
        for i in range(len(dc_list)):
            dc_response = vm_helper.get_dc(si, dc_list[i])

            if dc_response['status'] == "success":
                dc = dc_response['res']
            else:
                return dc_response['res']

            host = si.content.searchIndex.FindChild(dc.hostFolder, host_list[i])
            rs = si.content.searchIndex.FindChild(host.resourcePool, rp_list[i])
            child_rs_obj_list = rs.resourcePool

            # all the vm machines object from all the child resource pool
            for i in child_rs_obj_list:
                temp_vm_obj = i.vm
                for j in temp_vm_obj:
                    vm_obj_list.append(j)

            for vm in vm_obj_list:
                existing_vm.append(vm.name)

        for i in range(len(vm_name)):
            if vm_name[i] in existing_vm:
                index = existing_vm.index(vm_name[i])
                # list of vm object
                vm_obj = vm_obj_list[index]

                if vm_obj.snapshot is None:
                    pass
                else:
                    snapshot_name = vm_name[i] + "_SS"
                    snap_obj = get_snapshots_by_name_recursively(
                                vm_obj.snapshot.rootSnapshotList, snapshot_name)

                    if len(snap_obj) == 1:
                        snapshot_list.append(snapshot_name)


        return len(snapshot_list)

    except vmodl.MethodFault as vm_exception:
        logger_message = f"Exception occurred while fetching snapshot: {str(vm_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)
        return vm_exception.msg

    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching snapshot: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)
        return "Exception occurred while fetching the snapshot." + str(unknown_exception)


