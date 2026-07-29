#DAGU Env variables Global

resource "local_file" "dagu_global_env" {
  filename = "${abspath(path.module)}/${var.dagu_dags_path}/.env.global"
  content  = <<-EOT
    # Endpoints internos (pois os workers rodarão dentro da lakehouse_net)
    POLARIS_ENDPOINT=${var.polaris_external_endpoint}
    POLARIS_REALM=${var.polaris_relm}
    POLARIS_USER=${var.polaris_user}
    POLARIS_PASS=${var.polaris_pass}
    MINIO_ENDPOINT=${var.minio_external_endpoint}
    MINIO_USER=${var.minio_user}
    MINIO_PASS=${var.minio_pass}
    CATALOG_BUCKET=${var.catalog_bucket}
  EOT
}

# Network

resource "docker_network" "lakehouse_net" {
  name = "lakehouse_net"
}

# Volumes

resource "docker_volume" "minio_data" {
  name = "minio_data"
}

resource "docker_volume" "polaris_data" {
  name = "polaris_data"
}

resource "docker_volume" "dagu_data" {
  name = "dagu_data"
}

# MinIO Container
resource "docker_container" "minio" {
  name  = "minio"
  image = "minio/minio:latest"

  networks_advanced {
    name = docker_network.lakehouse_net.name
  }

  volumes {
    volume_name    = docker_volume.minio_data.name
    container_path = "/data"
  }

  # new minio license free tier is needed aistore
  volumes {
    host_path      = "/licenses/minio.license"
    container_path = "/minio.license"
  }

  env = [
    "MINIO_ROOT_USER=${var.minio_user}",
    "MINIO_ROOT_PASSWORD=${var.minio_pass}"
  ]
  command = ["server", "/data", "--console-address", ":9001"]
  #internal api
  ports {
    internal = 9000
    external = 9000
  }

  ports {
    internal = 9001
    external = 9001
  }

}

# Polaris Container
resource "docker_container" "polaris" {
  name  = "polaris"
  image = "apache/polaris:latest"

  networks_advanced {
    name = docker_network.lakehouse_net.name
  }

  volumes {
    volume_name    = docker_volume.polaris_data.name
    container_path = "/data"
  }

  env = [
    "AWS_ACCESS_KEY_ID=${var.minio_user}",
    "AWS_SECRET_ACCESS_KEY=${var.minio_pass}",
    "AWS_REGION=us-east-1",
    "AWS_ENDPOINT_URL_S3=${var.minio_external_endpoint}",
    "POLARIS_PORT=8181",
    "POLARIS_STORAGE_TYPE=S3",
    "POLARIS_BOOTSTRAP_CREDENTIALS=${var.polaris_relm},${var.polaris_user},${var.polaris_pass}",
    "POLARIS_FEATURES__SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION=false"
  ]

  ports {
    internal = 8181
    external = 8181
  }
  #internal api
  ports {
    internal = 8182
    external = 8182
  }


  depends_on = [docker_container.minio]

}

# DAGU Container
resource "docker_container" "dagu" {
  name = "dagu"
  image = "ghcr.io/dagucloud/dagu:latest"
  user = "0:0"
  networks_advanced {
    name = docker_network.lakehouse_net.name
  }

  volumes {
    volume_name = docker_volume.dagu_data.name
    container_path = "/var/lib/dagu"
  }

  # External access to host docker
  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  } 

  # DAGS directory
  volumes {
    host_path      = "${abspath(path.module)}/${var.dagu_dags_path}"
    container_path = "/dags"
  }

  ports {
    internal = var.dagu_port
    external = var.dagu_port
  }

  env = [ 
    "DAGU_DAGS_DIR=/dags",
    "DAGU_PORT=${var.dagu_port}",
    "DAGU_AUTH_MODE=none"
   ]

  entrypoint = ["/usr/bin/tini", "--", "dagu", "start-all"]
  # null_resource have health_check probes to polaris and minio
  # dagu depends of this to work + envs
  depends_on = [
      null_resource.create_minio_bucket, 
      null_resource.create_polaris_catalog, 
      local_file.dagu_global_env
    ]
}



