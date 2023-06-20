import json
from pathlib import Path

import capnp

messages = capnp.load("deepdrr_zmq/deepdrrzmq/messages.capnp")
def extract_topic_data_from_log(log_file):
    entries = messages.LogEntry.read_multiple_bytes(log_file.read_bytes())
    topic_data = []
    for entry in entries:
        topic = entry.topic.decode('utf-8')
        # data = entry.data.decode('ascii')
        # topic_data.append({'topic': topic, 'data': data})
        print(topic)
        topic_data.append({'topic': topic})

    return topic_data

def convert_pvrlog_to_json(log_folder):
    log_folder_path = Path(log_folder)
    pvrlog_files = log_folder_path.glob("*.pvrlog")
    for log_file in pvrlog_files:
        json_file_path = log_folder_path / f"{log_file.stem}.json"
        topic_data = extract_topic_data_from_log(log_file)
        with open(json_file_path, 'w') as json_file:
            json.dump(topic_data, json_file, indent=4)
        print(f"Converted {log_file.name} to JSON.")


# log_folder = input("Enter the folder path containing .pvrlog files: ")
# convert_pvrlog_to_json(log_folder)
if __name__ == '__main__':
    # log_folder = input("Enter the folder path containing .pvrlog files: ")
    log_folder = "C:/vrplog/gn6w7q6bvwivsb93--2023-06-20-00-21-42"
    convert_pvrlog_to_json(log_folder)