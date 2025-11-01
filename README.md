# KubeSight

Minimal Kubernetes pod monitoring with a clean web interface.

## Setup

```bash
git clone https://github.com/arivictor/kubesight.git
cd kubesight
uv run python main.py
```

Open `http://localhost:5000`

## Requirements

- Python 3.12+
- Access to Kubernetes cluster (`kubectl` configured)
- `uv` (installs automatically if missing)

## Features

- View and manage pods across namespaces
- Container logs and resource metrics
- Pod restart and delete operations
- Real-time updates via HTMX
- Context switching for multiple clusters

## Optional: Metrics

For CPU/memory usage, install metrics-server:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

For local clusters (minikube, kind):
```bash
kubectl patch -n kube-system deployment metrics-server --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```
