import os

from kubernetes import client, config

APP_NAME = "splunk-arcade"
NAMESPACE = os.getenv("NAMESPACE") or "splunk-arcade"
IMAGE_PLAYER_CABINET = os.getenv("PLAYER_CABINET_IMAGE") or "splunk-arcade/cabinet:latest"
IMAGE_PLAYER_CLOUD = os.getenv("PLAYER_CLOUD_IMAGE") or "splunk-arcade/player-cloud:latest"
IMAGE_PULL_POLICY = os.getenv("IMAGE_PULL_POLICY") or "IfNotPresent"
ARCADE_HOST = os.getenv("ARCADE_HOST") or "www.splunkarcade.com"
PLAYER_CONTENT_HOST = os.getenv("PLAYER_CONTENT_HOST") or f"{APP_NAME}-player-content"
POSTGRES_ARCHITECTURE = os.getenv("POSTGRES_ARCHITECTURE") or "standalone"
POSTGRES_URL = (
    f"postgresql://postgres:password@{APP_NAME}-postgresql/myapp"
    if POSTGRES_ARCHITECTURE == "standalone"
    else f"postgresql://postgres:password@{APP_NAME}-postgresql-read/myapp"
)


class _Config:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        self.config = config.load_incluster_config()


def player_deployment_create(player_id: str, observability_realm: str) -> None:
    if player_id == "devplayer":
        # this is our player for testing/dev, and we prohibit use of this username, so this will
        # only be needed when doing devspace things in which case the deployment/service will
        # already exist
        return

    # ensure config is loaded
    _ = _Config()

    dep = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f"{APP_NAME}-player-{player_id}",
            labels={
                "app.kubernetes.io/name": f"{APP_NAME}-cabinet",
                "app.kubernetes.io/instance": f"{APP_NAME}-cabinet-{player_id}",
            },
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            strategy=client.V1DeploymentStrategy(
                rolling_update=client.V1RollingUpdateDeployment(
                    max_surge=1,
                    max_unavailable=0,
                ),
                type="RollingUpdate",
            ),
            selector=client.V1LabelSelector(
                match_labels={
                    "app.kubernetes.io/name": f"{APP_NAME}-cabinet",
                    "app.kubernetes.io/instance": f"{APP_NAME}-cabinet-{player_id}",
                }
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app.kubernetes.io/name": f"{APP_NAME}-cabinet",
                        "app.kubernetes.io/instance": f"{APP_NAME}-cabinet-{player_id}",
                    },
                ),
                spec=client.V1PodSpec(
                    volumes=[
                        client.V1Volume(
                            name="config-volume",
                            config_map=client.V1ConfigMapVolumeSource(name="my-config"),
                        )
                    ],
                    containers=[
                        client.V1Container(
                            name="player",
                            image=IMAGE_PLAYER_CABINET,
                            image_pull_policy=IMAGE_PULL_POLICY,
                            resources=client.V1ResourceRequirements(
                                requests={
                                    "cpu": "32m",
                                    "memory": "128Mi",
                                },
                                limits={
                                    "cpu": "128m",
                                    "memory": "192Mi",
                                },
                            ),
                            env=[
                                client.V1EnvVar(
                                    name="NODE_IP",
                                    value_from=client.V1EnvVarSource(
                                        field_ref=client.V1ObjectFieldSelector(
                                            field_path="status.hostIP"
                                        )
                                    ),
                                ),
                                client.V1EnvVar(
                                    name="OTEL_EXPORTER_OTLP_ENDPOINT",
                                    value="http://$(NODE_IP):4317",
                                ),
                                client.V1EnvVar(
                                    name="OTEL_EXPORTER_HEALTH_ENDPOINT",
                                    value="http://$(NODE_IP):13133",
                                ),
                                client.V1EnvVar(
                                    name="PLAYER_NAME",
                                    value=player_id,
                                ),
                                client.V1EnvVar(
                                    name="SECRET_KEY",
                                    value="SECRET_KEY",
                                ),
                                client.V1EnvVar(
                                    name="DATABASE_URL",
                                    value=POSTGRES_URL,
                                ),
                                client.V1EnvVar(
                                    name="REDIS_HOST",
                                    value=f"{APP_NAME}-redis-master",
                                ),
                                client.V1EnvVar(
                                    name="SCOREBOARD_HOST", value=f"{APP_NAME}-scoreboard"
                                ),
                                client.V1EnvVar(
                                    name="OTEL_SERVICE_NAME",
                                    value=f"{APP_NAME}-cabinet-player-{player_id}",
                                ),
                                client.V1EnvVar(
                                    name="OTEL_RESOURCE_ATTRIBUTES",
                                    value=f"service.name=$(OTEL_SERVICE_NAME),service.namespace={APP_NAME},deployment.environment=gameify",
                                ),
                                client.V1EnvVar(
                                    name="ARCADE_HOST",
                                    value=ARCADE_HOST,
                                ),
                                client.V1EnvVar(
                                    name="PLAYER_CONTENT_HOST",
                                    value=PLAYER_CONTENT_HOST,
                                ),
                                client.V1EnvVar(
                                    name="SPLUNK_OBSERVABILITY_REALM",
                                    value=observability_realm,
                                ),
                            ],
                            ports=[
                                client.V1ContainerPort(
                                    name="http",
                                    container_port=5_000,
                                ),
                            ],
                            readiness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(
                                    path=f"/player/{player_id}/alive", port="http", scheme="HTTP"
                                ),
                                success_threshold=1,
                                failure_threshold=2,
                                period_seconds=30,
                                timeout_seconds=5,
                            ),
                        )
                    ],
                    service_account_name="default",
                ),
            ),
        ),
    )

    apps_v1 = client.AppsV1Api()
    apps_v1.create_namespaced_deployment(namespace=NAMESPACE, body=dep)

    svc = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=f"{APP_NAME}-cabinet-player-{player_id}",
            labels={
                "app.kubernetes.io/name": f"{APP_NAME}-cabinet",
                "app.kubernetes.io/instance": f"{APP_NAME}-cabinet-{player_id}",
            },
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            session_affinity=None,
            selector={
                "app.kubernetes.io/name": f"{APP_NAME}-cabinet",
                "app.kubernetes.io/instance": f"{APP_NAME}-cabinet-{player_id}",
            },
            ports=[
                client.V1ServicePort(
                    name="http",
                    port=80,
                    target_port=5000,
                    protocol="TCP",
                ),
            ],
        ),
    )

    core_v1 = client.CoreV1Api()
    core_v1.create_namespaced_service(namespace=NAMESPACE, body=svc)


def player_deployment_ready(player_id: str) -> bool:
    if player_id == "devplayer":
        # this is our player for testing/dev, and we prohibit use of this username, so this will
        # only be needed when doing devspace things in which case the deployment/service will
        # already exist
        return True

    # ensure config is loaded
    _ = _Config()

    apps_v1 = client.AppsV1Api()
    resp = apps_v1.list_namespaced_deployment(
        namespace=NAMESPACE,
        label_selector=f"app.kubernetes.io/instance={APP_NAME}-cabinet-{player_id}",
    )

    if not resp.items:
        return False

    ready_replicas = resp.items[0].status.ready_replicas
    if not ready_replicas:
        return False

    return ready_replicas > 0
