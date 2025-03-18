from pyVmomi import vim
import time
from .helpers import VmHelper
from pyVim.connect import SmartConnect, Disconnect
# from vm_scripts.machines import Machines

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'


def take_snapshot_vm(si, vm_name, defaults):
    try:
        print("here: take-snapshot_vm: ", vm_name, defaults)
        snapshot_name = defaults['snapshot_name']
        description = defaults['description']
        str_folder = defaults.get("folder", "")

        if isinstance(defaults["resource_pool"], list):
            str_resource_pool = defaults['resource_pool'][0]
        else:
            str_resource_pool = defaults['resource_pool']

        # when use_vm_memory is True: Captures the full state of the VM and ensures data consistency.
        # when use_vm_memory is False: Fast snapshot creation with no memory or application-level consistency.
        # Setting use_vm_memory to True by default
        use_vm_memory = defaults.get("use_vm_memory", True)
        power_off_vm_on_success = defaults.get("power_off_vm_on_success", "NO")

        # init helpers
        vm_helper = VmHelper()

        # Get the VM object
        vm_obj_response = vm_helper.get_vm_obj(vm_name, defaults['data_center'], defaults['host'], str_resource_pool, str_folder, defaults['is_cluster'])


        if vm_obj_response and vm_obj_response["status"] == "success" and vm_obj_response["res"] is not None:
            vm = vm_obj_response["res"]
        else:
            logger_message = "Error while taking snapshot for VM: ()".format(str(vm_obj_response["res"]))
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            res = {"status": "error", "res": vm_obj_response["res"]}
            return res


        # Create Snapshot
        print("here: creating snapshot: ")
        # Step 1: Create a snapshot
        # memory = False
        memory = use_vm_memory
        quiesce = False
        task = vm.CreateSnapshot(snapshot_name, description, memory, quiesce)

        # Monitor the snapshot task
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            time.sleep(1)

        if task.info.state == vim.TaskInfo.State.success:
            logger_message = f"Snapshot taken successfully for the VM"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            print("Snapshot created successfully!")
            if power_off_vm_on_success == "NO":
                return {"status": "success", "res": f"The `{snapshot_name}` snapshot created successfully!"}
        else:
            logger_message = f"Error while taking snapshot for VM: {str(task.info.error)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            print(f"Failed to create snapshot: {task.info.error}")
            return {"status": "error", "res": f"Snapshot creation failed: {task.info.error.msg}"}

        if power_off_vm_on_success == "YES":

            # Step 2: Power off the VM
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                print("Powering off the VM...")
                task = vm.PowerOffVM_Task()

                # Monitor the power-off task
                while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                    time.sleep(1)

                if task.info.state == vim.TaskInfo.State.success:
                    res = {
                        "status": "success",
                        "res": "The snapshot was successfully created, and the virtual machine was powered off"
                    }
                    print(res)
                    return res

                else:
                    return {"status": "success",
                            "res": f"The snapshot was successfully created, and failed to power off VM: {task.info.error}"}
            else:
                res = {
                        "status": "success",
                        "res": "The snapshot was successfully created, and the virtual machine was powered off"
                       }
                print(res)
                return res

    except Exception as e:
        logger_message = f"Exception occurred while taking snapshot for VM: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)
        return {"status": "error", "res": f"Exception occurred while taking snapshot: {str(e)}"}

    finally:
        print("here: finally")
        # Ensure the connection is always closed
        Disconnect(si)


def delete_snapshot_vm(si, vm_name, defaults):
    """
        Deletes a snapshot by name from the specified VM.

        :param vm: The VirtualMachine object
        :param snapshot_name: The name of the snapshot to delete
        :param remove_children: Boolean, if True, removes all children snapshots
        :return: result of delete snapshot operation
        """
    try:
        print("here: delete-snapshot_vm: ", vm_name, defaults)
        snapshot_name = defaults['snapshot_name']
        # description = defaults['description']

        str_folder = defaults.get("folder", "")

        if isinstance(defaults["resource_pool"], list):
            str_resource_pool = defaults['resource_pool'][0]
        else:
            str_resource_pool = defaults['resource_pool']

        # If you set remove_children to True, It will delete all it's child snapshots as well
        remove_children = False

        # init helpers
        vm_helper = VmHelper()

        # Get the VM object
        vm_obj_response = vm_helper.get_vm_obj(vm_name, defaults['data_center'], defaults['host'], str_resource_pool, str_folder, defaults['is_cluster'])

        if vm_obj_response and vm_obj_response["status"] == "success" and vm_obj_response["res"] is not None:
            vm = vm_obj_response["res"]
        else:
            logger_message = f"Error while deleting the snapshot for VM: {str(vm_obj_response["res"])}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            res = {"status": "error", "res": vm_obj_response["res"]}
            return res

        print(f"here: vm found: {str(vm)}")

        # ==============Delete Snapshot=======================================
        print("here: deleting snapshot from vSphere: ")

        if vm.snapshot:

            # Get the snapshot tree
            snapshot_tree = vm.snapshot.rootSnapshotList

            # Traverse snapshot tree to find the snapshot
            def find_snapshot_in_tree(snapshot_list, target_name):
                for snapshot in snapshot_list:
                    if snapshot.name == target_name:
                        return snapshot.snapshot
                    if snapshot.childSnapshotList:
                        found_snapshot = find_snapshot_in_tree(snapshot.childSnapshotList, target_name)
                        if found_snapshot:
                            return found_snapshot

                return None

            # Find the target snapshot
            target_snapshot = find_snapshot_in_tree(snapshot_tree, snapshot_name)

            if not target_snapshot:
                print(f"Snapshot '{snapshot_name}' not found for VM '{vm.name}'.")
                return {"status": "error", "res": f"Snapshot '{snapshot_name}' not found for VM '{vm.name}'."}

            # Remove the snapshot
            print(f"Deleting snapshot '{snapshot_name}' for VM '{vm.name}'...")

            # Step1: Deleting Snapshot
            task = target_snapshot.RemoveSnapshot_Task(remove_children)

            # Monitor the snapshot task
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(1)

            if task.info.state == vim.TaskInfo.State.success:
                logger_message = f"Snapshot deleted successfully for the VM"
                logger.info(logger_message)
                audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

                print(f"The {snapshot_name} snapshot deleted successfully!")
                return {"status": "success", "res": f"The `{snapshot_name}` snapshot deleted successfully!"}
            else:
                logger_message = f"Failed to delete a snapshot"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                print(f"Failed to delete a snapshot: {task.info.error}")
                return {"status": "error", "res": f"Snapshot deletion failed: {task.info.error.msg}"}

        else:
            logger_message = f"The VM don't have snapshots to delete"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            print(f"here: The {vm_name} VM don't have snapshots")
            return {"status": "error", "res": f"The {vm_name} VM don't have snapshots"}

        # ---------------------------------------------------------------
    except Exception as e:
        logger_message = f"Exception occurred while deleting the snapshot for VM: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return {"status": "error", "res": f"Exception occurred while deleting snapshot: {str(e)}"}

    finally:
        print("here: finally")
        # Ensure the connection is always closed
        Disconnect(si)


