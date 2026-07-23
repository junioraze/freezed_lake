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
    host_path      = "/license/minio.license"
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
    "AWS_ENDPOINT_URL_S3=http://minio:9000",
    "POLARIS_PORT=8181",
    "POLARIS_STORAGE_TYPE=S3",
    "POLARIS_BOOTSTRAP_CREDENTIALS=${var.polaris_relm},${var.polaris_user},${var.polaris_pass}"
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
               curlimages/curl -s -o /dev/null -w '%%{http_code}' http://minio:9000/minio/health/ready)" != "200" ]; do
        sleep 2
      done

      echo "Configuring alias and creating bucket '${var.catalog_bucket}'..."
      # executing two commands via sh
      docker run --rm --network ${docker_network.lakehouse_net.name} \
        --entrypoint sh \
        minio/mc -c "
          mc alias set myminio http://minio:9000 '${var.minio_user}' '${var.minio_pass}' && \
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
        http://polaris:8181/api/catalog/v1/oauth/tokens \
        -H 'Polaris-Realm: ${var.polaris_relm}' \
        -d 'grant_type=client_credentials' \
        -d 'client_id=${var.polaris_user}' \
        -d 'client_secret=${var.polaris_pass}' \
        -d 'scope=PRINCIPAL_ROLE:ALL')

      POLARIS_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

      echo "Creating catalog '${var.catalog_bucket}' on Polaris..."
      docker run --rm --network ${docker_network.lakehouse_net.name} \
        curlimages/curl -s -X POST \
        http://polaris:8181/api/management/v1/catalogs \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $POLARIS_TOKEN" \
        -d '{
          "name": "'${var.catalog_bucket}'",
          "type": "INTERNAL",
          "storageType": "S3",
          "properties": {
            "default-base-location": "s3://'${var.catalog_bucket}'"
          },
          "storageConfigInfo": {
            "storageType": "S3",
            "endpoint": "http://minio:9000",
            "region": "us-east-1",
            "allowedLocations": [
              "s3://'${var.catalog_bucket}'"
            ],
            "credentials": {
              "accessKeyId": "'${var.minio_user}'",
              "secretAccessKey": "'${var.minio_pass}'"
            }
          }
        }'
    EOT
  }
}