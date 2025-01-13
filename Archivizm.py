import os
import time
import psutil
from psutil._common import bytes2human
from rich.console import Console
from rich.table import Table
from rich.live import Live
import questionary

print("""
  ▒▓██████▓▒  ▒▓███████▓▒   ▒▓██████▓▒  ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓████████▓▒ ▒▓██████████████▓▒   
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒  
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▓█▓▒  ▒▓█▓▒      ▒▓██▓▒  ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒  
 ▒▓████████▓▒ ▒▓███████▓▒  ▒▓█▓▒        ▒▓████████▓▒ ▒▓█▓▒  ▒▓█▓▒ ▓█▓▒  ▒▓█▓▒    ▒▓██▓▒    ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒  
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒   ▒▓█▓▓█▓▒   ▒▓█▓▒  ▒▓██▓▒      ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒  
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒   ▒▓█▓▓█▓▒   ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒  
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓██████▓▒  ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒    ▒▓██▓▒    ▒▓█▓▒ ▒▓████████▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒                                                                                                                                                                                                                        
""")


def deviceList():
    partitions = psutil.disk_partitions()
    table = Table(title="Device List")
    

    #Columns
    columns = ["Device", "Type", "Filesystem", "Size"]
    for column in columns:
        table.add_column(column)
    
    #Rows
    for partition in partitions:
        if get_access(partition.device):
            table.add_row(partition.device, partition.opts, partition.fstype, bytes2human(psutil.disk_usage(partition.device).total))
        else:
            table.add_row(partition.device, "N/A", "N/A", "N/A")
    return table

def get_access(device):
    try:
        if psutil.disk_usage(device).total > 0:
            return True
    except PermissionError:
        return False
    except FileNotFoundError:
        return False
    except OSError as e:
        return False
    return None   


def chooseDevice():
    partitions = psutil.disk_partitions()
    
    #Device Dictionary
    deviceDict = {}
    for partition in partitions:
        deviceDict[partition.device] =  partition
    

    question = questionary.checkbox(
        "View Device:",
        choices = list(deviceDict.keys())
        ).ask()
    
    print(question)

   

def deviceView(partition):

    print(f"Device: {partition.device}")
    print(f"Type: {partition.opts}")
    print(f"Filesystem: {partition.fstype}")
    print(f"Size: {bytes2human(psutil.disk_usage(partition.device).used)} | {bytes2human(psutil.disk_usage(partition.device).total)}")

#Old Print Method
'''
def getDevices():
    partitions = psutil.disk_partitions()
    for partition in partitions:
        if(get_access(partition.device)):
            print(f"Device: {partition.device}")
            print(f"Type: {partition.opts}")
            print(f"Filesystem: {partition.fstype}")
            print(f"Size: {bytes2human(psutil.disk_usage(partition.device).used)} | {bytes2human(psutil.disk_usage(partition.device).total)}")
            print("-" * 20)
'''


#print(psutil.disk_partitions()) 
with Live(deviceList(), refresh_per_second=4) as live:
    while True:
        time.sleep(0.4)
        live.update(deviceList())


#number of files
#content filetypes


#select device to view

