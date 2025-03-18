from credentials.models import Credential
from notify.signals import notify
from users.models import User
from django.conf import settings
from settingspage.views import fetch_esxi_cred

# celery
from celery import shared_task
from celery_progress.backend import ProgressRecorder

from vm_scripts.helpers import VmHelper
from vm_scripts.machines import Machines
from vm_scripts.networks import Networks

import logging
from django.apps import apps
from utils import get_log_extra_paras

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit_logger')

module_name = __name__
app_name = apps.get_app_config(module_name.split('.')[0]).name
if app_name is None or app_name == "":
    app_name = 'NA'


@shared_task(bind=True, name="Setting up VAPT labs")
def prepare_vapt_lab(self, details, **kwargs):
    # for celery progress bar
    progress_recorder = ProgressRecorder(self)

    try:
        # init helpers
        vm_helper = VmHelper()
        machine_helper = Machines()
        network_helper = Networks()

        # login to vsphere
        service_instance = vm_helper.vm_login()

        cred_details = fetch_esxi_cred()

        if cred_details['status'] == 'success':
            default_values = cred_details['res']
        else:
            return cred_details

        default_values['folder'] = settings.TEMPLATE_FOLDER
        default_values['subnet'] = settings.VAPT_SUBNET
        default_values['gateway'] = settings.VAPT_GATEWAY
        default_values['dns'] = settings.DNS
        default_values['data_store_cluster'] = "NA"
        default_values['domain'] = "NA"

        # provide ip address from this range
        ip_range_available = settings.VAPT_IP_RANGE
        assigned_machine_list = []
        gateway_ip = 1

        # sample data for testing
        # details = [{'scenarios': 'Task08: uploading a Website ransomware', 'participants': 2, 'participants_list': ['student_4', 'student_3']}, {'scenarios': 'Task09: Exploiting http file server vulnerability', 'participants': 1, 'participants_list': ['student_5']}]

        for i in range(len(details)):
            machines = list(
                Credential.objects.filter(machine_used__contains=details[i]['scenarios']).values('username', 'password',
                                                                                                 'machine_name', 'ip',
                                                                                                 'rdp_ip', 'os'))

            if len(machines) > 0:
                for machine in machines:
                    machine_name = machine['machine_name']
                    username = machine['username']
                    password = machine['password']
                    os = machine['os']

                    details[i].update({"machines": machine_name})
                    details[i].update({"username": username})
                    details[i].update({"password": password})
                    details[i].update({"os": os})

        response_message = 'Fetching details about the vapt tasks '
        progress_recorder.set_progress(10, 100, description=response_message)

        created_machines = []
        for i in range(len(details)):
            for j in range(len(details[i]['participants_list'])):
                participant = details[i]['participants_list'][j]
                vm_name = details[i]['machines'] + "_" + str(participant)
                host_name = details[i]['machines']
                template_name = str(details[i]['machines'] + "_template")

                # create clone from the templates
                clone_machine = machine_helper.clone_from_template(
                    service_instance,
                    vm_name,
                    template_name,
                    default_values
                )

                response_message = 'Cloning machines '
                progress_recorder.set_progress(60, 100, description=response_message)

                # if machine is cloned successfully from the given template
                if clone_machine["status"] == "success":
                    # append list with all the created machines
                    created_machines.append(vm_name)

                    response_message = 'updating ip address of the machines '
                    progress_recorder.set_progress(80, 100, description=response_message)

                    # assign ip address to the newly created vm machine
                    # to keep track of assignd ip address #
                    gateway_ip = gateway_ip + 1
                    ip = ip_range_available + str(gateway_ip)
                    print(ip)
                    print(details)

                    assign_ip_res = network_helper.ip_assign(service_instance,
                                                             vm_name,
                                                             host_name,
                                                             ip, default_values,
                                                             details[i]['os'],
                                                             details[i]['username'],
                                                             details[i]['password']
                                                             )

                    # check for success assignement of ip address
                    # run the code if there is error while assigning the ip address
                    if assign_ip_res['status'] == "error":
                        logger.info(assign_ip_res['res'])

                        # delete the already created machines
                        if len(created_machines) > 0:
                            for del_vm in created_machines:
                                delete_machine = machine_helper.delete_vm(
                                    service_instance,
                                    del_vm,
                                    default_values
                                )
                                if delete_machine['status'] != "success":
                                    progress_recorder.set_progress(0, 100,
                                                                   description='Error while setting up the lab!')
                                    logger.info(delete_machine['res'])
                                    return "Exception occurred while preparing the lab. Please delete all the clone vms manually before trying again."
                                else:
                                    created_machines.remove(del_vm)

                        progress_recorder.set_progress(0, 100, description='Error while setting up the lab!')
                        return "Exception occurred while preparing the lab. Deleted cloned vms due to error" + \
                               assign_ip_res['res']
                    else:
                        # dictionary object to store the information of assigned server
                        # needed to send notification to aspirants
                        assigned_machine = {}
                        assigned_machine['ip'] = ip
                        assigned_machine['name'] = vm_name
                        assigned_machine['user'] = participant
                        assigned_machine_list.append(assigned_machine)

                # if there is error while cloning the vm from the template
                else:
                    # write code to delete the vm machines if error occurred
                    # while creating any clone
                    if len(created_machines) > 0:
                        for del_vm in created_machines:
                            delete_machine = machine_helper.delete_vm(
                                service_instance,
                                del_vm,
                                default_values
                            )
                            if delete_machine['status'] != "success":
                                logger.info(delete_machine['res'])
                                logger.info("Please delete vm" + str(del_vm) + " manually before trying again.")

                    progress_recorder.set_progress(0, 100, description='Error while setting up the lab!')
                    print(clone_machine["res"])
                    logger.info(clone_machine["res"])
                    return clone_machine["res"]

        # send notifications
        try:
            print(assigned_machine_list)
            for ele in assigned_machine_list:
                extra = {
                    'machine': "NA",
                    'rdp_ip': "NA",
                    'username': "NA",
                    'password': "NA",
                    'browser_url': ""
                }

                username = User.objects.get(username=ele['user'])
                sender = User.objects.get(username=kwargs["username"])
                notify.send(sender, recipient=username, actor=sender,
                            verb="VAPT Server Assigned ".format(kwargs["username"]),
                            description="VAPT Server with IP Address " + ele['ip'] + " has been assigned to you."
                                                                                     " You can start your activity on this server.",
                            nf_type='receive-red-cred', extra=extra)


        except Exception as err:
            progress_recorder.set_progress(0, 100, description='Error while setting up the lab!')
            logger.info(err)
            return "Exception occurred while sending notification to aspirant." + str(err)


        logger_message = f"VAPT lab prepared and started successfully"
        logger.info(logger_message)
        audit_logger.info(logger_message, extra=get_log_extra_paras(None, app_name))

        return "VAPT started successfully"
    except Exception as e:
        logger_message = f"Exception occurred while preparing vapt lab: {str(e)}"
        logger.error(logger_message)
        audit_logger.error(logger_message, extra=get_log_extra_paras(None, app_name))
        print(logger_message)

        progress_recorder.set_progress(0, 100, description='Error while setting up the lab!')
        return "Exception occurred while preparing the lab." 

