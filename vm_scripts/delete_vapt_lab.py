from django.http import HttpResponse, Http404, FileResponse, JsonResponse

# celery
from celery import shared_task
from celery_progress.backend import ProgressRecorder

from vm_scripts.helpers import VmHelper
from vm_scripts.machines import Machines

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'



@shared_task(bind=True, name="Deleting VAPT labs")
def delete_vapt_lab(self,default_values,**kwargs):
    # for celery progress bar
    progress_recorder = ProgressRecorder(self)
    try:
        # init helpers
        vm_helper = VmHelper()
        machine_helper = Machines()

        # login to vsphere
        service_instance = vm_helper.vm_login()

        assigned_machine_list = []


        for datacenter in service_instance.content.rootFolder.childEntity:
            # get folders from all the data center
            folder_list = datacenter.vmFolder.childEntity

            # for required folder get the vms
            for folder_obj in folder_list:
                if folder_obj.name == default_values["folder"]:
                    ele_obj = folder_obj.childEntity

                    # check which ele is vm ware and delete them
                    for ele in ele_obj:
                       
                        # if element is not an template delete it
                        if ele.summary.config.template is False:
                    
                            vm_name = ele.name
                            delete_machine = machine_helper.delete_vm(
                                            service_instance,
                                            vm_name,
                                            default_values
                                        )

                            print(delete_machine['res'])
                            if delete_machine['status'] != "success":
                                logger_message = f"Error while deleting the VAPT lab: {str(delete_machine['res'])}"
                                logger.error(logger_message)
                                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                                # progress_recorder.set_progress(100, 100, description='Error while setting up the lab!')
                                print(delete_machine['res'])
                                logger.info("Error occurred while assigning the ip address.Please delete vms manually before trying again.")
                                return "Exception occurred while deleting the lab. Please delete all the clone vms manually."

                            logger_message = f"VAPT lab deleted successfully!"
                            logger.info(logger_message)
                            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))
    except Exception as e:
        logger_message = f"Exception occurred while deleting the VAPT lab: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        # progress_recorder.set_progress(100, 100, description='Error while setting up the lab!')
        return "Exception occurred while preparing the lab." 

