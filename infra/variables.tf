variable "minio_user" {
  description = "Admin do minio"
  type        = string
}

variable "minio_pass" {
  description = "Senha do Admin do minio"
  type        = string
}

variable "minio_external_endpoint" {
  description = "Endpoint externo 'localhost' para testes"
  type        = string
  default     = "http://localhost:9000"
}

variable "polaris_user" {
  description = "Admin do Polaris"
  type        = string
}

variable "polaris_pass" {
  description = "Senha do Admin do Polaris"
  type        = string
}

variable "polaris_relm" {
  description = "Relm padrao"
  type        = string
}

variable "catalog_bucket" {
  description = "Nome do bucket e do catalog"
  type        = string
}

variable "polaris_external_endpoint" {
  description = "Endpoint externo 'localhost' para testes"
  type        = string
  default     = "http://polaris:8181"
}

variable "dagu_dags_path" {
  description = "Path to dagu dags"
  type        = string
  default     = "../dags"
}

variable "dagu_port" {
  description = "Port of orquestration without ':'"
  type        = number
  default     = 8081
}