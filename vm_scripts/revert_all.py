import atexit
from pyVim import connect
from .helpers import VmHelper
from pyVmomi import vim, vmodl
import time
from vm_scripts import revert_all as revert_all_script

# celery
from celery import shared_task
from celery_progress.backend import ProgressRecorder


import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'

def revert_all_cluster(si,cluster_name):
    try:
        # init helpers
        vm_helper = VmHelper()

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


        res = {
            'message': vm_obj_list,
            'status': "success"
        }
        return res
    except Exception as unknown_exception:
        logger_message = f"Exception occurred while fetching all machines from cluster: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        response = 'Exception occurred while fetching machines from cluster ' + str(unknown_exception)
        res = {
            'message': 'Exception occurred while fetching machines from cluster for reverting ' + str(response),
            'status': "error"
        }
        return res


@shared_task(bind=True, name='Reverting machines for the selected scenario')
def revert_all_machine(self, cred_details,**kwargs):
    try:
        vm_name = cred_details['machines']
        _revert = cred_details['exsi_details']['res']

        if "is_cluster" in _revert:
            is_cluster = _revert['is_cluster']
            cluster_name = _revert['cluster_name']
        else:
            is_cluster = ""
            cluster_name = ""


        if len(vm_name) == 0:
            return "Please select at least one virtual machine."

        # remove PR Portal from the list
        if 'PR-Portal' in vm_name:
            vm_name.remove('PR-Portal')

        # init helpers
        # init progress recorder
        vm_helper = VmHelper()
        progress_recorder = ProgressRecorder(self)

        # login
        # disconnect vc
        si = vm_helper.vm_login()
        atexit.register(connect.Disconnect, si)

        # dc_list = _revert['data_center']
        # host_list = _revert['host']
        # rp_list = _revert['resource_pool']
        existing_vm = []
        vm_obj_list = []


        if is_cluster == 1:
            res = revert_all_script.revert_all_cluster(si, cluster_name)

            if res['status'] == "success":
                vm_obj_list = res["message"]
            else:
                progress_recorder.set_progress(0, 100, res["message"])
                logger.info(res["message"])
                return res["message"]


        else:

            dc_list = _revert['data_center']
            host_list = _revert['host']
            rp_list = _revert['resource_pool']


            for i in range(len(dc_list)):
                dc_response = vm_helper.get_dc(si, dc_list[i])
                if dc_response['status'] == "success":
                    dc = dc_response['res']
                else:
                    return dc_response['res']

                host = si.content.searchIndex.FindChild(dc.hostFolder, host_list[i])
                rs = si.content.searchIndex.FindChild(host.resourcePool, rp_list[i])
                child_rs_obj_list = rs.resourcePool


                for i in child_rs_obj_list:
                    temp_vm_obj = i.vm
                    for j in temp_vm_obj:
                        vm_obj_list.append(j)


        for vm in vm_obj_list:
            existing_vm.append(vm.name)

        # total number of machines
        no_of_vms = len(vm_name)

        # initiate the progress bar
        progress_recorder.set_progress(0, 100, 'Reverting machines')



        for i in range(no_of_vms):
            if vm_name[i] in existing_vm:
                index = existing_vm.index(vm_name[i])
                vm_obj = vm_obj_list[index]

                # calculate percentage
                percentage = (i + 1) / (no_of_vms + 1) * 100
                progress_recorder.set_progress(percentage, 100, 'Reverting {}'.format(vm_name[i]))

                if vm_obj.snapshot is None:
                    # progress_recorder.set_progress(100, 100, description=f'Virtual Machine {str(vm_obj.name)} does not have any snapshots')
                    print("Exception occurred while reverting the snapshot. {} doesn't have any snapshots".format(str(vm_obj.name)))
                    print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@2")
                else:
                    snapshot_name = vm_obj.name + "_SS"
                    snap_obj = get_snapshots_by_name_recursively(vm_obj.snapshot.rootSnapshotList, snapshot_name)

                    if len(snap_obj) == 1:
                        if format(vm_obj.runtime.powerState) == "poweredOn":

                            task_power_off = vm_obj.PowerOffVM_Task()
                            progress_recorder.set_progress(percentage, 100, 'Reverting {}: Switching off machine'.format(vm_name[i]))
                            task_res_so = vm_helper.wait_for_task(task_power_off, "switching off machine : " + vm_name[i])
                            if task_res_so['status'] == "error":
                                return 'Exception occurred while switching off the VM ' + str(vm_name[i]) + ', ' + str(task_res_so['res'])

                        # revert vm machine
                        snap_obj = snap_obj[0].snapshot
                        task_revert = snap_obj.RevertToSnapshot_Task()
                        progress_recorder.set_progress(percentage, 100, 'Reverting {}: Restoring snapshot'.format(vm_name[i]))
                        task_res_rev = vm_helper.wait_for_task(task_revert, "reverting the machine : " + vm_name[i])
                        if task_res_rev['status'] == "error":
                            return 'Exception occurred while reverting the VM ' + str(vm_name[i]) + ', ' + str(task_res_rev['res'])

                        # power on vm machine
                        if format(vm_obj.runtime.powerState) != "poweredOn":
                            task_power_on = vm_obj.PowerOn()

                            # send the progress to the celery db
                            progress_recorder.set_progress(percentage, 100, 'Reverting {}: Switching on'.format(vm_name[i]))
                            task_res_po = vm_helper.wait_for_task(task_power_on, "switching on machine : " + vm_name[i])
                            if task_res_po['status'] == "error":
                                return 'Exception occurred while Switching on the VM ' + str(vm_name[i]) + ', ' + str(task_res_po['res'])
                    else:
                        # stop the task and send final status with error to the db
                        progress_recorder.set_progress(100, 100, description=f'Snapshot {snapshot_name} not available')
                        return "Exception occurred while reverting the snapshot. " + snapshot_name + " not available."

            else:
                print("Machine {} does not exist".format(vm_name[i]))
                progress_recorder.set_progress(100, 100, description=f'Virtual Machine {str(vm_name[i])} does not exist')
                # return "Exception occurred while reverting the snapshot." + str(vm_name[i]) + " doesn't exist."

        # stop the task and send final status to the db
        progress_recorder.set_progress(90, 100, 'sleeping for few minutes')
        time.sleep(600)
        progress_recorder.set_progress(100, 100, 'Successful!')

        logger_message = f"Successfully reverted all machines"
        logger.info(logger_message)
        audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

        return 200
    except Exception as unknown_exception:
        logger_message = f"Exception occurred while reverting all machines: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

        return "Exception occurred while reverting the snapshot." + str(unknown_exception)


def get_snapshots_by_name_recursively(snapshots, snapname):
    snap_obj = []
    for snapshot in snapshots:
        if snapshot.name == snapname:
            snap_obj.append(snapshot)
        else:
            snap_obj = snap_obj + get_snapshots_by_name_recursively(
                snapshot.childSnapshotList, snapname)
    return snap_obj

