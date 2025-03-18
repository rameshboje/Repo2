from pyVmomi import vim, vmodl
from .helpers import VmHelper
# test
import sys
import os
from django.conf import settings

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'



inputs = {'data_store': settings.VAPT_DS}


class AddDisk:
    @staticmethod
    def add_cd_rom_iso(si, vm, iso):
        try:
            # init Helper
            vm_helper = VmHelper()
            print("Attaching iso {0} to CD drive".format(iso))
            content = si.RetrieveContent()

            cdspec = vim.vm.device.VirtualDeviceSpec()
            cdspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            cdspec.device = vim.vm.device.VirtualCdrom()
            cdspec.device.key = 3000
            cdspec.device.controllerKey = 200
            cdspec.device.unitNumber = 0

            cdspec.device.deviceInfo = vim.Description()
            cdspec.device.deviceInfo.label = 'CD/DVD drive 1'
            cdspec.device.deviceInfo.summary = 'ISO'

            cdspec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            cdspec.device.backing.fileName = iso
            datastore_response = VmHelper.get_obj(content, [vim.Datastore], inputs['data_store'])
            if datastore_response['status'] == "success":
                datastore = datastore_response['res']
            else:
                return datastore_response
            cdspec.device.backing.datastore = datastore

            cdspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdspec.device.connectable.startConnected = True
            cdspec.device.connectable.allowGuestControl = True
            cdspec.device.connectable.connected = False
            cdspec.device.connectable.status = 'untried'

            # create the Cd-Rom drive
            vmconf = vim.vm.ConfigSpec()
            vmconf.deviceChange = [cdspec]
            dev_changes = []
            dev_changes.append(cdspec)
            vmconf.deviceChange = dev_changes

            task = vm.ReconfigVM_Task(spec=vmconf)
            task_res_cd = vm_helper.wait_for_task(task, "adding cd rom")
            if task_res_cd['status'] == "error":
                logger_message = f"Error while adding CD ROM to VM: {str(task_res_cd['res'])}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                _json = {
                    'res': 'Exception occurred while adding the CD ROM to the VM, error ' + str(task_res_cd['res']),
                    'status': "error"
                }
                return _json
            json_ = {
                'res': "CD ROM added successfully",
                'status': "success"
            }

            logger_message = f"CD ROM added successfully to the VM"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as vm_exception:
            logger_message = f"Exception occurred while adding the CD ROM to the VM: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while adding the CD ROM.' + str(vm_exception)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_
        # except Exception as e:
        #     response_messages = 'Exception occurred: Unable to add CD ROM ' + str(e)
        #     json_ = {
        #         'res': response_messages,
        #         'status': "error"
        #     }
        #     return json_

    @staticmethod
    def add_scsi_controller(vm):
        vm_helper = VmHelper()
        # setting controller information
        try:
            print("scsi controller 1")
            scsi_ctr = vim.vm.device.VirtualDeviceSpec()
            scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            scsi_ctr.device = vim.vm.device.VirtualLsiLogicController()
            scsi_ctr.device.sharedBus = 'noSharing'
            # setting backings
            spec = vim.vm.ConfigSpec()

            # creating the list
            dev_changes = []
            dev_changes.append(scsi_ctr)
            spec.deviceChange = dev_changes

            print("scsi controller 2")
            # This submits the configspec and performs all the tasks contained
            task = vm.ReconfigVM_Task(spec=spec)
            task_res_sc = vm_helper.wait_for_task(task, "adding scsi controller")
            if task_res_sc['status'] == "error":
                logger_message = f"Error while adding SCSI to VM: {str(task_res_sc['res'])}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                _json = {
                    'res': 'Exception occurred while adding the SCSI to the VM, ' + str(task_res_sc['res']),
                    'status': "error"
                }
                return _json

            json_ = {
                'res': "SCSI added successfully",
                'status': "success"
            }

            logger_message = f"SCSI added successfully for the VM!"
            logger.info(logger_message)
            audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

            return json_
        except Exception as vm_exception:
            logger_message = f"Exception occurred while adding the SCSI to the VM: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while adding the SCSI to the VM.' + str(vm_exception)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_
        # except Exception as e:
        #     response_messages = 'Exception occurred: Unable to add SCSI while adding disk ' + str(e)
        #     json_ = {
        #         'res': response_messages,
        #         'status': "error"
        #     }
        #     return json_

    @staticmethod
    def add_hard_disk(vm, disk_size):
        try:
            vm_helper = VmHelper()
            disk_type = 'thin'
            spec = vim.vm.ConfigSpec()
            # get all disks on a VM, set unit_number to the next available
            unit_number = 0
            controller = None

            for dev in vm.config.hardware.device:
                if hasattr(dev.backing, 'fileName'):
                    unit_number = int(dev.unitNumber) + 1
                    if unit_number == 7:
                        unit_number += 1
                    if unit_number >= 16:
                        json_ = {
                            'res': "We don't support this many disks",
                            'status': "error"
                        }
                        return json_
                if isinstance(dev, vim.vm.device.VirtualSCSIController):
                    controller = dev

            # add disk here
            dev_changes = []
            new_disk_kb = int(disk_size) * 1024 * 1024
            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.fileOperation = "create"
            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            disk_spec.device = vim.vm.device.VirtualDisk()
            disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
            if disk_type == 'thin':
                disk_spec.device.backing.thinProvisioned = True

            disk_spec.device.backing.diskMode = 'persistent'
            disk_spec.device.unitNumber = unit_number
            disk_spec.device.capacityInKB = new_disk_kb
            disk_spec.device.controllerKey = controller.key
            dev_changes.append(disk_spec)
            spec.deviceChange = dev_changes
            task = vm.ReconfigVM_Task(spec=spec)
            task_res_disk = vm_helper.wait_for_task(task, "adding hard disk")
            if task_res_disk['status'] == "error":
                logger_message = f"Error while adding hard disk to VM: {str(task_res_disk['res'])}"
                logger.error(logger_message)
                audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))

                _json = {
                    'res': 'Exception occurred while adding the hard disk, ' + str(task_res_disk['res']),
                    'status': "error"
                }
                return _json

            print("%sGB disk added to %s" % (disk_size, vm.config.name))

            json_ = {
                'res': str(disk_size) + "Hard disk added successfully to " + str(vm.config.name),
                'status': "success"
            }

            logger_message = str(disk_size) + "Hard disk added successfully to " + str(vm.config.name)
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
                
            return json_
        except Exception as vm_exception:
            logger_message = f"Exception occurred while adding the hard disk: {str(vm_exception)}"
            logger.error(logger_message)
            audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
            print(logger_message)

            response_messages = 'Exception occurred while adding the hard disk.' + str(vm_exception)
            json_ = {
                'res': response_messages,
                'status': "error"
            }
            return json_
        # except Exception as e:
        #     response_messages = 'Exception occurred: Unable to add hard disk' + str(e)
        #     json_ = {
        #         'res': response_messages,
        #         'status': "error"
        #     }
        #     return json_
        # except vim.fault as error:
        #     logger.info(error)
        #     print("hard disk error "+ error)
        #     return error.msg

        # except Exception as unknown_exception:
        #     exc_type, exc_obj, exc_tb = sys.exc_info()
        #     print(".......add hard disk exception........")
        #     print(exc_type.__name__)
        #     print(">>>>>>>>>>>>")
        #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #     print(exc_type, fname, exc_tb.tb_lineno)
        #     logger.info(unknown_exception)
        #     print("hard disk exece " + unknown_exception)
        #     return "Exception occured. "+ str(unknown_exception)

