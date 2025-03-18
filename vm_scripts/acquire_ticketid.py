from pyVmomi import vim
from .helpers import VmHelper
from .machines import Machines
from vm_scripts.helpers import VmHelper

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'

class AcquireTicketID:
    # init helper
    _vm_helper = VmHelper()
    _machine_helper = Machines()


    def acquire_ticket(self, service_instance, vm_name):
        try:
            print("....taking console.....")
            content = service_instance.RetrieveContent()

            vm_response = self._vm_helper.get_obj(content, [vim.VirtualMachine], vm_name)
            if vm_response['status'] == "success":
                vm = vm_response['res']
            else:
                logger_message = f"Error while acquiring the ticket_id: {str(vm_response['res'])}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                return vm_response

            spec = vim.vm.ConfigSpec()

            # add Switch here

            acquire_ticket = vm.AcquireTicket(ticketType="webmks")
            ticket_id = acquire_ticket.ticket

            task = vm.ReconfigVM_Task(spec=spec)

            task_take_ticket_id = self._vm_helper.wait_for_task(task, "acquiring ticket id")
            if task_take_ticket_id['status'] == "error":
                logger_message = f"Error while acquiring the ticket_id: {str(task_take_ticket_id['res'])}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                json_ = {
                    'res': 'Exception occurred while acquiring the ticket id ' + str(vm_name) + ', ' + str(task_take_ticket_id['res']),
                    'status': "error"
                }
                return json_
            else:
                json_ = {
                    "status": "success",
                    "res": ticket_id
                }
                print(json_)
                return json_

        except Exception as exp:
            logger_message = f"Exception occurred while acquiring the ticket_id: {str(exp)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while acquiring the ticket id.' + str(exp)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_
