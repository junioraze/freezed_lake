# Freezed Lakehouse Terraform Setup (Development)

Este projeto está em desenvolvimento.

## O que foi feito

- Provisionamento de containers Docker via Terraform:
  - **MinIO** (S3-compatible object storage) com credenciais configuráveis.
  - **Polaris** (Apache Polaris catalog) com autenticação OAuth2 e realm customizado.
- Criação automática de:
  - Bucket no MinIO (`catalog_bucket`).
  - Catálogo no Polaris via API REST, utilizando token de acesso obtido via OAuth2.
- Rede Docker dedicada (`lakehouse_net`) e volumes persistentes para dados.

## Variáveis

| Variável          | Descrição                     |
|-------------------|-------------------------------|
| `minio_user`      | Usuário root do MinIO         |
| `minio_pass`      | Senha root do MinIO           |
| `polaris_user`    | Usuário admin do Polaris      |
| `polaris_pass`    | Senha admin do Polaris        |
| `polaris_relm`    | Realm (tenant) do Polaris     |
| `catalog_bucket`  | Nome do bucket e do catálogo  |

## Como executar

```bash
terraform init
terraform apply -var-file=terraform.tfvars