{: set filetype=mustache: */}}

{{/*
Expand the name of the chart.
*/}}
{{- define "howler.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "howler.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "howler.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "howler.labels" -}}
app.kubernetes.io/name: {{ include "howler.name" . }}
helm.sh/chart: {{ include "howler.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
printConfigs
takes a section of values and prints it in dot notation instead of the hierarchy
*/}}
{{- define "printConfigs" }}
  {{- if kindIs "map" .map }}
    {{- range $key, $map := .map }}
      {{- include "printConfigs" (dict "key" (append $.key $key ) "map" $map) }}
    {{- end -}}
  {{- else -}}
    {{printf "%s=%s\n" (join "." .key) (toString .map) }}
  {{- end -}}
{{- end }}


{{/*
sharedEnv

*/}}

{{- define "sharedEnv" -}}
{{- range .Values.howlerRest.oauth.providers }}
- name: {{ upper .name }}_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .secret.name }}
      key: {{ .secret.key }}
{{- end }}
{{- range .Values.howlerRest.datastore.hosts }}
- name: {{ upper .name }}_HOST_APIKEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .secret.name }}
      key: {{ .secret.idKey }}
- name: {{ upper .name }}_HOST_APIKEY_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .secret.name }}
      key: {{ .secret.secretKey }}
{{- end }}
{{- if (and .Values.apm.enabled .Values.apm.tokenSecret) }}
- name: ELASTIC_APM_SECRET_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.apm.tokenSecret }}
      key: {{ .Values.apm.tokenKey | default "token" }}
{{- end }}
- name: ELASTIC_APM_DEBUG
  value: {{ .Values.apm.workWithDebug | quote }}
- name: ELASTIC_APM_LOG_LEVEL
  value: {{ .Values.apm.loggingLevel }}
- name: HWL_INTERPOD_COMMS_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .Values.websocket.commSecret.name | default "howler-interpod-comms-secret" }}
      key: {{ .Values.websocket.commSecret.key | default "secret" }}
{{- end -}}