resource "null_resource" "create_minio_bucket" {
  depends_on = [docker_container.minio]

  triggers = {
    minio_id = docker_container.minio.id
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command = <<EOT
      echo "W8 MinIO health check..."
      # check probe
      while [ "$(docker run --rm --network ${docker_network.lakehouse_net.name} \
               curlimages/curl -s -o /dev/null -w '%%{http_code}' ${var.minio_external_endpoint}/minio/health/ready)" != "200" ]; do
        sleep 2
      done

      echo "Configuring alias and creating bucket '${var.catalog_bucket}'..."
      # executing two commands via sh
      docker run --rm --network ${docker_network.lakehouse_net.name} \
        --entrypoint sh \
        minio/mc -c "
          mc alias set myminio ${var.minio_external_endpoint} '${var.minio_user}' '${var.minio_pass}' && \
          mc mb myminio/${var.catalog_bucket}
        "
    EOT
  }
}

resource "null_resource" "create_polaris_catalog" {
  depends_on = [docker_container.minio, null_resource.create_minio_bucket]

  triggers = {
    polaris_id = docker_container.polaris.id
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command = <<EOT
      echo "W8 Polaris health check..."
      while ! docker run --rm --network ${docker_network.lakehouse_net.name} curlimages/curl -s -f http://polaris:8182/q/health; do
        sleep 2
      done

      echo "Obtaining Polaris access token..."
      RESPONSE=$(docker run --rm --network ${docker_network.lakehouse_net.name} curlimages/curl -s \
        ${var.polaris_external_endpoint}/api/catalog/v1/oauth/tokens \
        -H 'Polaris-Realm: ${var.polaris_relm}' \
        -d 'grant_type=client_credentials' \
        -d 'client_id=${var.polaris_user}' \
        -d 'client_secret=${var.polaris_pass}' \
        -d 'scope=PRINCIPAL_ROLE:ALL')

      POLARIS_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

      echo "Creating catalog '${var.catalog_bucket}' on Polaris..."
      docker run --rm --network ${docker_network.lakehouse_net.name} \
        curlimages/curl -s -X POST \
        ${var.polaris_external_endpoint}/api/management/v1/catalogs \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $POLARIS_TOKEN" \
        -d '{
            "name": "${var.catalog_bucket}",
            "type": "INTERNAL",
            "storageType": "S3",
            "properties": {
              "default-base-location": "s3://${var.catalog_bucket}",
              "table-default.s3.endpoint": "${var.minio_external_endpoint}",
              "table-default.s3.endpoint-internal": "${var.minio_external_endpoint}",
              "table-default.s3.path-style-access": "true",
              "table-default.s3.region": "us-east-1"
            },
            "storageConfigInfo": {
              "storageType": "S3",
              "allowedLocations": ["s3://${var.catalog_bucket}"],
              "endpoint": "${var.minio_external_endpoint}",
              "endpointInternal": "${var.minio_external_endpoint}",
              "pathStyleAccess": true,
              "region": "us-east-1",
              "stsUnavailable": true,
              "roleArn": "arn:aws:iam::000000000000:role/dummy"
            }
        }'
      echo "Granting CATALOG_MANAGE_CONTENT to catalog_admin... (Minio issue with STS)"
      docker run --rm --network ${docker_network.lakehouse_net.name} \
        curlimages/curl -s -X PUT \
        ${var.polaris_external_endpoint}/api/management/v1/catalogs/${var.catalog_bucket}/catalog-roles/catalog_admin/grants \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $POLARIS_TOKEN" \
        -d '{"type":"catalog", "privilege":"CATALOG_MANAGE_CONTENT"}'
    EOT
  }
}