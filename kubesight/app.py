"""Flask application for KubeSight."""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Initialize Kubernetes client
    try:
        # Try to load in-cluster config first (for running inside K8s)
        config.load_incluster_config()
    except config.ConfigException:
        # Fall back to local kubeconfig (for development)
        try:
            config.load_kube_config()
        except config.ConfigException:
            app.logger.warning("No Kubernetes configuration found. Using mock data.")
    
    return app


app = create_app()


def get_k8s_client():
    """Get Kubernetes API client."""
    return client.CoreV1Api()


def format_age(created_time):
    """Format the age of a resource."""
    if not created_time:
        return "Unknown"
    
    now = datetime.utcnow()
    # Make created_time timezone-naive for comparison
    if created_time.tzinfo is not None:
        created_time = created_time.replace(tzinfo=None)
    
    delta = now - created_time
    
    if delta.days > 0:
        return f"{delta.days}d"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m"
    else:
        return f"{delta.seconds}s"


def get_pod_status(pod):
    """Get simplified pod status."""
    if pod.status.phase == "Running":
        # Check if all containers are ready
        if pod.status.container_statuses:
            all_ready = all(cs.ready for cs in pod.status.container_statuses)
            if all_ready:
                return "Running"
            else:
                return "Starting"
    return pod.status.phase


@app.route('/')
def index():
    """Home page with pod list."""
    return render_template('index.html')


@app.route('/api/namespaces')
def get_namespaces():
    """Get list of namespaces."""
    try:
        v1 = get_k8s_client()
        namespaces = v1.list_namespace()
        
        ns_list = [{
            'name': ns.metadata.name,
            'status': ns.status.phase,
            'age': format_age(ns.metadata.creation_timestamp)
        } for ns in namespaces.items]
        
        return jsonify({'namespaces': ns_list})
    except Exception as e:
        app.logger.error(f"Error fetching namespaces: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/pods')
def get_pods():
    """Get list of pods, optionally filtered by namespace."""
    namespace = request.args.get('namespace', 'default')
    search = request.args.get('search', '').lower()
    
    try:
        v1 = get_k8s_client()
        
        if namespace == 'all':
            pods = v1.list_pod_for_all_namespaces()
        else:
            pods = v1.list_namespaced_pod(namespace)
        
        pod_list = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            pod_ns = pod.metadata.namespace
            
            # Apply search filter
            if search and search not in pod_name.lower() and search not in pod_ns.lower():
                continue
            
            # Count ready containers
            ready_containers = 0
            total_containers = 0
            if pod.status.container_statuses:
                total_containers = len(pod.status.container_statuses)
                ready_containers = sum(1 for cs in pod.status.container_statuses if cs.ready)
            
            # Get restart count
            restart_count = 0
            if pod.status.container_statuses:
                restart_count = sum(cs.restart_count for cs in pod.status.container_statuses)
            
            pod_list.append({
                'name': pod_name,
                'namespace': pod_ns,
                'status': get_pod_status(pod),
                'ready': f"{ready_containers}/{total_containers}",
                'restarts': restart_count,
                'age': format_age(pod.metadata.creation_timestamp),
                'node': pod.spec.node_name or 'N/A'
            })
        
        # Return HTML for HTMX
        return render_template('pods_table.html', pods=pod_list)
    except Exception as e:
        app.logger.error(f"Error fetching pods: {e}")
        return f'<div class="error">Error: {str(e)}</div>', 500


@app.route('/api/pods/<namespace>/<pod_name>')
def get_pod_details(namespace, pod_name):
    """Get detailed information about a specific pod."""
    try:
        v1 = get_k8s_client()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        
        # Extract container info
        containers = []
        if pod.spec.containers:
            for container in pod.spec.containers:
                container_status = None
                if pod.status.container_statuses:
                    container_status = next(
                        (cs for cs in pod.status.container_statuses if cs.name == container.name),
                        None
                    )
                
                containers.append({
                    'name': container.name,
                    'image': container.image,
                    'ready': container_status.ready if container_status else False,
                    'restart_count': container_status.restart_count if container_status else 0,
                    'state': str(container_status.state) if container_status else 'Unknown'
                })
        
        # Extract labels
        labels = pod.metadata.labels or {}
        
        # Extract conditions
        conditions = []
        if pod.status.conditions:
            for condition in pod.status.conditions:
                conditions.append({
                    'type': condition.type,
                    'status': condition.status,
                    'reason': condition.reason or 'N/A',
                    'message': condition.message or 'N/A',
                    'last_transition': format_age(condition.last_transition_time)
                })
        
        details = {
            'name': pod.metadata.name,
            'namespace': pod.metadata.namespace,
            'status': get_pod_status(pod),
            'node': pod.spec.node_name or 'N/A',
            'ip': pod.status.pod_ip or 'N/A',
            'created': pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else 'N/A',
            'age': format_age(pod.metadata.creation_timestamp),
            'labels': labels,
            'containers': containers,
            'conditions': conditions
        }
        
        return jsonify(details)
    except ApiException as e:
        app.logger.error(f"Error fetching pod details: {e}")
        return jsonify({'error': str(e)}), e.status
    except Exception as e:
        app.logger.error(f"Error fetching pod details: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/pods/<namespace>/<pod_name>/logs')
def get_pod_logs(namespace, pod_name):
    """Get logs from a pod."""
    container = request.args.get('container')
    tail_lines = request.args.get('tail', 100, type=int)
    
    try:
        v1 = get_k8s_client()
        
        # If no container specified, get the first one
        if not container:
            pod = v1.read_namespaced_pod(pod_name, namespace)
            if pod.spec.containers:
                container = pod.spec.containers[0].name
        
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines
        )
        
        return jsonify({
            'logs': logs,
            'container': container
        })
    except ApiException as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        return jsonify({'error': str(e)}), e.status
    except Exception as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/pods/<namespace>/<pod_name>', methods=['DELETE'])
def delete_pod(namespace, pod_name):
    """Delete a pod."""
    try:
        v1 = get_k8s_client()
        v1.delete_namespaced_pod(pod_name, namespace)
        
        return jsonify({'message': f'Pod {pod_name} deleted successfully'})
    except ApiException as e:
        app.logger.error(f"Error deleting pod: {e}")
        return jsonify({'error': str(e)}), e.status
    except Exception as e:
        app.logger.error(f"Error deleting pod: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/pods/<namespace>/<pod_name>/restart', methods=['POST'])
def restart_pod(namespace, pod_name):
    """Restart a pod by deleting it (it will be recreated by its controller)."""
    try:
        v1 = get_k8s_client()
        v1.delete_namespaced_pod(pod_name, namespace)
        
        return jsonify({'message': f'Pod {pod_name} restarted successfully'})
    except ApiException as e:
        app.logger.error(f"Error restarting pod: {e}")
        return jsonify({'error': str(e)}), e.status
    except Exception as e:
        app.logger.error(f"Error restarting pod: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
