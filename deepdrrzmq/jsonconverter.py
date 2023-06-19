import json
from pathlib import Path

import capnp
from deepdrrzmq import messages


def extract_topic_data_from_log(log_file):
    entries = messages.LogEntry.read_multiple_bytes(log_file.read_bytes())
    topic_data = []
    for entry in entries:
        topic = entry.topic.decode('utf-8')
        data = entry.data.decode('utf-8')
        topic_data.append({'topic': topic, 'data': data})
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
    log_folder = input("Enter the folder path containing .pvrlog files: ")
    convert_pvrlog_to_json(log_folder)