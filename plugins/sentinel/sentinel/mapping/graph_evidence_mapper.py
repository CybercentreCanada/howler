"""Convert Microsoft Graph evidence to howler evidence format."""

from typing import Any
from uuid import uuid4


def default_unknown_evidence(evidence: dict[str, Any]) -> dict:
    """Default function to handle unknown evidence types."""
    return {
        "metadata": {
            "kind": "evidence",
            "provider": "Alert",
            "rawdata": evidence,
        },
    }


class GraphEvidenceParser:
    """Parse graph evidence into howler evidence format."""

    @staticmethod
    def amazon_resource_evidence(evidence: dict[str, Any]):
        """Convert Amazon resource evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "aws": {
                "account": {
                    "id": evidence.get("amazonAccountId"),
                },
                "resource": {
                    "id": evidence.get("amazonResourceId"),
                    "type": evidence.get("resourceType"),
                    "name": evidence.get("resourceName"),
                },
            },
        }

    @staticmethod
    def analyzed_message_evidence(evidence: dict[str, Any]):
        """Convert analyzed message evidence to howler evidence format."""
        sender = [
            evidence.get("p1Sender", {}).get("emailAddress", "Unknown"),
            evidence.get("p2Sender", {}).get("emailAddress", "Unknown"),
        ]
        if not sender:
            sender = []
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "email": {
                "direction": evidence.get("antiSpamDirection"),
                "local_id": evidence.get("networkMessageId"),
                "to": evidence.get("recipientEmailAddress"),
                "sender": ", ".join(sender),
                "subject": evidence.get("subject"),
            },
            "host": {"ip": [evidence.get("senderIp")]},
            "url": {
                "full": ", ".join(evidence.get("urls", [])),
            },
        }

    @staticmethod
    def azure_resource_evidence(evidence: dict[str, Any]):
        """Convert Azure resource evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "azure": {
                "resource": [
                    {
                        "resource_id": evidence.get("resourceId"),
                        "resource_type": evidence.get("resourceType"),
                        "resource_name": evidence.get("resourceName"),
                    }
                ]
            },
        }

    @staticmethod
    def blob_container_evidence(evidence: dict[str, Any]):
        """Convert blob container evidence to howler evidence format."""
        resource = evidence.get("StorageResource", {})
        _hashes = evidence.get("FileHashes", {})
        if not resource:
            resource = {}
        if not _hashes:
            _hashes = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "Azure": {
                "resource": [
                    {
                        "resource_id": resource.get("ResourceId"),
                        "resource_type": resource.get("ResourceType"),
                        "resource_name": resource.get("ResourceName"),
                    }
                ]
            },
            "file": {
                "created": evidence.get("CreatedDateTime"),
                "hash": {
                    "sha1": _hashes.get("Sha1"),
                    "sha256": _hashes.get("Sha256"),
                    "md5": _hashes.get("Md5"),
                },
                "name": evidence.get("Name"),
            },
        }

    @staticmethod
    def blob_evidence(evidence: dict[str, Any]):
        """Convert blob evidence to howler evidence format."""
        container_evidence = evidence.get("BlobContainer", {})
        resource = container_evidence.get("StorageResource", {})
        _hashes = evidence.get("FileHashes", {})
        if not container_evidence:
            container_evidence = {}
        if not resource:
            resource = {}
        if not _hashes:
            _hashes = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "Azure": {
                "resource": [
                    {
                        "resource_id": resource.get("ResourceId"),
                        "resource_type": resource.get("ResourceType"),
                        "resource_name": resource.get("ResourceName"),
                    }
                ]
            },
            "file": {
                "created": evidence.get("CreatedDateTime"),
                "hash": {
                    "sha1": _hashes.get("Sha1"),
                    "sha256": _hashes.get("Sha256"),
                    "md5": _hashes.get("Md5"),
                },
                "name": evidence.get("Name"),
            },
        }

    @staticmethod
    def cloud_application_evidence(evidence: dict[str, Any]):
        """Convert cloud application evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "cloud": {
                "project": {
                    "id": str(evidence.get("AppId")),
                    "name": evidence.get("DisplayName"),
                }
            },
        }

    @staticmethod
    def cloud_logon_request_evidence(evidence: dict[str, Any]):
        """Convert cloud logon request evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            }
        }

    @staticmethod
    def cloud_logon_session_evidence(evidence: dict[str, Any]):
        """Convert cloud logon session evidence to howler evidence format."""
        account = evidence.get("Account", {})
        user = account.get("UserAccount", {})
        if not account:
            account = {}
        if not user:
            user = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "host": {
                "name": evidence.get("DeviceName"),
                "os": {
                    "full": evidence.get("OperatingSystem"),
                },
            },
            "network": {
                "protocol": evidence.get("Protocol"),
            },
            "user": {
                "name": user.get("AccountName"),
                "full_name": user.get("UserPrincipalName"),
                "id": user.get("AzureAdUserId"),
                "domain": user.get("DomainName"),
            },
            "user_agent": {
                "original": evidence.get("UserAgent"),
            },
        }

    @staticmethod
    def container_evidence(evidence: dict[str, Any]):
        """Convert container evidence to howler evidence format."""
        image = evidence.get("Image", {})
        pod = evidence.get("Pod", {})
        containers = pod.get("Containers", [])
        if not image:
            image = {}
        if not pod:
            pod = {}
        if not containers:
            containers = []
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "container": {
                "id": evidence.get("ContainerId"),
                "image": evidence.get("Name"),
            },
            "image": {"name": image.get("DigestImage")},
            "kubernetes": {
                "pod": {
                    "containers": [
                        {
                            "name": container.get("Name"),
                            "image": container.get("Image"),
                            "id": container.get("ContainerId"),
                            "digest": container.get("DigestImage"),
                        }
                        for container in containers
                    ],
                    "controller": pod.get("Controller"),
                    "ephemeral_containers": pod.get("EphemeralContainers"),
                    "init_containers": pod.get("InitContainers"),
                    "labels": pod.get("Labels"),
                    "name": pod.get("Name"),
                    "namespace": pod.get("Namespace"),
                    "pod_ip": pod.get("PodIp"),
                    "service_account": {
                        "name": pod.get("ServiceAccountName"),
                        "namespace": pod.get("Namespace"),
                    },
                }
            },
        }

    @staticmethod
    def container_image_evidence(evidence: dict[str, Any]):
        """Convert container image evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "image": {"name": evidence.get("DigestImage")},
        }

    @staticmethod
    def container_registry_evidence(evidence: dict[str, Any]):
        """Convert container registry evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "container": {
                "registry": evidence.get("Registry"),
            },
        }

    @staticmethod
    def device_evidence(evidence: dict[str, Any]):
        """Convert device evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "host": {
                "id": evidence.get("MdeDeviceId"),
                "name": evidence.get("HostName"),
                "domain": [evidence.get("NtDomain","unknown")],
                "os": {
                    "platform": evidence.get("OsPlatform"),
                    "version": str(evidence.get("OsBuild")),
                },
                "logged_on_users": [
                    {
                        "name": user.get("AccountName"),
                        "domain": user.get("DomainName"),
                    }
                    for user in evidence.get("LoggedOnUsers", [])
                ],
                "risk_score": evidence.get("RiskScore"),
                "status_av": evidence.get("DefenderAvStatus"),
                "status_health": evidence.get("HealthStatus"),
                "status_onboarding": evidence.get("OnboardingStatus"),
            },
        }

    @staticmethod
    def file_evidence(evidence: dict[str, Any]):
        """Convert file evidence to howler evidence format."""
        file_details = evidence.get("FileDetails", {})
        if not file_details:
            file_details = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "status_remediation": evidence.get("DetectionStatus"),
            },
            "file": {
                "created": evidence.get("CreatedDateTime"),
                "hash": {
                    "sha1": file_details.get("Sha1"),
                    "sha256": file_details.get("Sha256"),
                    "md5": file_details.get("Md5"),
                },
                "name": file_details.get("FileName"),
                "path": file_details.get("FilePath"),
                "size": file_details.get("FileSize"),
                "code_signature": {
                    "signing_id": file_details.get("Signer"),
                    "team_id": file_details.get("Issuer"),
                },
            },
        }

    @staticmethod
    def google_cloud_resource_evidence(evidence: dict[str, Any]):
        """Convert Google Cloud resource evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "gcp": {
                "zone": evidence.get("Location"),
                "zone_type": evidence.get("LocationType"),
                "project_id": evidence.get("ProjectId"),
                "project_number": evidence.get("ProjectNumber"),
                "resource_id": evidence.get("ResourceName"),
                "resource_type": evidence.get("ResourceType"),
            },
        }

    @staticmethod
    def iot_device_evidence(evidence: dict[str, Any]):
        """Convert IoT device evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "iot": {
                "hub": evidence.get("IotHub"),
                "id": evidence.get("DeviceId"),
                "name": evidence.get("DeviceName"),
                "owners": evidence.get("Owners"),
                "ioTSecurityAgentId": evidence.get("SecurityAgentId"),
                "deviceType": evidence.get("DeviceType"),
                "source": evidence.get("Source"),
                "source_ref": evidence.get("SourceRef"),
                "manufacturer": evidence.get("Manufacturer"),
                "model": evidence.get("Model"),
                "serial": evidence.get("SerialNumber"),
                "site": evidence.get("Site"),
                "zone": evidence.get("Zone"),
                "sensor": evidence.get("Sensor"),
                "importance": evidence.get("Importance"),
                "purdue_layer": evidence.get("PurdueLayer"),
                "is_programming": evidence.get("IsProgramming"),
                "is_authorized": evidence.get("IsAuthorized"),
                "is_scanner": evidence.get("IsScanner"),
                "device_link": evidence.get("DevicePageLink"),
                "device_subtype": evidence.get("DeviceSubtype"),
            },
            "host": {
                "ip": evidence.get("IpAddress"),
                "mac": evidence.get("MacAddress"),
                "os": {
                    "full": evidence.get("OperatingSystem"),
                },
            },
        }

    @staticmethod
    def ip_evidence(evidence: dict[str, Any]):
        """Convert IP evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "host": {
                "ip": [evidence.get("IpAddress")],
                "geo": {
                    "country_iso_code": evidence.get("CountryCode"),
                },
            },
        }

    @staticmethod
    def kubernetes_cluster_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes cluster evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "namespace": {
                    "cluster": {
                        "cloud_resource": evidence.get("CloudResource"),
                        "distribution": evidence.get("Distribution"),
                        "name": evidence.get("Name"),
                        "platform": evidence.get("Platform"),
                        "version": evidence.get("Version"),
                    }
                }
            },
        }

    @staticmethod
    def kubernetes_controller_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes controller evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "pod": {
                    "controller": {
                        "labels": evidence.get("Labels"),
                        "name": evidence.get("Name"),
                        "namespace": evidence.get("Namespace"),
                        "controller_type": evidence.get("Type"),
                    }
                }
            },
        }

    @staticmethod
    def kubernetes_namespace_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes namespace evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "namespace": {
                    "cluster": {
                        "cloud_resource": evidence.get("CloudResource"),
                        "distribution": evidence.get("Distribution"),
                        "name": evidence.get("Name"),
                        "platform": evidence.get("Platform"),
                        "version": evidence.get("Version"),
                    }
                },
                "labels": evidence.get("Labels"),
                "name": evidence.get("Name"),
            },
        }

    @staticmethod
    def kubernetes_pod_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes pod evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "controller": {
                    "labels": evidence.get("Labels"),
                    "name": evidence.get("Name"),
                    "namespace": evidence.get("Namespace"),
                    "controller_type": evidence.get("Type"),
                    "ephemeral_containers": [
                        {
                            "id": container.get("ContainerId"),
                            "args": container.get("Args"),
                            "command": container.get("Command"),
                            "name": container.get("Name"),
                        }
                        for container in evidence.get("EphemeralContainers", [])
                    ],
                    "init_containers": [
                        {
                            "id": container.get("ContainerId"),
                            "args": container.get("Args"),
                            "command": container.get("Command"),
                            "name": container.get("Name"),
                        }
                        for container in evidence.get("EphemeralContainers", [])
                    ],
                    "pod_ip": evidence.get("PodIp"),
                    "service_account": {
                        "name": evidence.get("ServiceAccountName"),
                        "namespace": evidence.get("Namespace"),
                    },
                }
            },
        }

    @staticmethod
    def kubernetes_secret_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes secret evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "secret": {
                    "name": evidence.get("Name"),
                    "namespace": evidence.get("Namespace"),
                    "secret_type": evidence.get("SecretType"),
                }
            },
        }

    @staticmethod
    def kubernetes_service_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes service evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "service": {
                    "cluster_ip": evidence.get("ClusterIp"),
                    "external_ips": [
                        x.get("IpAddress") for x in evidence.get("ExternalIps", [])
                    ],
                    "labels": evidence.get("Labels"),
                    "name": evidence.get("Name"),
                    "namespace": evidence.get("Namespace"),
                    "selector": evidence.get("Selector"),
                    "service_ports": [
                        {
                            "app_protocol": port.get("AppProtocol"),
                            "name": port.get("Name"),
                            "node_port": port.get("NodePort"),
                            "port": port.get("Port"),
                            "protocol": port.get("Protocol"),
                            "target_port": port.get("TargetPort"),
                        }
                        for port in evidence.get("ServicePorts", [])
                    ],
                    "service_type": evidence.get("ServiceType"),
                }
            },
        }

    @staticmethod
    def kubernetes_service_account_evidence(evidence: dict[str, Any]):
        """Convert Kubernetes service account evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "kubernetes": {
                "pod": {
                    "service_account": {
                        "name": evidence.get("Name"),
                        "namespace": evidence.get("Namespace"),
                    }
                }
            },
        }

    @staticmethod
    def mail_cluster_evidence(evidence: dict[str, Any]):
        """Convert mail cluster evidence to howler evidence format."""
        return {
            "metadata": {
                "id": str(uuid4()),
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "mailcluster": {
                "cluster_by": evidence.get("ClusterBy"),
                "cluster_by_value": evidence.get("ClusterByValue"),
                "email_count": evidence.get("EmailCount"),
                "network_message_ids": evidence.get("NetworkMessageIds"),
                "query": evidence.get("Query"),
                "urn": evidence.get("Urn"),
            },
        }

    @staticmethod
    def mailbox_evidence(evidence: dict[str, Any]):
        """Convert mailbox evidence to howler evidence format."""
        user = evidence.get("UserAccount", {})
        if not user:
            user = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "email": {
                "id": str(uuid4()),
                "to": evidence.get("PrimaryAddress"),
            },
            "user": {
                "id": user.get("AzureAdUserId"),
                "name": user.get("AccountName"),
                "full_name": user.get("UserPrincipalName"),
                "domain": user.get("Domain"),
            },
        }

    @staticmethod
    def nic_evidence(evidence: dict[str, Any]):
        """Convert NIC evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "host": {
                "ip": evidence.get("IpAddress"),
                "mac": evidence.get("MacAddress"),
            },
        }

    @staticmethod
    def oauth_application_evidence(evidence: dict[str, Any]):
        """Convert OAuth application evidence to howler evidence format."""
        return {
            "metadata": {
                "id": str(uuid4()),
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "oauth": {
                "app_id": evidence.get("AppId"),
                "display_name": evidence.get("DisplayName"),
                "object_id": evidence.get("ObjectId"),
                "publisher": evidence.get("Publisher"),
            },
        }

    @staticmethod
    def process_evidence(evidence: dict[str, Any]):
        """Convert process evidence to howler evidence format."""
        image_file = evidence.get("ImageFile", {})
        parent_image_file = evidence.get("ParentImageFile", {})
        if not image_file:
            image_file = {}
        if not parent_image_file:
            parent_image_file = {}
        executable = f"{image_file.get('FilePath')}\\{image_file.get('FileName')}"
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "status_remediation": evidence.get("DetectionStatus"),
            },
            "process": {
                "start": evidence.get("ProcessCreationDateTime"),
                "pid": evidence.get("ProcessId"),
                "name": image_file.get("FileName"), # error on this line: AttributeError: 'NoneType' object has no attribute 'get'
                "hash": {
                    "sha1": image_file.get("Sha1"),
                    "sha256": image_file.get("Sha256"),
                    "md5": image_file.get("Md5"),
                },
                "executable": executable,
                "code_signature": {
                    "team_id": image_file.get("Issuer"),
                    "signing_id": image_file.get("Signer"),
                },
                "parent": {
                    "start": evidence.get("ParentProcessCreationDateTime"),
                    "pid": evidence.get("ParentProcessId"),
                    "name": parent_image_file.get("FileName"),
                    "hash": {
                        "sha1": parent_image_file.get("Sha1"),
                        "sha256": parent_image_file.get("Sha256"),
                        "md5": parent_image_file.get("Md5"),
                    },
                    "executable": parent_image_file.get("FilePath"),
                    "code_signature": {
                        "team_id": parent_image_file.get("Issuer"),
                        "signing_id": parent_image_file.get("Signer"),
                    },
                },
            },
        }

    @staticmethod
    def registry_key_evidence(evidence: dict[str, Any]):
        """Convert registry key evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "key": evidence.get("RegistryKey"),
            "hive": evidence.get("RegistryHive"),
        }

    @staticmethod
    def registry_value_evidence(evidence: dict[str, Any]):
        """Convert registry value evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "registry": {
                "hive": evidence.get("RegistryHive"),
                "key": evidence.get("RegistryKey"),
                "value": evidence.get("RegistryValue"),
            },
            "host": {
                "id": evidence.get("MdeDeviceId"),
            },
        }

    @staticmethod
    def security_group_evidence(evidence: dict[str, Any]):
        """Convert security group evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "group": {
                "id": evidence.get("SecurityGroupId"),
                "name": evidence.get("DisplayName"),
            },
        }

    @staticmethod
    def teams_message_evidence(evidence: dict[str, Any]):
        """Convert Teams message evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "roles": evidence.get("roles"),
                "tags": evidence.get("tags"),
                "verdict": evidence.get("verdict"),
                "status_remediation": evidence.get("remediationStatus"),
                "status_remediation_details": evidence.get("remediationStatusDetails"),
            },
            "teams": {
                "campaign_id": evidence.get("CampaignId"),
                "channel_id": evidence.get("ChannelId"),
                "delivery_action": evidence.get("DeliveryAction"),
                "delivery_location": evidence.get("DeliveryLocation"),
                "detailed_roles": evidence.get("DetailedRoles"),
                "files": [
                    {
                        "path": file.get("FileDetails", {}).get("FilePath"),
                        "name": file.get("FileDetails", {}).get("FileName"),
                        "hash": {
                            "sha1": file.get("FileDetails", {}).get("Sha1"),
                            "sha256": file.get("FileDetails", {}).get("Sha256"),
                            "md5": file.get("FileDetails", {}).get("Md5"),
                        },
                        "code_signature": {
                            "signing_id": file.get("FileDetails", {}).get("Signer"),
                            "team_id": file.get("FileDetails", {}).get("Issuer"),
                        },
                        "size": file.get("FileDetails", {}).get("FileSize"),
                    }
                    for file in evidence.get("Files", [])
                ],
                "group_id": evidence.get("GroupId"),
                "is_external": evidence.get("IsExternal"),
                "is_owned": evidence.get("IsOwned"),
                "last_modified": evidence.get("LastModified"),
                "message_direction": evidence.get("MessageDirection"),
                "message_id": evidence.get("MessageId"),
                "owning_tenant_id": evidence.get("OwningTenantId"),
                "parent_message_id": evidence.get("ParentMessageId"),
                "received": evidence.get("Received"),
                "recipients": evidence.get("Recipients"),
                "sender_from_address": evidence.get("SenderFromAddress"),
                "sender_ip": evidence.get("SenderIp"),
                "source_add_name": evidence.get("SourceAddName"),
                "source_id": evidence.get("SourceId"),
                "subject": evidence.get("Subject"),
                "suspicious_recipients": evidence.get("SuspiciousRecipients"),
                "thread_id": evidence.get("ThreadId"),
                "thread_type": evidence.get("ThreadType"),
                "urls": [
                    {
                        "full": url.get("Url"),
                    }
                    for url in evidence.get("Urls", [])
                ],
            },
        }

    @staticmethod
    def url_evidence(evidence: dict[str, Any]):
        """Convert URL evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "url": {
                "full": evidence.get("Url"),
            },
        }

    @staticmethod
    def user_evidence(evidence: dict[str, Any]):
        """Convert user evidence to howler evidence format."""
        user = evidence.get("UserAccount", {})
        if not user:
            user = {}
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "user": {
                "name": user.get("AccountName"),
                "full_name": user.get("UserPrincipalName"),
                "id": user.get("AzureAdUserId"),
                "domain": user.get("DomainName"),
            },
        }


evidence_function_map = {
    "amazonResourceEvidence": GraphEvidenceParser.amazon_resource_evidence,
    "analyzedMessageEvidence": GraphEvidenceParser.analyzed_message_evidence,
    "azureResourceEvidence": GraphEvidenceParser.azure_resource_evidence,
    "blobContainerEvidence": GraphEvidenceParser.blob_container_evidence,
    "blobEvidence": GraphEvidenceParser.blob_evidence,
    "cloudApplicationEvidence": GraphEvidenceParser.cloud_application_evidence,
    "cloudLogonRequestEvidence": GraphEvidenceParser.cloud_logon_request_evidence,
    "cloudLogonSessionEvidence": GraphEvidenceParser.cloud_logon_session_evidence,
    "containerEvidence": GraphEvidenceParser.container_evidence,
    "containerImageEvidence": GraphEvidenceParser.container_image_evidence,
    "containerRegistryEvidence": GraphEvidenceParser.container_registry_evidence,
    "deviceEvidence": GraphEvidenceParser.device_evidence,
    "fileEvidence": GraphEvidenceParser.file_evidence,
    "googleCloudResourceEvidence": GraphEvidenceParser.google_cloud_resource_evidence,
    "iotDeviceEvidence": GraphEvidenceParser.iot_device_evidence,
    "ipEvidence": GraphEvidenceParser.ip_evidence,
    "kubernetesClusterEvidence": GraphEvidenceParser.kubernetes_cluster_evidence,
    "kubernetesControllerEvidence": GraphEvidenceParser.kubernetes_controller_evidence,
    "kubernetesNamespaceEvidence": GraphEvidenceParser.kubernetes_namespace_evidence,
    "kubernetesPodEvidence": GraphEvidenceParser.kubernetes_pod_evidence,
    "kubernetesSecretEvidence": GraphEvidenceParser.kubernetes_secret_evidence,
    "kubernetesServiceEvidence": GraphEvidenceParser.kubernetes_service_evidence,
    "kubernetesServiceAccountEvidence": GraphEvidenceParser.kubernetes_service_account_evidence,
    "mailClusterEvidence": GraphEvidenceParser.mail_cluster_evidence,
    "mailboxEvidence": GraphEvidenceParser.mailbox_evidence,
    "nicEvidence": GraphEvidenceParser.nic_evidence,
    "oauthApplicationEvidence": GraphEvidenceParser.oauth_application_evidence,
    "processEvidence": GraphEvidenceParser.process_evidence,
    "registryKeyEvidence": GraphEvidenceParser.registry_key_evidence,
    "registryValueEvidence": GraphEvidenceParser.registry_value_evidence,
    "securityGroupEvidence": GraphEvidenceParser.security_group_evidence,
    "teamsMessageEvidence": GraphEvidenceParser.teams_message_evidence,
    "urlEvidence": GraphEvidenceParser.url_evidence,
    "userEvidence": GraphEvidenceParser.user_evidence,
}
