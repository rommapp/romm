

<!-- markdownlint-disable MD033 -->

<h1 align="center">
    <a href="https://github.com/zurdi15/romm">
        <img src="https://raw.githubusercontent.com/zurdi15/romm/release/.github/resources/romm.svg" alt="Logo" style="max-height: 150px">
    </a>
</h1>

<h4 align="center">RomM - RomM (Rom Manager) is a web based retro roms manager integrated with IGDB.</h4>

<div align="center">
  <br/>

  [
    ![License](https://img.shields.io/github/license/zurdi15/romm?logo=git&logoColor=white&logoWidth=20)
  ](LICENSE)
  <br/>
  ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square)
  ![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-informational?style=flat-square)
  ![AppVersion: 2.1.0](https://img.shields.io/badge/AppVersion-2.1.0-informational?style=flat-square)

</div>

---

## [RomM](https://github.com/zurdi15/romm)

> _Disclaimer: This application has been developed by the [RomM](https://github.com/zurdi15/romm) community._

RomM (**ROM M**anager) is a game library manager focused on retro gaming. It enables you to efficiently manage and organize all your games from a web browser.

Inspired by [Jellyfin](https://jellyfin.org/), RomM allows you to handle all your games through a modern interface while enhancing them with IGDB metadata.

## ⚡ Features

- Scan your game library (all at once or by platform) and enrich it with IGDB metadata.
- Access your library via your web browser.
- Easily choose from matching IGDB results if the scan doesn't find the right one.
- Compatible with EmuDeck folder structures.
- Supports games with multiple files.
- Download games directly from your web browser.
- Edit your game files directly from your web browser.
- Upload games directly from your web-browser
- Set a custom cover for each game
- Includes region, revision/version, and extra tags support.
- Works with SQLite or MariaDB.
- Features a responsive design with dark mode support.

[> More about RomM](https://github.com/zurdi15/romm)

---

## TL;DR

```shell
helm repo add zurdi15 https://zurdi15.github.io/romm
helm install my-release zurdi15/RomM
```

## Introduction

This chart bootstraps a RomM deployment on a [Kubernetes](kubernetes.io) cluster using the [Helm](helm.sh) package manager.

## Prerequisites

- Kubernetes >=1.22.0-0
- Helm 3+
- PV provisioner support in the underlying infrastructure

## Installing the Chart

To install the chart with the release name `my-release`:

```shell
helm repo add zurdi15 https://zurdi15.github.io/romm
helm install my-release zurdi15/RomM
```

These commands deploy RomM on the Kubernetes cluster in the default configuration.
The Parameters section lists the parameters that can be configured during installation.

> **Tip:** List all releases using `helm list`

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```shell
helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Parameters

### Global parameters

| Key | Description | Default |
|-----|-------------|---------|
| `global.commonLabels` |  Labels to apply to all resources. | `{}` |
| `global.imagePullSecrets` |  Reference to one or more secrets to be used when pulling images    ([kubernetes.io/docs](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)) | `[]` |

### Common parameters

| Key | Description | Default |
|-----|-------------|---------|
| `fullnameOverride` | String to fully override `common.names.fullname` template | `""` |
| `nameOverride` | String to partially override `common.names.fullname` template (will maintain the release name) | `""` |

### RomM parameters

| Key | Description | Default |
|-----|-------------|---------|
| `image.pullPolicy` | pull policy, if you set tag to latest, this should be set to Always to not end up with stale builds | `"IfNotPresent"` |
| `image.repository` | referencing the docker image to use for the deployment | `"zurdi15/romm"` |
| `image.tag` | Overrides the image tag whose default is the chart appVersion. | `""` |

### Security parameters

| Key | Description | Default |
|-----|-------------|---------|
| `podSecurityContext.fsGroup` | set filesystem group access to the same as runAsGroup | `1000` |
| `podSecurityContext.fsGroupChangePolicy` | change fs mount permissions if they are not matching desired fsGroup | `"OnRootMismatch"` |
| `podSecurityContext.runAsGroup` | run the deployment as a group with this GID, should match fsGroup above | `1000` |
| `podSecurityContext.runAsNonRoot` | ensure the container dosnt run with not-needed root permissions | `true` |
| `podSecurityContext.runAsUser` | run the deployment as a user with this UID | `1000` |
| `podSecurityContext.seccompProfile.type` |  | `"RuntimeDefault"` |

### Deployment/Statefulset parameters

| Key | Description | Default |
|-----|-------------|---------|
| `affinity` |  | `{}` |
| `nodeSelector` |  | `{}` |
| `podAnnotations` | If needed, set some annotations to the deployed pods | `{}` |
| `resources` |  | `{}` |
| `tolerations` |  | `[]` |

### Network parameters

| Key | Description | Default |
|-----|-------------|---------|
| `ingress.annotations."nginx.ingress.kubernetes.io/proxy-body-size"` |  | `"256m"` |
| `ingress.className` |  | `""` |
| `ingress.enabled` |  | `false` |
| `ingress.hosts[0].host` |  | `"chart-example.local"` |
| `ingress.hosts[0].paths[0].path` |  | `"/"` |
| `ingress.hosts[0].paths[0].pathType` |  | `"ImplementationSpecific"` |
| `ingress.tls` |  | `[]` |
| `service.type` |  | `"ClusterIP"` |
| `serviceAccount.annotations` | Annotations to add to the service account | `{}` |
| `serviceAccount.create` | Specifies whether a service account should be created | `true` |
| `serviceAccount.name` | The name of the service account to use.    If not set and create is true, a name is generated using the fullname template | `""` |

### Persistence parameters

| Key | Description | Default |
|-----|-------------|---------|
| `persistence.database.enabled` | Enable roms database persistence using `PVC`. only needed when database backend is sqlite | `true` |
| `persistence.database.volumeClaimSpec` | Claims that pods are allowed to reference (see    [kubernetes.io/docs](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.26/#persistentvolumeclaim-v1-core)    for structural reference) | `{"accessModes":["ReadWriteOnce"],"resources":{"requests":{"storage":"2Gi"}}}` |
| `persistence.logs.enabled` | Enable logs persistence using `PVC`. If false, use emptyDir | `false` |
| `persistence.logs.volumeClaimSpec` | Claims that pods are allowed to reference (see    [kubernetes.io/docs](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.26/#persistentvolumeclaim-v1-core)    for structural reference) | `{"accessModes":["ReadWriteOnce"],"resources":{"requests":{"storage":"256Mi"}}}` |
| `persistence.resources.enabled` | Enable roms metadata (covers) persistence using `PVC`. If false, use emptyDir | `true` |
| `persistence.resources.volumeClaimSpec` | Claims that pods are allowed to reference (see    [kubernetes.io/docs](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.26/#persistentvolumeclaim-v1-core)    for structural reference) | `{"accessModes":["ReadWriteOnce"],"resources":{"requests":{"storage":"2Gi"}}}` |

### RBAC parameters

| Key | Description | Default |
|-----|-------------|---------|
### Other parameters

| Key | Description | Default |
|-----|-------------|---------|
| `mariadb` | Enable and configure mariadb database subchart under this key.    If enabled, the app's db envs will be set for you.    [[ref]]([github.com/bitnami](https://github.com/bitnami/charts/tree/main/bitnami/mariadb)) TODO: currently bitnami has a bug where redis and mariadb can not be       enabled at the same time ([github.com/bitnami](https://github.com/bitnami/charts/issues/20504)) | See [values.yaml](./values.yaml) |
| `mariadb.enabled` | provision an instance of the mariadb sub-chart | `false` |
| `redis` | Enable and configure redis subchart under this key.    If enabled, the app's redis envs will be set for you.    [[ref]]([github.com/bitnami](https://github.com/bitnami/charts/tree/main/bitnami/redis)) | See [values.yaml](./values.yaml) |
| `redis.enabled` | provision an instance of the redis sub-chart | `true` |
| `romm.config.auth.enabled` | enable romm's integrated authentication mechanics (this requires redis to be available) | `false` |
| `romm.config.auth.password` | default password for the admin user | `"admin"` |
| `romm.config.auth.username` | default username for the admin user | `"admin"` |
| `romm.config.database.mariadb` | only needed when you are using an external shared mariadb    that is already existing and not the romm integrated one | `{"host":"localhost","pass":"password","port":3306,"schema":"romm","user":"romm-user"}` |
| `romm.config.database.type` | type can either be mariadb or sqlite | `"sqlite"` |
| `romm.config.filesystem_watcher.enabled` | enable inotify filesystem watcher mechanics to automatically add new roms and pick up changes as they happen | `true` |
| `romm.config.filesystem_watcher.scan_delay` |  | `5` |
| `romm.config.igdb_api.client_id` |  | `"CHANGEME_IGDB_CLIENT_ID"` |
| `romm.config.igdb_api.client_secret` |  | `"CHANGEME_IGDB_CLIENT_SECRET"` |
| `romm.config.scheduled_tasks.filesystem_scan.cron` | Cron expression for the scheduled scan (default: 0 3 * * * - At 3:00 AM every day) | `"0 3 * * *"` |
| `romm.config.scheduled_tasks.filesystem_scan.enabled` |  | `true` |
| `romm.config.scheduled_tasks.mame_xml_update.cron` | Cron expression to update mame xml database (default: 0 5 * * * - At 5:00 AM every day) | `"0 5 * * *"` |
| `romm.config.scheduled_tasks.mame_xml_update.enabled` |  | `true` |
| `romm.config.scheduled_tasks.switch_titledb_update.cron` | Cron expression to update switch titledb (default: 0 4 * * * - At 4:00 AM every day) | `"0 4 * * *"` |
| `romm.config.scheduled_tasks.switch_titledb_update.enabled` |  | `true` |
| `romm.config.steamgriddb_api.api_key` |  | `"CHANGEME_STEAMGRIDDB_API_KEY"` |
| `romm.mediaVolumes` | The list of volumes that will be mounted inside romm pod, to `/romm/library`. | `[]` |
| `romm.settings.exclude.platforms` | Exclude platforms to be scanned | `["romm"]` |
| `romm.settings.exclude.roms` | Exclude roms or parts of roms to be scanned | `{"multi_file":{"names":["my_multi_file_game","DLC"],"parts":{"extensions":["txt"],"names":["data.xml"]}},"single_file":{"extensions":["xml"],"names":["info.txt"]}}` |
| `romm.settings.exclude.roms.multi_file` | Multi files games section | `{"names":["my_multi_file_game","DLC"],"parts":{"extensions":["txt"],"names":["data.xml"]}}` |
| `romm.settings.exclude.roms.multi_file.names` | Exclude matched 'folder' (RomM identifies folders as multi file games) names to be scanned | `["my_multi_file_game","DLC"]` |
| `romm.settings.exclude.roms.multi_file.parts.extensions` | Exclude all files with certain extensions to be scanned from multi file roms | `["txt"]` |
| `romm.settings.exclude.roms.multi_file.parts.names` | Exclude matched file names to be scanned from multi file roms    Keep in mind that RomM doesn't scan folders inside multi files games,    so there is no need to exclude folders from inside of multi files games. | `["data.xml"]` |
| `romm.settings.exclude.roms.single_file` | Single file games section | `{"extensions":["xml"],"names":["info.txt"]}` |
| `romm.settings.exclude.roms.single_file.extensions` | Exclude all files with certain extensions to be scanned | `["xml"]` |
| `romm.settings.exclude.roms.single_file.names` | Exclude matched file names to be scanned | `["info.txt"]` |
| `romm.settings.system.platforms.gc` | [your custom platform folder name]: [RomM platform name] | `"ngc"` |
| `romm.settings.system.platforms.psx` |  | `"ps"` |
| `securityContext.allowPrivilegeEscalation` |  | `false` |
| `securityContext.capabilities` | drop unneccessary permissions | `{"drop":["ALL"]}` |
| `securityContext.readOnlyRootFilesystem` | mount / as readonly, writeable directorys are explicitely mounted | `true` |

Specify each parameter using the `--set key=value[,key=value]` argument to `helm install`. For example,

```shell
helm install my-release --set fullnameOverride=my-RomM zurdi15/RomM
```

Alternatively, a YAML file that specifies the values for the parameters can be provided while installing the chart. For example,

```shell
helm install my-release -f values.yaml zurdi15/RomM
```

> **Tip:** You can use the default values.yaml

## License

Licensed under the GNU General Public License v3.0 (the "License"); you may not use this file except in compliance with
the License. You may obtain a copy of the License at

```
https://github.com/zurdi15/romm/blob/release/LICENSE
```

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.

----------------------------------------------
Autogenerated from chart metadata using [helm-docs v1.11.3](https://github.com/norwoodj/helm-docs/releases/v1.11.3)
