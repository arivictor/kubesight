# ⎈ KubeSight

**Full-featured Kubernetes monitoring service** that allows inspection and management of pods in a cluster.

Built with:
- 🚀 **uv** - Fast Python package installer and resolver
- ☸️ **kubernetes-client/python** - Official Python client for Kubernetes
- 🌶️ **Flask** - Lightweight Python web framework
- ⚡ **HTMX** - Modern HTML-over-the-wire framework for dynamic UIs

## Features

- **Pod Management**: View, inspect, and manage pods across all namespaces
- **Resource Metrics**: Display real-time CPU and memory usage for containers (requires metrics-server)
- **Real-time Updates**: Dynamic UI updates using HTMX without full page reloads
- **Pod Details**: Comprehensive pod information including status, containers, labels, and conditions
- **Container Logs**: View logs from any container in a pod
- **Pod Operations**: Delete and restart pods directly from the UI
- **Search & Filter**: Search pods by name or namespace, filter by namespace
- **Responsive Design**: Clean, modern UI that works on desktop and mobile
- **Namespace Support**: View pods across all namespaces or filter by specific namespace

## Installation

### Prerequisites

- Python 3.12 or higher
- Access to a Kubernetes cluster (with `kubectl` configured)
- `uv` package manager (will be installed if not present)
- **Optional**: metrics-server deployed in your cluster for CPU/memory metrics

### Setup

1. Clone the repository:
```bash
git clone https://github.com/arivictor/kubesight.git
cd kubesight
```

2. Install dependencies using uv:
```bash
pip install uv  # If uv is not already installed
uv sync
```

3. Ensure you have access to a Kubernetes cluster:
```bash
kubectl cluster-info
```

4. **Optional**: Install metrics-server for CPU/memory metrics:
```bash
# For most clusters
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For local clusters (minikube, kind, etc.) - add insecure flags
kubectl patch -n kube-system deployment metrics-server --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

## Usage

### Running the Application

#### Using uv:
```bash
uv run python main.py
```

#### Or activate the virtual environment:
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python main.py
```

The application will start on `http://localhost:5000`

### Kubernetes Configuration

KubeSight will automatically try to connect to your Kubernetes cluster using:
1. In-cluster configuration (if running inside a Kubernetes pod)
2. Local kubeconfig file (typically `~/.kube/config`)

### Running in Development Mode

The application runs in debug mode by default, which provides:
- Auto-reload on code changes
- Detailed error messages
- Debug logs

For production deployment, modify `kubesight/app.py` to disable debug mode.

## Project Structure

```
kubesight/
├── kubesight/
│   ├── __init__.py          # Package initialization
│   ├── app.py               # Flask application and routes
│   ├── templates/           # HTML templates
│   │   ├── base.html        # Base template
│   │   ├── index.html       # Main dashboard
│   │   └── pods_table.html  # Pod list component
│   └── static/              # Static assets
│       ├── css/
│       │   └── style.css    # Application styles
│       └── js/
│           └── app.js       # JavaScript utilities
├── main.py                  # Application entry point
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/namespaces` - List all namespaces
- `GET /api/pods?namespace=<ns>&search=<term>` - List pods (with filters)
- `GET /api/pods/<namespace>/<pod>` - Get pod details (includes metrics)
- `GET /api/pods/<namespace>/<pod>/metrics` - Get pod CPU/memory metrics (JSON)
- `GET /api/pods/<namespace>/<pod>/logs?container=<name>` - Get pod logs
- `DELETE /api/pods/<namespace>/<pod>` - Delete a pod
- `POST /api/pods/<namespace>/<pod>/restart` - Restart a pod

## Technologies Used

### Backend
- **Flask**: Lightweight web framework for Python
- **kubernetes-client/python**: Official Kubernetes Python client library
- **uv**: Modern Python package management

### Frontend
- **HTMX**: Enables dynamic HTML updates without JavaScript frameworks
- **CSS3**: Modern styling with CSS Grid and Flexbox
- **Vanilla JavaScript**: Minimal JavaScript for enhanced functionality

## Metrics Support

KubeSight displays real-time CPU and memory usage for containers when metrics-server is available in your cluster.

### Setting up metrics-server

**For production clusters:**
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

**For local development clusters (minikube, kind, k3d):**
```bash
# Install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Add insecure TLS flag for local clusters
kubectl patch -n kube-system deployment metrics-server --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

### Verifying metrics-server

Check if metrics-server is working:
```bash
# Check if metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# Test metrics API
kubectl top pods
kubectl top nodes
```

### Troubleshooting

If metrics are not showing up:

1. **Check metrics-server logs:**
   ```bash
   kubectl logs -n kube-system deployment/metrics-server
   ```

2. **Verify metrics API:**
   ```bash
   kubectl get --raw "/apis/metrics.k8s.io/v1beta1/pods"
   ```

3. **Common issues:**
   - **Local clusters**: Add `--kubelet-insecure-tls` flag
   - **Self-signed certificates**: Add `--kubelet-insecure-tls` flag
   - **Network policies**: Ensure metrics-server can reach kubelets (port 10250)

## Security Considerations

- KubeSight requires access to your Kubernetes cluster API
- Use RBAC to limit what KubeSight can access
- Consider running in read-only mode for production monitoring
- Use network policies to restrict access to the web interface

## Development

### Adding New Features

1. Backend: Add routes to `kubesight/app.py`
2. Frontend: Add templates to `kubesight/templates/`
3. Styling: Update `kubesight/static/css/style.css`

### Testing

To test the application locally:
```bash
# Start a local Kubernetes cluster (e.g., minikube)
minikube start

# Run the application
uv run python main.py

# Access at http://localhost:5000
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See [LICENSE](LICENSE) file for details.

## Acknowledgments

- Kubernetes community for the excellent Python client
- Flask team for the amazing web framework
- HTMX for making modern web development simpler
- Astral for creating the fast uv package manager
