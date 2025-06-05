from typing import Any
from uuid import uuid4


def default_unknown_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Default function to handle unknown evidence types."""
    return {}


class XDRAlertEvidence:
    """Parse graph evidence into howler evidence format."""

    @staticmethod
    def amazon_resource_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Amazon resource evidence to howler evidence format."""
        return {
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
    def analyzed_message_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert analyzed message evidence to howler evidence format."""
        sender = [
            evidence.get("p1Sender", {}).get("emailAddress", "Unknown"),
            evidence.get("p2Sender", {}).get("emailAddress", "Unknown"),
        ]
        if not sender:
            sender = []
        return {
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
    def azure_resource_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Azure resource evidence to howler evidence format."""
        return {
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
    def blob_container_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert blob container evidence to howler evidence format."""
        resource = evidence.get("storageResource", {})
        _hashes = evidence.get("fileHashes", {})
        if not resource:
            resource = {}
        if not _hashes:
            _hashes = {}
        return {
            "Azure": {
                "resource": [
                    {
                        "resource_id": resource.get("resourceId"),
                        "resource_type": resource.get("resourceType"),
                        "resource_name": resource.get("resourceName"),
                    }
                ]
            },
            "file": {
                "created": evidence.get("createdDateTime"),
                "hash": {
                    "sha1": _hashes.get("sha1"),
                    "sha256": _hashes.get("sha256"),
                    "md5": _hashes.get("md5"),
                },
                "name": evidence.get("name"),
            },
        }

    @staticmethod
    def blob_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert blob evidence to howler evidence format."""
        container_evidence = evidence.get("blobContainer", {})
        resource = container_evidence.get("storageResource", {})
        _hashes = evidence.get("fileHashes", {})
        if not container_evidence:
            container_evidence = {}
        if not resource:
            resource = {}
        if not _hashes:
            _hashes = {}
        return {
            "Azure": {
                "resource": [
                    {
                        "resource_id": resource.get("resourceId"),
                        "resource_type": resource.get("resourceType"),
                        "resource_name": resource.get("resourceName"),
                    }
                ]
            },
            "file": {
                "created": evidence.get("createdDateTime"),
                "hash": {
                    "sha1": _hashes.get("sha1"),
                    "sha256": _hashes.get("sha256"),
                    "md5": _hashes.get("md5"),
                },
                "name": evidence.get("name"),
            },
        }

    @staticmethod
    def cloud_application_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert cloud application evidence to howler evidence format."""
        return {
            "cloud": {
                "project": {
                    "id": str(evidence.get("appId")),
                    "name": evidence.get("displayName"),
                }
            },
        }

    @staticmethod
    def cloud_logon_session_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert cloud logon session evidence to howler evidence format."""
        account = evidence.get("account", {})
        user = account.get("userAccount", {})
        if not account:
            account = {}
        if not user:
            user = {}
        return {
            "host": {
                "name": evidence.get("deviceName"),
                "os": {
                    "full": evidence.get("operatingSystem"),
                },
            },
            "network": {
                "protocol": evidence.get("protocol"),
            },
            "user": {
                "name": user.get("accountName"),
                "full_name": user.get("userPrincipalName"),
                "id": user.get("azureAdUserId"),
                "domain": user.get("domainName"),
            },
            "user_agent": {
                "original": evidence.get("userAgent"),
            },
        }

    @staticmethod
    def container_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert container evidence to howler evidence format."""
        image = evidence.get("image", {})
        pod = evidence.get("pod", {})
        containers = pod.get("containers", [])
        if not image:
            image = {}
        if not pod:
            pod = {}
        if not containers:
            containers = []
        return {
            "container": {
                "id": evidence.get("containerId"),
                "image": evidence.get("name"),
            },
            "image": {"name": image.get("digestImage")},
            "kubernetes": {
                "pod": {
                    "containers": [
                        {
                            "name": container.get("name"),
                            "image": container.get("image"),
                            "id": container.get("containerId"),
                            "digest": container.get("digestImage"),
                        }
                        for container in containers
                    ],
                    "controller": pod.get("controller"),
                    "ephemeral_containers": pod.get("ephemeralContainers"),
                    "init_containers": pod.get("initContainers"),
                    "labels": pod.get("labels"),
                    "name": pod.get("name"),
                    "namespace": pod.get("namespace"),
                    "pod_ip": pod.get("podIp"),
                    "service_account": {
                        "name": pod.get("serviceAccountName"),
                        "namespace": pod.get("namespace"),
                    },
                }
            },
        }

    @staticmethod
    def container_image_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert container image evidence to howler evidence format."""
        return {
            "image": {"name": evidence.get("digestImage")},
        }

    @staticmethod
    def container_registry_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert container registry evidence to howler evidence format."""
        return {
            "container": {
                "registry": evidence.get("registry"),
            },
        }

    @staticmethod
    def device_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert device evidence to howler evidence format."""
        hostname = evidence.get("hostName")
        if not hostname:
            hostname = evidence.get("deviceDnsName")
        return {
            "host": {
                "id": evidence.get("mdeDeviceId"),
                "name": hostname,
                "domain": [evidence.get("ntDomain", "unknown")],
                "os": {
                    "platform": evidence.get("osPlatform"),
                    "version": str(evidence.get("osBuild")),
                },
                "logged_on_users": [
                    {
                        "name": user.get("accountName"),
                        "domain": user.get("domainName"),
                    }
                    for user in evidence.get("loggedOnUsers", [])
                ],
                "risk_score": evidence.get("riskScore"),
                "status_av": evidence.get("defenderAvStatus"),
                "status_health": evidence.get("healthStatus"),
                "status_onboarding": evidence.get("onboardingStatus"),
            },
        }

    @staticmethod
    def file_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert file evidence to howler evidence format."""
        file_details = evidence.get("fileDetails", {})
        if not file_details:
            file_details = {}
        return {
            "file": {
                "created": evidence.get("createdDateTime"),
                "hash": {
                    "sha1": file_details.get("sha1"),
                    "sha256": file_details.get("sha256"),
                    "md5": file_details.get("md5"),
                },
                "name": file_details.get("fileName"),
                "path": file_details.get("filePath"),
                "size": file_details.get("fileSize"),
                "code_signature": {
                    "signing_id": file_details.get("signer"),
                    "team_id": file_details.get("issuer"),
                },
            },
        }

    @staticmethod
    def google_cloud_resource_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Google Cloud resource evidence to howler evidence format."""
        return {
            "gcp": {
                "zone": evidence.get("location"),
                "zone_type": evidence.get("locationType"),
                "project_id": evidence.get("projectId"),
                "project_number": evidence.get("projectNumber"),
                "resource_id": evidence.get("resourceName"),
                "resource_type": evidence.get("resourceType"),
            },
        }

    @staticmethod
    def iot_device_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert IoT device evidence to howler evidence format."""
        return {
            "iot": {
                "hub": evidence.get("iotHub"),
                "id": evidence.get("deviceId"),
                "name": evidence.get("deviceName"),
                "owners": evidence.get("owners"),
                "ioTSecurityAgentId": evidence.get("securityAgentId"),
                "deviceType": evidence.get("deviceType"),
                "source": evidence.get("source"),
                "source_ref": evidence.get("sourceRef"),
                "manufacturer": evidence.get("manufacturer"),
                "model": evidence.get("model"),
                "serial": evidence.get("serialNumber"),
                "site": evidence.get("site"),
                "zone": evidence.get("zone"),
                "sensor": evidence.get("sensor"),
                "importance": evidence.get("importance"),
                "purdue_layer": evidence.get("purdueLayer"),
                "is_programming": evidence.get("isProgramming"),
                "is_authorized": evidence.get("isAuthorized"),
                "is_scanner": evidence.get("isScanner"),
                "device_link": evidence.get("devicePageLink"),
                "device_subtype": evidence.get("deviceSubtype"),
            },
            "host": {
                "ip": evidence.get("ipAddress"),
                "mac": evidence.get("macAddress"),
                "os": {
                    "full": evidence.get("operatingSystem"),
                },
            },
        }

    @staticmethod
    def ip_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert IP evidence to howler evidence format."""
        return {
            "host": {
                "ip": [evidence.get("ipAddress")],
                "geo": {
                    "country_iso_code": evidence.get("countryCode"),
                },
            },
        }

    @staticmethod
    def kubernetes_cluster_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes cluster evidence to howler evidence format."""
        return {
            "kubernetes": {
                "namespace": {
                    "cluster": {
                        "cloud_resource": evidence.get("cloudResource"),
                        "distribution": evidence.get("distribution"),
                        "name": evidence.get("name"),
                        "platform": evidence.get("platform"),
                        "version": evidence.get("version"),
                    }
                }
            },
        }

    @staticmethod
    def kubernetes_controller_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes controller evidence to howler evidence format."""
        return {
            "kubernetes": {
                "pod": {
                    "controller": {
                        "labels": evidence.get("labels"),
                        "name": evidence.get("name"),
                        "namespace": evidence.get("namespace"),
                        "controller_type": evidence.get("type"),
                    }
                }
            },
        }

    @staticmethod
    def kubernetes_namespace_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes namespace evidence to howler evidence format."""
        return {
            "kubernetes": {
                "namespace": {
                    "cluster": {
                        "cloud_resource": evidence.get("cloudResource"),
                        "distribution": evidence.get("distribution"),
                        "name": evidence.get("name"),
                        "platform": evidence.get("platform"),
                        "version": evidence.get("version"),
                    }
                },
                "labels": evidence.get("labels"),
                "name": evidence.get("name"),
            },
        }

    @staticmethod
    def kubernetes_pod_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes pod evidence to howler evidence format."""
        return {
            "kubernetes": {
                "controller": {
                    "labels": evidence.get("labels"),
                    "name": evidence.get("name"),
                    "namespace": evidence.get("namespace"),
                    "controller_type": evidence.get("type"),
                    "ephemeral_containers": [
                        {
                            "id": container.get("containerId"),
                            "args": container.get("args"),
                            "command": container.get("command"),
                            "name": container.get("name"),
                        }
                        for container in evidence.get("ephemeralContainers", [])
                    ],
                    "init_containers": [
                        {
                            "id": container.get("containerId"),
                            "args": container.get("args"),
                            "command": container.get("command"),
                            "name": container.get("name"),
                        }
                        for container in evidence.get("ephemeralContainers", [])
                    ],
                    "pod_ip": evidence.get("podIp"),
                    "service_account": {
                        "name": evidence.get("serviceAccountName"),
                        "namespace": evidence.get("namespace"),
                    },
                }
            },
        }

    @staticmethod
    def kubernetes_secret_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes secret evidence to howler evidence format."""
        return {
            "kubernetes": {
                "secret": {
                    "name": evidence.get("name"),
                    "namespace": evidence.get("namespace"),
                    "secret_type": evidence.get("secretType"),
                }
            },
        }

    @staticmethod
    def kubernetes_service_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes service evidence to howler evidence format."""
        return {
            "kubernetes": {
                "service": {
                    "cluster_ip": evidence.get("clusterIp"),
                    "external_ips": [x.get("ipAddress") for x in evidence.get("externalIps", [])],
                    "labels": evidence.get("labels"),
                    "name": evidence.get("name"),
                    "namespace": evidence.get("namespace"),
                    "selector": evidence.get("selector"),
                    "service_ports": [
                        {
                            "app_protocol": port.get("appProtocol"),
                            "name": port.get("name"),
                            "node_port": port.get("nodePort"),
                            "port": port.get("port"),
                            "protocol": port.get("protocol"),
                            "target_port": port.get("targetPort"),
                        }
                        for port in evidence.get("servicePorts", [])
                    ],
                    "service_type": evidence.get("serviceType"),
                }
            },
        }

    @staticmethod
    def kubernetes_service_account_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert Kubernetes service account evidence to howler evidence format."""
        return {
            "kubernetes": {
                "pod": {
                    "service_account": {
                        "name": evidence.get("name"),
                        "namespace": evidence.get("namespace"),
                    }
                }
            },
        }

    @staticmethod
    def mail_cluster_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert mail cluster evidence to howler evidence format."""
        return {
            "metadata": {
                "id": str(uuid4()),
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "mailcluster": {
                "cluster_by": evidence.get("clusterBy"),
                "cluster_by_value": evidence.get("clusterByValue"),
                "email_count": evidence.get("emailCount"),
                "network_message_ids": evidence.get("networkMessageIds"),
                "query": evidence.get("query"),
                "urn": evidence.get("urn"),
            },
        }

    @staticmethod
    def mailbox_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert mailbox evidence to howler evidence format."""
        user = evidence.get("userAccount", {})
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
                "to": evidence.get("primaryAddress"),
            },
            "user": {
                "id": user.get("azureAdUserId"),
                "name": user.get("accountName"),
                "full_name": user.get("userPrincipalName"),
                "domain": user.get("domain"),
            },
        }

    @staticmethod
    def nic_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert NIC evidence to howler evidence format."""
        return {
            "host": {
                "ip": evidence.get("ipAddress"),
                "mac": evidence.get("macAddress"),
            },
        }

    @staticmethod
    def oauth_application_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert OAuth application evidence to howler evidence format."""
        return {
            "metadata": {
                "id": str(uuid4()),
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "oauth": {
                "app_id": evidence.get("appId"),
                "display_name": evidence.get("displayName"),
                "object_id": evidence.get("objectId"),
                "publisher": evidence.get("publisher"),
            },
        }

    @staticmethod
    def process_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert process evidence to howler evidence format."""
        image_file = evidence.get("imageFile", {})
        parent_image_file = evidence.get("parentImageFile", {})
        if not image_file:
            image_file = {}
        if not parent_image_file:
            parent_image_file = {}
        executable = f"{image_file.get('filePath')}\\{image_file.get('fileName')}"
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
                "status_remediation": evidence.get("detectionStatus"),
            },
            "process": {
                "start": evidence.get("processCreationDateTime"),
                "pid": evidence.get("processId"),
                "name": image_file.get("fileName"),
                "hash": {
                    "sha1": image_file.get("sha1"),
                    "sha256": image_file.get("sha256"),
                    "md5": image_file.get("md5"),
                },
                "executable": executable,
                "code_signature": {
                    "team_id": image_file.get("issuer"),
                    "signing_id": image_file.get("signer"),
                },
                "parent": {
                    "start": evidence.get("parentProcessCreationDateTime"),
                    "pid": evidence.get("parentProcessId"),
                    "name": parent_image_file.get("fileName"),
                    "hash": {
                        "sha1": parent_image_file.get("sha1"),
                        "sha256": parent_image_file.get("sha256"),
                        "md5": parent_image_file.get("md5"),
                    },
                    "executable": parent_image_file.get("filePath"),
                    "code_signature": {
                        "team_id": parent_image_file.get("issuer"),
                        "signing_id": parent_image_file.get("signer"),
                    },
                },
            },
        }

    @staticmethod
    def registry_key_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert registry key evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "key": evidence.get("registryKey"),
            "hive": evidence.get("registryHive"),
        }

    @staticmethod
    def registry_value_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert registry value evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "registry": {
                "hive": evidence.get("registryHive"),
                "key": evidence.get("registryKey"),
                "value": evidence.get("registryValue"),
            },
            "host": {
                "id": evidence.get("mdeDeviceId"),
            },
        }

    @staticmethod
    def security_group_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert security group evidence to howler evidence format."""
        return {
            "metadata": {
                "kind": "evidence",
                "provider": "Alert",
                "rawdata": evidence,
            },
            "group": {
                "id": evidence.get("securityGroupId"),
                "name": evidence.get("displayName"),
            },
        }

    @staticmethod
    def teams_message_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
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
                "campaign_id": evidence.get("campaignId"),
                "channel_id": evidence.get("channelId"),
                "delivery_action": evidence.get("deliveryAction"),
                "delivery_location": evidence.get("deliveryLocation"),
                "detailed_roles": evidence.get("detailedRoles"),
                "files": [
                    {
                        "path": file.get("fileDetails", {}).get("filePath"),
                        "name": file.get("fileDetails", {}).get("fileName"),
                        "hash": {
                            "sha1": file.get("fileDetails", {}).get("sha1"),
                            "sha256": file.get("fileDetails", {}).get("sha256"),
                            "md5": file.get("fileDetails", {}).get("md5"),
                        },
                        "code_signature": {
                            "signing_id": file.get("fileDetails", {}).get("signer"),
                            "team_id": file.get("fileDetails", {}).get("issuer"),
                        },
                        "size": file.get("fileDetails", {}).get("fileSize"),
                    }
                    for file in evidence.get("files", [])
                ],
                "group_id": evidence.get("groupId"),
                "is_external": evidence.get("isExternal"),
                "is_owned": evidence.get("isOwned"),
                "last_modified": evidence.get("lastModified"),
                "message_direction": evidence.get("messageDirection"),
                "message_id": evidence.get("messageId"),
                "owning_tenant_id": evidence.get("owningTenantId"),
                "parent_message_id": evidence.get("parentMessageId"),
                "received": evidence.get("received"),
                "recipients": evidence.get("recipients"),
                "sender_from_address": evidence.get("senderFromAddress"),
                "sender_ip": evidence.get("senderIp"),
                "source_add_name": evidence.get("sourceAddName"),
                "source_id": evidence.get("sourceId"),
                "subject": evidence.get("subject"),
                "suspicious_recipients": evidence.get("suspiciousRecipients"),
                "thread_id": evidence.get("threadId"),
                "thread_type": evidence.get("threadType"),
                "urls": [
                    {
                        "full": url.get("url"),
                    }
                    for url in evidence.get("urls", [])
                ],
            },
        }

    @staticmethod
    def url_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert URL evidence to howler evidence format."""
        return {
            "url": {
                "full": evidence.get("url"),
            },
        }

    @staticmethod
    def user_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        """Convert user evidence to howler evidence format."""
        user = evidence.get("userAccount", {})
        if not user:
            user = {}
        return {
            "user": {
                "name": user.get("accountName"),
                "full_name": user.get("userPrincipalName"),
                "id": user.get("azureAdUserId"),
                "domain": user.get("domainName"),
            },
        }


