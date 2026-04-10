import pandas as pd
import os
import pickle

# -------------------------------
# LOAD DATA (use raw strings)
# -------------------------------
logs_df = pd.read_csv(
    r"C:\Ruturaj\CTI-Dashboard-master\dataset\cybersecurity_threat_detection_logs.csv"
)

cloudwatch_df = pd.read_csv(
    r"C:\Ruturaj\CTI-Dashboard-master\dataset\CloudWatch_Traffic_Web_Attack.csv"
)

attack_df = pd.read_csv(
    r"C:\Ruturaj\CTI-Dashboard-master\dataset\Attack_Dataset.csv"
)

anomaly_df = pd.read_csv(
    r"C:\Ruturaj\CTI-Dashboard-master\dataset\smart_system_anomaly_dataset.csv"
)

# -------------------------------
# DOCUMENT BUILDERS
# -------------------------------
def log_row_to_doc(row):
    return {
        "text": (
            f"At {row['timestamp']}, a network event occurred where source IP "
            f"{row['source_ip']} communicated with destination IP {row['dest_ip']} "
            f"using protocol {row['protocol']}. The action taken was '{row['action']}'. "
            f"Threat label associated with this event was '{row['threat_label']}'. "
            f"The request path was '{row['request_path']}', transferring "
            f"{row['bytes_transferred']} bytes."
        ),
        "source": "logs",
        "type": "log",
        "label": row["threat_label"],
        "metadata": {
            "protocol": row["protocol"],
            "action": row["action"],
            "log_type": row["log_type"]
        }
    }


def cloudwatch_row_to_doc(row):
    return {
        "text": (
            f"A cloud security alert was generated from source IP {row['src_ip']} "
            f"targeting destination IP {row['dst_ip']} on port {row['dst_port']} "
            f"using protocol {row['protocol']}. The response code observed was "
            f"{row['response.code']}. Detection types included {row['detection_types']}. "
            f"Security rules triggered were {row['rule_names']}."
        ),
        "source": "cloudwatch",
        "type": "alert",
        "label": row["detection_types"],
        "metadata": {
            "src_country": row["src_ip_country_code"],
            "observation": row["observation_name"],
            "bytes_in": row["bytes_in"],
            "bytes_out": row["bytes_out"]
        }
    }


def attack_row_to_doc(row):
    return {
        "text": (
            f"The attack titled '{row['Title']}' falls under the category "
            f"'{row['Category']}' and involves the attack type '{row['Attack Type']}'. "
            f"Scenario description: {row['Scenario Description']}. "
            f"Tools commonly used include {row['Tools Used']}. "
            f"The attack targets {row['Target Type']} exploiting the vulnerability "
            f"{row['Vulnerability']}. This maps to MITRE technique "
            f"{row['MITRE Technique']}. The impact includes {row['Impact']}. "
            f"Detection can be done via {row['Detection Method']}. "
            f"Recommended solution: {row['Solution']}."
        ),
        "source": "attack_dataset",
        "type": "attack_knowledge",
        "label": row["Category"],
        "metadata": {
            "attack_type": row["Attack Type"],
            "mitre": row["MITRE Technique"],
            "tags": row["Tags"]
        }
    }


def anomaly_row_to_doc(row):
    return {
        "text": (
            f"At {row['timestamp']}, device {row['device_id']} of type "
            f"{row['device_type']} showed abnormal behavior. CPU usage was "
            f"{row['cpu_usage']} percent, memory usage {row['memory_usage']} percent, "
            f"network input {row['network_in_kb']} KB and output "
            f"{row['network_out_kb']} KB. Failed authentication attempts were "
            f"{row['failed_auth_attempts']}. The anomaly label was {row['label']}."
        ),
        "source": "anomaly",
        "type": "anomaly",
        "label": row["label"],
        "metadata": {
            "encrypted": row["is_encrypted"],
            "geo_variation": row["geo_location_variation"]
        }
    }

MAX_LOG_DOCS = 50_000
MAX_ANOMALY_DOCS = 50_000


# -------------------------------
# BUILD DOCUMENTS (THIS WAS MISSING)
# -------------------------------
documents = []

for _, row in logs_df.head(MAX_LOG_DOCS).iterrows():
    documents.append(log_row_to_doc(row))

for _, row in cloudwatch_df.iterrows():
    documents.append(cloudwatch_row_to_doc(row))

for _, row in attack_df.iterrows():
    documents.append(attack_row_to_doc(row))

for _, row in anomaly_df.head(MAX_ANOMALY_DOCS).iterrows():
    documents.append(anomaly_row_to_doc(row))

# -------------------------------
# SAVE
# -------------------------------
os.makedirs("rag_store", exist_ok=True)

with open("rag_store/documents.pkl", "wb") as f:
    pickle.dump(documents, f)

print("Saved documents.pkl successfully")
