import atexit
from pyVim import connect
from .helpers import VmHelper
from pyVmomi import vim, vmodl
import time
from vm_scripts import power_off_all as power_off_all_script
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


def power_off_all_cluster(si,cluster_name,vm_list,host_list):
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
                if host.name in host_list:
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
            'message': 'Exception occurred while fetching machines from cluster ' + str(response),
            'status': "error"
        }
        return res




@shared_task(bind=True,name='Powering off vm machines')
def power_off_all(self, cred_details,**kwargs):

    # init progress recorder
    vm_list = cred_details['machines']
    _vsphere_details = cred_details['exsi_details']['res']
    progress_recorder = ProgressRecorder(self)
    try:
        # remove PR Portal from the list
        if 'PR-Portal' in vm_list:
            vm_list.remove('PR-CRO')

        # init helpers
        vm_helper = VmHelper()

        # login
        si = vm_helper.vm_login()

        # disconnect vc
        atexit.register(connect.Disconnect, si)

        is_cluster = _vsphere_details['is_cluster']
        cluster_name = _vsphere_details['cluster_name']
        host_list = _vsphere_details['host']

        existing_vm = []
        vm_obj_list = []

        if is_cluster == 1:

            res = power_off_all_script.power_off_all_cluster(si, cluster_name,vm_list,host_list)

            if res['status'] == "success":
                vm_obj_list = res["message"]
                existing_vm = res["existing_vm"]
            else:
                progress_recorder.set_progress(0, 100, res["message"])
                logger.info(res["message"])
                return res["message"]
        else:

            dc_list = _vsphere_details['data_center']


            for i in range(len(dc_list)):
                dc_response = vm_helper.get_dc(si, dc_list[i])
                if dc_response['status'] == "success":
                    dc = dc_response['res']
                else:
                    return dc_response['res']


                for compute_resource in dc.hostFolder.childEntity:
                    for host in compute_resource.host:
                        if host.name in host_list:
                            print(host)
                            for vm in host.vm:
                                if vm.name in vm_list and not vm.config.template:
                                    vm_obj_list.append(vm)
                                    existing_vm.append(vm.name)


        # total number of machines
        no_of_vms = len(vm_list)

        # initiate the progress bar
        progress_recorder.set_progress(0, 100, 'Switching off {} machines'.format(no_of_vms))

        for i in range(len(vm_list)):
            # calculate percentage
            percentage = (i + 1) / no_of_vms * 100
            progress_recorder.set_progress(percentage, 100, 'Switching off machines')


            if vm_list[i] in existing_vm:
                index = existing_vm.index(vm_list[i])
                vm_obj = vm_obj_list[index]

                # temp
                progress_recorder.set_progress(percentage, 100, 'Switching off {}'.format(vm_list[i]))

                if vm_obj.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                # if vm_obj.runtime.powerState != "poweredOff":
                    task_power_off = vm_obj.PowerOffVM_Task()

                    progress_recorder.set_progress(percentage, 100, 'Switching off {}: '.format(vm_list[i]))

                    # Monitor the power-off task
                    while task_power_off.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                        time.sleep(1)

                    if task_power_off.info.state == vim.TaskInfo.State.success:
                        print("VM {} powered off successfully!".format(str(vm_list[i])))

                        logger_message = f"The VM {str(vm_list[i])} powered off successfully!"
                        logger.info(logger_message)
                        audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

                    else:
                        print("Failed to power off VM: {}".format(task_power_off.info.error))
                        res = {
                            "status": "error",
                            "res": "Exception occurred while switching off the VM {}: {}".format(str(vm_list[i]),task_power_off.info.error)
                        }
                        return res

            else:
                print("Machine {} does not exist".format(vm_list[i]))
                # progress_recorder.set_progress(self, percentage, 'Machine {} does not exist'.format(vm_name[i]))

                # return 'Exception occurred while switching off the VM.' + str(vm_name[i]) + " does not exist in the lab."

        # temp
        progress_recorder.set_progress(100, 100, 'Successful!')
        return 200
    except Exception as unknown_exception:

        logger_message = f"Exception occurred while switching off machine: {str(unknown_exception)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        progress_recorder.set_progress(30, 0, 'Failed while switching off Machine, please check celery log file')
        response = 'Exception occurred while switching off the Machine ' + str(unknown_exception)
        return 'Exception occurred while switching off the Machine.' + str(response)
