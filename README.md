### Prerequisites
Ensure your system meets the following requirements:
- A Linux distribution (e.g., Ubuntu, CentOS, Fedora, etc.)
- `curl` installed (for downloading DevSpace)
- `kubectl` installed (for Kubernetes management)
- A running Kubernetes cluster (local or remote)

### Download and Install DevSpace

#### Install using `curl`

1. Run the following command to download and install the latest version of DevSpace:

   ```bash
   curl -L -o devspace "https://github.com/loft-sh/devspace/releases/latest/download/devspace-linux-amd64" && sudo install -c -m 0755 devspace /usr/local/bin
   ```

2. Verify the installation by checking the version of DevSpace:

   ```bash
   devspace --version
   ```

   You should see the version number of DevSpace if the installation was successful.

---

### Additional Notes

- If you encounter issues or need more advanced configuration, refer to the [official DevSpace documentation](https://devspace.sh/docs).
- Ensure that your Kubernetes context (`kubectl config use-context`) is properly set up to connect to the desired cluster.

### Environment Variable Configuration

You need to configure the following environment variables (or include them in your `devspace.yaml` file):

- `SPLUNK_ARCADE_OBSERVABILITY_ACCESS_TOKEN`
- `SPLUNK_ARCADE_OBSERVABILITY_REALM`
- `SPLUNK_ARCADE_DOMAIN` **TBD**

For K3s, if you’re using a local registry, configure the following environment variable:

- `SPLUNK_ARCADE_REGISTRY` to `localhost:<port>/splunk-arcade`

---

### Deployment

To deploy the application, run the following command:

```bash
devspace deploy
```

---

### Cleanup and Purge

To clean up or purge the deployment, use the following command:

```bash
devspace purge
```

---

### Manual Cleanup

Uninstalling a Helm chart does not automatically remove Persistent Volume Claims (PVCs) or other resources created by the portal. To manually clean them up, run:

- To clean PVCs:
  ```bash
  make clean-pvcs
  ```

- To clean players:
  ```bash
  make clean-players
  ```

Make sure you're configured to use the `splunk-arcade` namespace before running these commands.

---

### Troubleshooting Local Dev

Below are some common troubleshooting steps:

#### Add splunk-arcade.home to /etc/hosts
Adding an entry mapping splunk-arcade.home to 127.0.0.1 can be helpful to ease static domain resolution issues

#### Verify your load balancer is not in a `<pending>` state
This can happen if you are using something like [minikube](https://minikube.sigs.k8s.io/docs/commands/tunnel/) or [kind](https://kind.sigs.k8s.io/docs/user/loadbalancer) and have not setup tunneling.
See those links for details.

Conflicts with a local `traefik` service in the `kube-system` or similar namespace can als cause issues. 
`kubectl get services --all-namespaces -o wide` can get you a list of all services. look for any of `TYPE` matching `LoadBalancer` and compare `PORT(S)` for any two load balancers trying to make the same ports available. Fix this by editing the deployment of that service or just with kubectl `kubectl edit service -n kube-system traefik `
---

### Future Plans

In the future, we can set up a cron job to automatically prune these resources after a certain period.
