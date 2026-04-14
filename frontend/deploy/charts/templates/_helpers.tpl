{{/*
Expand the name of the chart.
*/}}
{{- define "vlagent-front.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vlagent-front.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "vlagent-front.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vlagent-front.labels" -}}
helm.sh/chart: {{ include "vlagent-front.chart" . }}
{{ include "vlagent-front.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vlagent-front.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vlagent-front.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
k8s-app: {{ include "vlagent-front.name" . }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vlagent-front.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vlagent-front.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
