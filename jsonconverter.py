import json
from pathlib import Path
import os
import capnp

messages = capnp.load("deepdrr_zmq/deepdrrzmq/messages.capnp")
def extract_topic_data_from_log(log_file):
    entries = messages.LogEntry.read_multiple_bytes(log_file.read_bytes())
    topic_data = []
    unique_topics = []
    i = 0
    for entry in entries:
        topic = entry.topic.decode('utf-8')
        msgdict = {'topic': topic}
        file_name = os.path.splitext(log_file.name)[0] 
        file_number = file_name.split("--")[-1] 
        # print(file_number + ' file '+str(len(topic_data))+' '+topic)#for debug
        if topic not in unique_topics:  # Add unique topics to the list
            unique_topics.append(topic)

        if topic.startswith("/mp/transform/"):
            with messages.SyncedTransformUpdate.from_bytes(entry.data) as transform:
                transform_dict = {}
                transform_dict['timestamp'] = transform.timestamp
                transform_dict['clientId'] = transform.clientId
                transforms = []
                for i in range(len(transform.transforms)):
                    transforms.append([x for x in transform.transforms[i].data])
                transform_dict['transforms'] = transforms
                msgdict['transforms'] = transform_dict 
        if topic.startswith("/mp/time/"):
            with messages.Time.from_bytes(entry.data) as time:
                msgdict['time'] = time.millis 
        if topic.startswith("/mp/setting"):
            with messages.SycnedSetting.from_bytes(entry.data) as setting_data:
                setting_data_dict = {}
                msgdict['timestamp'] = setting_data.timestamp
                msgdict['clientId'] = setting_data.clientId
                which = setting_data.setting.which()
                if which == 'uiControl':
                    setting = setting_data.setting.uiControl                   
                    setting_data_dict['patientMaterial'] = setting.patientMaterial
                    setting_data_dict['annotationSelection'] = list(setting.annotationError)
                    setting_data_dict['corridorIndicator'] = setting.corridorIndicator
                    setting_data_dict['carmIndicator'] = setting.carmIndicator
                    setting_data_dict['webcorridorerrorselect'] = setting.webcorridorerrorselect
                    setting_data_dict['webcorridorselection'] = setting.webcorridorselection
                    setting_data_dict['flippatient'] = setting.flippatient
                    setting_data_dict['viewIndicatorselfselect'] = setting.viewIndicatorselfselect
                    msgdict['uiControl'] = setting_data_dict   
                if which == 'arm':     
                    setting = setting_data.setting.arm.liveCapture  
                    msgdict['liveCapture'] = setting          
        topic_data.append(msgdict)
    return topic_data, unique_topics
def convert_pvrlog_to_json(log_folder):
    log_folder_path = Path(log_folder)
    pvrlog_files = log_folder_path.glob("*.pvrlog")
    for log_file in pvrlog_files:
        json_file_path = log_folder_path / f"{log_file.stem}.json"
        topic_data ,unique_topics= extract_topic_data_from_log(log_file)
        with open(json_file_path, 'w') as json_file:
            json.dump(topic_data, json_file, indent=4)
        # print(f"Converted {log_file.name} to JSON.")#for debug
    # print('--------------Unique Topics--------------')
    # for topic in unique_topics:
    #     print(topic)
    # print('---------------Convert Complete--------------')

if __name__ == '__main__':
    # log_folder = input("Enter the folder path containing .pvrlog files: ")
    log_folder = "C:/vrplog/7mfiyniy548ldjn8--2023-06-20-02-38-31"
    convert_pvrlog_to_json(log_folder)