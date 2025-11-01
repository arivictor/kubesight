"""Mock data for development and testing without a Kubernetes cluster."""

from datetime import datetime, timedelta
import random


def get_mock_namespaces():
    """Return mock namespace data."""
    return {
        'namespaces': [
            {'name': 'default', 'status': 'Active', 'age': '30d'},
            {'name': 'kube-system', 'status': 'Active', 'age': '30d'},
            {'name': 'kube-public', 'status': 'Active', 'age': '30d'},
            {'name': 'production', 'status': 'Active', 'age': '15d'},
            {'name': 'staging', 'status': 'Active', 'age': '10d'},
            {'name': 'development', 'status': 'Active', 'age': '5d'},
        ]
    }


def get_mock_pods(namespace='default', search=''):
    """Return mock pod data."""
    all_pods = [
        {
            'name': 'nginx-deployment-5d59b8b8c6-abcde',
            'namespace': 'default',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 0,
            'age': '3d',
            'node': 'node-1'
        },
        {
            'name': 'redis-master-0',
            'namespace': 'default',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 1,
            'age': '5d',
            'node': 'node-2'
        },
        {
            'name': 'postgres-db-xyz123',
            'namespace': 'default',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 0,
            'age': '7d',
            'node': 'node-1'
        },
        {
            'name': 'api-server-deployment-abc123',
            'namespace': 'production',
            'status': 'Running',
            'ready': '2/2',
            'restarts': 0,
            'age': '1d',
            'node': 'node-3'
        },
        {
            'name': 'worker-pod-1',
            'namespace': 'production',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 3,
            'age': '12h',
            'node': 'node-2'
        },
        {
            'name': 'frontend-app-def456',
            'namespace': 'staging',
            'status': 'Starting',
            'ready': '0/1',
            'restarts': 0,
            'age': '2m',
            'node': 'node-1'
        },
        {
            'name': 'coredns-78fcd69978-p9q8r',
            'namespace': 'kube-system',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 0,
            'age': '30d',
            'node': 'node-1'
        },
        {
            'name': 'kube-proxy-xvw9k',
            'namespace': 'kube-system',
            'status': 'Running',
            'ready': '1/1',
            'restarts': 0,
            'age': '30d',
            'node': 'node-2'
        },
    ]
    
    # Filter by namespace
    if namespace and namespace != 'all':
        all_pods = [p for p in all_pods if p['namespace'] == namespace]
    
    # Filter by search term
    if search:
        search_lower = search.lower()
        all_pods = [
            p for p in all_pods 
            if search_lower in p['name'].lower() or search_lower in p['namespace'].lower()
        ]
    
    return all_pods


def get_mock_pod_details(namespace, pod_name):
    """Return mock pod details."""
    return {
        'name': pod_name,
        'namespace': namespace,
        'status': 'Running',
        'node': 'node-1',
        'ip': '10.244.0.5',
        'created': (datetime.utcnow() - timedelta(days=3)).isoformat(),
        'age': '3d',
        'labels': {
            'app': 'nginx',
            'version': 'v1.0',
            'environment': 'production',
            'team': 'platform'
        },
        'containers': [
            {
                'name': 'nginx',
                'image': 'nginx:1.21-alpine',
                'ready': True,
                'restart_count': 0,
                'state': 'Running'
            }
        ],
        'conditions': [
            {
                'type': 'Initialized',
                'status': 'True',
                'reason': 'PodCompleted',
                'message': 'All init containers have completed successfully',
                'last_transition': '5m'
            },
            {
                'type': 'Ready',
                'status': 'True',
                'reason': 'ContainersReady',
                'message': 'All containers are ready',
                'last_transition': '5m'
            },
            {
                'type': 'ContainersReady',
                'status': 'True',
                'reason': 'ContainersReady',
                'message': 'All containers are ready',
                'last_transition': '5m'
            },
            {
                'type': 'PodScheduled',
                'status': 'True',
                'reason': 'PodScheduled',
                'message': 'Successfully assigned to node-1',
                'last_transition': '3d'
            }
        ]
    }


def get_mock_pod_logs(namespace, pod_name, container=None):
    """Return mock pod logs."""
    logs = """2025-11-01 07:00:00 INFO Starting application...
2025-11-01 07:00:01 INFO Connecting to database
2025-11-01 07:00:02 INFO Database connection established
2025-11-01 07:00:03 INFO Loading configuration
2025-11-01 07:00:04 INFO Configuration loaded successfully
2025-11-01 07:00:05 INFO Starting HTTP server on port 8080
2025-11-01 07:00:06 INFO Server started successfully
2025-11-01 07:15:23 INFO Received GET request for /health
2025-11-01 07:15:23 INFO Health check passed
2025-11-01 07:30:45 INFO Received GET request for /api/data
2025-11-01 07:30:45 INFO Processing request...
2025-11-01 07:30:46 INFO Request processed successfully
2025-11-01 08:00:00 INFO Performing scheduled task
2025-11-01 08:00:01 INFO Task completed successfully
"""
    
    return {
        'logs': logs,
        'container': container or 'main'
    }
