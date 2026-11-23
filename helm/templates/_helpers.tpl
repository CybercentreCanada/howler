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
{{- range .Values.rest.oauth.providers }}
- name: {{ upper .name }}_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .secret.name }}
      key: {{ .secret.key }}
{{- end }}
{{- range .Values.rest.datastore.hosts }}
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
{{- range $key, $val := .Values.rest.env }}
- name: {{ $key }}
  value: {{ $val | quote }}
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
- name: FLASK_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.flaskSecret.name | default "flask-secret-key" }}
      key: {{ .Values.flaskSecret.key | default "key" }}
- name: LIMIT_REQUEST_FIELD_SIZE
  value: "16380"
- name: ELASTIC_DEFAULT_SHARDS
  value: "1"
- name: ELASTIC_HIT_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.hit.shards | default 4 | quote }}{{ else }}"4"{{ end }}
- name: ELASTIC_HIT_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.hit.replicas | default 2 | quote }}{{ else }}"2"{{ end }}
- name: ELASTIC_USER_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.user.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_USER_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.user.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_ACTION_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.action.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_ACTION_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.action.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_DOSSIER_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.dossier.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_DOSSIER_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.dossier.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_OVERVIEW_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.overview.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_OVERVIEW_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.overview.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_VIEW_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.view.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_VIEW_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.view.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_ANALYTIC_SHARDS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.analytic.shards | default 1 | quote }}{{ else }}"1"{{ end }}
- name: ELASTIC_ANALYTIC_REPLICAS
  value: {{ if .Values.rest.elasticsearch }}{{ .Values.rest.elasticsearch.analytic.replicas | default 1 | quote }}{{ else }}"1"{{ end }}
{{- end -}}
