{{/*
Create a name for the application.
*/}}
{{- define "flask-postgres.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
