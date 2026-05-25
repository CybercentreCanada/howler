??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Cloud

> Fields related to the cloud or infrastructure the events are coming from.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| account | [Account](/howler/odm/class/account) | Cloud account information. | :material-minus-box-outline: Optional :material-alert-box-outline: Deprecated - Instead of using this more general field, use a platform-specific field. For more information, see [Disambiguated Cloud Ontology](https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology) | `None` |
| availability_zone | Keyword | Availability zone in which this host, resource, or service is located. | :material-minus-box-outline: Optional :material-alert-box-outline: Deprecated - Instead of using this more general field, use a platform-specific field. For more information, see [Disambiguated Cloud Ontology](https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology) | `None` |
| instance | [Instance](/howler/odm/class/instance) | Instance information. | :material-minus-box-outline: Optional | `None` |
| machine | [Machine](/howler/odm/class/machine) | Machine information. | :material-minus-box-outline: Optional | `None` |
| project | [Project](/howler/odm/class/project) | Project information. | :material-minus-box-outline: Optional :material-alert-box-outline: Deprecated - Instead of using this more general field, use a platform-specific field. For more information, see [Disambiguated Cloud Ontology](https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology) | `None` |
| provider | Keyword | Name of the cloud provider. Example values are aws, azure, gcp, or digitalocean. | :material-minus-box-outline: Optional | `None` |
| region | Keyword | Region in which this host, resource, or service is located. | :material-minus-box-outline: Optional | `None` |
| service | [Service](/howler/odm/class/service) | Service information. | :material-minus-box-outline: Optional | `None` |
| tenant_id | Keyword | The tenant id associated with this alert. | :material-minus-box-outline: Optional :material-alert-box-outline: Deprecated - Instead of using this more general field, use a platform-specific field. For more information, see [Disambiguated Cloud Ontology](https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology) | `None` |