evidence_function_map = {
    "amazonResourceEvidence": XDRAlertEvidence.amazon_resource_evidence,
    "analyzedMessageEvidence": XDRAlertEvidence.analyzed_message_evidence,
    "azureResourceEvidence": XDRAlertEvidence.azure_resource_evidence,
    "blobContainerEvidence": XDRAlertEvidence.blob_container_evidence,
    "blobEvidence": XDRAlertEvidence.blob_evidence,
    "cloudApplicationEvidence": XDRAlertEvidence.cloud_application_evidence,
    "cloudLogonSessionEvidence": XDRAlertEvidence.cloud_logon_session_evidence,
    "containerEvidence": XDRAlertEvidence.container_evidence,
    "containerImageEvidence": XDRAlertEvidence.container_image_evidence,
    "containerRegistryEvidence": XDRAlertEvidence.container_registry_evidence,
    "deviceEvidence": XDRAlertEvidence.device_evidence,
    "fileEvidence": XDRAlertEvidence.file_evidence,
    "googleCloudResourceEvidence": XDRAlertEvidence.google_cloud_resource_evidence,
    "iotDeviceEvidence": XDRAlertEvidence.iot_device_evidence,
    "ipEvidence": XDRAlertEvidence.ip_evidence,
    "kubernetesClusterEvidence": XDRAlertEvidence.kubernetes_cluster_evidence,
    "kubernetesControllerEvidence": XDRAlertEvidence.kubernetes_controller_evidence,
    "kubernetesNamespaceEvidence": XDRAlertEvidence.kubernetes_namespace_evidence,
    "kubernetesPodEvidence": XDRAlertEvidence.kubernetes_pod_evidence,
    "kubernetesSecretEvidence": XDRAlertEvidence.kubernetes_secret_evidence,
    "kubernetesServiceEvidence": XDRAlertEvidence.kubernetes_service_evidence,
    "kubernetesServiceAccountEvidence": XDRAlertEvidence.kubernetes_service_account_evidence,
    "mailClusterEvidence": XDRAlertEvidence.mail_cluster_evidence,
    "mailboxEvidence": XDRAlertEvidence.mailbox_evidence,
    "nicEvidence": XDRAlertEvidence.nic_evidence,
    "oauthApplicationEvidence": XDRAlertEvidence.oauth_application_evidence,
    "processEvidence": XDRAlertEvidence.process_evidence,
    "registryKeyEvidence": XDRAlertEvidence.registry_key_evidence,
    "registryValueEvidence": XDRAlertEvidence.registry_value_evidence,
    "securityGroupEvidence": XDRAlertEvidence.security_group_evidence,
    "teamsMessageEvidence": XDRAlertEvidence.teams_message_evidence,
    "urlEvidence": XDRAlertEvidence.url_evidence,
    "userEvidence": XDRAlertEvidence.user_evidence,
}