def revert_snapshot_vm(si, vm_name, defaults):
    try:
        print("here: revert-snapshot_vm: ", vm_name, defaults)
        snapshot_name = defaults['snapshot_name']
        # description = defaults['description']
        str_folder = defaults.get("folder", "")

        if isinstance(defaults["resource_pool"], list):
            str_resource_pool = defaults['resource_pool'][0]
        else:
            str_resource_pool = defaults['resource_pool']

        # init helpers
        vm_helper = VmHelper()

        # Get the VM object
        vm_obj_response = vm_helper.get_vm_obj(vm_name, defaults['data_center'], defaults['host'], str_resource_pool, str_folder, defaults['is_cluster'])

        print(f"here: revert-snapshot: vm_obj_response: {str(vm_obj_response)}")

        if vm_obj_response and vm_obj_response["status"] == "success" and vm_obj_response["res"] is not None:
            vm = vm_obj_response["res"]
        else:
            logger_message = f"Error while reverting the snapshot for VM: {str(vm_obj_response["res"])}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            res = {"status": "error", "res": vm_obj_response["res"]}
            return res

        print(f"here: vm found: {str(vm)}")

        # ==============Revert Snapshot=======================================
        print("here: reverting the snapshot: ")

        if vm.snapshot:

            # Get the snapshot tree
            snapshot_tree = vm.snapshot.rootSnapshotList

            # Traverse snapshot tree to find the snapshot
            def find_snapshot_in_tree(snapshot_list, target_name):
                for snapshot in snapshot_list:
                    if snapshot.name == target_name:
                        return snapshot.snapshot
                    if snapshot.childSnapshotList:
                        found_snapshot = find_snapshot_in_tree(snapshot.childSnapshotList, target_name)
                        if found_snapshot:
                            return found_snapshot

                return None

            # Find the target snapshot
            target_snapshot = find_snapshot_in_tree(snapshot_tree, snapshot_name)

            if not target_snapshot:
                logger_message = f"Snapshot not found to revert"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                print(f"Snapshot '{snapshot_name}' not found for VM '{vm.name}'.")
                return {"status": "error", "res": f"Snapshot '{snapshot_name}' not found for VM '{vm.name}'."}

            # Revert the snapshot
            print(f"Reverting snapshot '{snapshot_name}' for VM '{vm.name}'...")

            # Step1: Reverting the Snapshot
            task = target_snapshot.RevertToSnapshot_Task()

            # Monitor the snapshot task
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(1)

            if task.info.state == vim.TaskInfo.State.success:
                logger_message = f"Snapshot reverted successfully for the VM"
                logger.info(logger_message)
                audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

                print(f"The {snapshot_name} snapshot reverted successfully!")
                return {"status": "success", "res": f"The `{snapshot_name}` snapshot reverted successfully!"}
            else:
                logger_message = f"Failed to revert a snapshot of the VM"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                print(f"Failed to revert snapshot: {task.info.error}")
                return {"status": "error", "res": f"Snapshot reverting failed: {task.info.error.msg}"}

        else:
            print(f"here: The {vm_name} VM don't have snapshots")
            return {"status": "error", "res": f"The {vm_name} VM don't have snapshots"}

        # -------------------------------------------------------------------------
    except Exception as e:
        logger_message = f"Exception occurred while reverting the snapshot for VM: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)
        return {"status": "error", "res": f"Exception occurred while reverting snapshot: {str(e)}"}

    finally:
        print("here: finally")
        # Ensure the connection is always closed
        Disconnect(si)

