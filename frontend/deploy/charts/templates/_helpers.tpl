{{/*
Expand the name of the chart.
*/}}
{{- define "vlagent-frontend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vlagent-frontend.fullname" -}}
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
{{- define "vlagent-frontend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vlagent-frontend.labels" -}}
helm.sh/chart: {{ include "vlagent-frontend.chart" . }}
{{ include "vlagent-frontend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vlagent-frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vlagent-frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
k8s-app: {{ include "vlagent-frontend.name" . }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vlagent-frontend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vlagent-frontend.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
