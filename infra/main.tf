#DAGU Env variables Global (ainda precisando estudar melhores padroes de job params e envs)

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
    #BIND-LOCAL to keep lake data
    volume_name    = "${abspath(path.module)}/data/minio"
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
      docker_container.minio, 
      docker_container.polaris,
      local_file.dagu_global_env
    ]
}
