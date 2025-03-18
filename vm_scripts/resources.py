from pyVmomi import vim, vmodl
from pyVim import connect
import atexit


class Resources:

    def create_resource_pool(host):
        configSpec = vim.ResourceConfigSpec()
        cpuAllocationInfo = vim.ResourceAllocationInfo()
        memAllocationInfo = vim.ResourceAllocationInfo()
        sharesInfo = vim.SharesInfo(level='normal')

        cpuAllocationInfo.reservation = 0
        cpuAllocationInfo.expandableReservation = True
        cpuAllocationInfo.shares = sharesInfo
        cpuAllocationInfo.limit = -1

        memAllocationInfo.reservation = 0
        memAllocationInfo.expandableReservation = True
        memAllocationInfo.shares = sharesInfo
        memAllocationInfo.limit = -1

        configSpec.cpuAllocation = cpuAllocationInfo
        configSpec.memoryAllocation = memAllocationInfo
        host.CreateResourcePool("APITesting", configSpec)