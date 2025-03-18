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

def create_template_vm(si, vm_name, defaults):
    try:
        # get the values from the default variable
        template_name = defaults['template_name']
        is_cluster = defaults['is_cluster']
        str_cluster_name = defaults.get("cluster_name", "")
        str_template_folder = defaults.get("template_folder", "")
        arr_data_center = defaults['data_center']
        arr_host = defaults['host']


        # if rp is list get the first value
        if isinstance(defaults["resource_pool"], list):
            str_resource_pool = defaults['resource_pool'][0]
        else:
            str_resource_pool = defaults['resource_pool']


        # init helpers
        vm_helper = VmHelper()


        # Get the VM object without folder name
        vm_obj_response = vm_helper.find_vm_anywhere(vm_name, arr_data_center, arr_host, is_cluster)
        print(f"here: create-template: vm_obj_response: {str(vm_obj_response)}")
        if vm_obj_response and vm_obj_response["status"] == "success" and vm_obj_response["res"] is not None:
            vm = vm_obj_response["res"]
        else:
            res = {"status": "error", "res": vm_obj_response["res"]}
            logger_message = f"Error while creating template for a VM: {str(vm_obj_response["res"])}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            return res
        
        print(f"here: vm found: {str(vm)}")

        # Get the Resource Pool or Cluster object
        res_resource_pool_obj = vm_helper.get_resource_pool_obj(arr_data_center, arr_host, str_resource_pool, str_cluster_name, is_cluster)
        print(f"here: create-template: res_resource_pool_obj: {str(res_resource_pool_obj)}")


        # # -----------Code Worked for specific resource pool------------- if res_resource_pool_obj and
        # res_resource_pool_obj["status"] == "success" and res_resource_pool_obj["res"] is not None:
        # obj_resource_pool = res_resource_pool_obj["res"] else: res = {"status": "error",
        # "res": res_resource_pool_obj["res"]} return res #
        # ----------------------------------------------------------------


        if res_resource_pool_obj and res_resource_pool_obj["status"] == "success" and res_resource_pool_obj[
            "res"] is not None:
            print("here: resource pool obj found!")
            obj_resource_pool = res_resource_pool_obj["res"]
        else:
            obj_resource_pool = None
        print(f"here: res-resource_pool_obj found!: {str(res_resource_pool_obj)}")



        # Get the template folder object
        res_template_folder_obj = vm_helper.get_folder_obj(str_template_folder)
        print(f"here: create-template: res_template_folder_obj: {str(res_template_folder_obj)}")
        if res_template_folder_obj and res_template_folder_obj["status"] == "success" and res_template_folder_obj[
            "res"] is not None:
            template_folder_obj = res_template_folder_obj["res"]
        else:
            logger_message = f"Error while creating template for a VM: {str(res_template_folder_obj["res"])}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            res = {"status": "error", "res": res_template_folder_obj["res"]}
            return res
        print(f"here: template_folder_obj found: {str(template_folder_obj)}")

        # Create template
        print("here: creating template: ")
        objRelocateSpec = vim.vm.RelocateSpec()
        objCloneSpec = vim.vm.CloneSpec()
        # objRelocateSpec.datastore = datastore


        # If the resource pool obj found then use specified resource pool else by pass it.,
        # If the resource pool is not assigned, It wiil assign default resource pool,
        # vSphere will automatically assign the correct resource pool.
        if obj_resource_pool is not None:
            objRelocateSpec.pool = obj_resource_pool
        objCloneSpec.location = objRelocateSpec
        objCloneSpec.template = True
        objCloneSpec.powerOn = False


        task = vm.Clone(folder=template_folder_obj, name=template_name, spec=objCloneSpec)
        # Monitor the template task
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            time.sleep(1)

        if task.info.state == vim.TaskInfo.State.success:
            print("Template created successfully!")
            logger_message = f"Template creating template for a VM"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return {"status": "success", "res": f"The `{template_name}` template created successfully!"}
        else:
            print(f"Failed to create template: {task.info.error}")
            logger_message = f"Error while creating template for a VM: Failed to create template: {str(task.info.error)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            return {"status": "error", "res": f"Template creation failed: {task.info.error.msg}"}
    except Exception as e:
        logger_message = f"Exception occurred while creating template for a VM: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)
        return {"status": "error", "res": f"Exception occurred while taking template: {str(e)}"}

    finally:
        print("here: finally")
        # Ensure the connection is always closed
        Disconnect(si)


def delete_template_vm(si, vm_name, defaults):
    """
        Deletes a template by name from the specified VM.
        :param vm: The VirtualMachine object
        :param template_name: The name of the template to delete
        :return: result of delete template operation
        """
    try:
        print("here: delete-template_vm: ", vm_name, defaults)
        template_name = defaults['template_name']
        # description = defaults['description']
        str_template_folder = defaults.get("template_folder", "")

        # init helpers
        vm_helper = VmHelper()

        # Get the template object
        template_obj_response = vm_helper.get_vm_template_obj(str_template_folder, template_name)

        if template_obj_response and template_obj_response["status"] == "success" and template_obj_response["res"] is not None:
            obj_template = template_obj_response["res"]
        else:
            logger_message = f"Error while deleting the VM template: {str(template_obj_response['res'])}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            res = {"status": "error", "res": template_obj_response["res"]}
            return res

        print(f"here: obj-template found: {str(obj_template)}")

        # ==============Delete Template=======================================
        print("here: deleting template from vSphere: ")

        task = obj_template.Destroy_Task()

        # Monitor the template task
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            time.sleep(1)

        if task.info.state == vim.TaskInfo.State.success:

            logger_message = f"Template deleted successfully!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            print(f"The {template_name} template deleted successfully!")
            return {"status": "success", "res": f"The `{template_name}` template deleted successfully!"}
        else:
            logger_message = f"Error while deleting the VM template: Failed to delete a template: {str(task.info.error)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

            print(f"Failed to delete a template: {task.info.error}")
            return {"status": "error", "res": f"Template deletion failed: {task.info.error.msg}"}

        # ---------------------------------------------------------------
    except Exception as e:
        logger_message = f"Exception occurred while deleting the VM template: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        return {"status": "error", "res": f"Exception occurred while deleting template: {str(e)}"}

    finally:
        print("here: finally")
        # Ensure the connection is always closed
        Disconnect(si)

