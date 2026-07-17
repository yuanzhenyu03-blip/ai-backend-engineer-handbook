{{/* Common naming and label helpers shared by every template so selectors and
     targets agree by construction. */}}
{{- define "rag-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rag-platform.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "rag-platform.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "rag-platform.labels" -}}
app.kubernetes.io/name: {{ include "rag-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Selector labels: used identically by the Deployment selector, the Pod
     template, and the Service selector so they always match. */}}
{{- define "rag-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api
{{- end -}}

{{- define "rag-platform.postgres.fullname" -}}
{{- printf "%s-postgres" (include "rag-platform.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rag-platform.postgres.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgres
{{- end -}}
