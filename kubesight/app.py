"""Flask application for KubeSight."""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def get_available_contexts():
    """Get list of available Kubernetes contexts from kubeconfig."""
    try:
        contexts, active_context = config.list_kube_config_contexts()
        context_list = []
        for context in contexts:
            context_info = {
                'name': context['name'],
                'cluster': context['context'].get('cluster', ''),
                'user': context['context'].get('user', ''),
                'namespace': context['context'].get('namespace', 'default'),
                'is_active': context['name'] == active_context['name'] if active_context else False
            }
            context_list.append(context_info)
        return context_list, active_context['name'] if active_context else None
    except Exception as e:
        return [], None


def is_running_in_cluster():
    """Check if the application is running inside a Kubernetes cluster."""
    return os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token')


def load_k8s_config(context_name=None):
    """Load Kubernetes configuration with optional context selection."""
    try:
        if is_running_in_cluster():
            # Running inside a cluster - use service account
            config.load_incluster_config()
            return True, "in-cluster", "Using in-cluster service account configuration"
        else:
            # Running locally - use kubeconfig
            if context_name:
                config.load_kube_config(context=context_name)
                return True, context_name, f"Using Kubernetes context: {context_name}"
            else:
                config.load_kube_config()
                contexts, active_context = config.list_kube_config_contexts()
                return True, active_context['name'] if active_context else 'default', f"Using default Kubernetes context"
    except config.ConfigException as e:
        return False, None, f"Kubernetes configuration error: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error loading Kubernetes config: {str(e)}"


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['USE_MOCK_DATA'] = os.environ.get('USE_MOCK_DATA', 'false').lower() == 'true'
    app.config['RUNNING_IN_CLUSTER'] = is_running_in_cluster()
    
    # Initialize Kubernetes client
    if not app.config['USE_MOCK_DATA']:
        success, context, message = load_k8s_config()
        if success:
            app.config['K8S_CONTEXT'] = context
            app.config['K8S_MESSAGE'] = message
            app.logger.info(message)
        else:
            app.logger.warning(f"Failed to load Kubernetes config: {message}")
            app.config['USE_MOCK_DATA'] = True
            app.config['K8S_MESSAGE'] = f"Using mock data: {message}"
    
    return app


app = create_app()


def get_k8s_client():
    """Get Kubernetes API client."""
    return client.CoreV1Api()


def get_metrics_client():
    """Get Kubernetes Metrics API client."""
    return client.CustomObjectsApi()


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


def get_available_actions(pod_data):
    """Determine available actions based on pod state - HATEOAS compliance."""
    actions = []
    namespace = pod_data['namespace']
    pod_name = pod_data['name']
    status = pod_data['status']
    
    # View logs action - always available if containers exist
    # if pod_data.get('containers'):
    #     for container in pod_data['containers']:
    #         actions.append({
    #             'label': f'LOGS ({container["name"]})',
    #             'href': f'/pods/{namespace}/{pod_name}/logs/{container["name"]}',
    #             'method': 'GET',
    #             'style': 'secondary',
    #             'description': f'View logs for container {container["name"]}'
    #         })
    
    # Restart action - available for running pods
    if status in ['Running', 'Starting', 'Pending']:
        actions.append({
            'label': 'RESTART',
            'href': f'/api/pods/{namespace}/{pod_name}/restart',
            'method': 'POST',
            'style': 'warning',
            'confirm': f'Are you sure you want to restart pod {pod_name}?',
            'description': 'Restart the pod by deleting it (will be recreated by controller)'
        })
    
    # Delete action - available for most pods except system pods
    if not namespace.startswith('kube-') or namespace in ['default', 'production', 'staging', 'development']:
        actions.append({
            'label': 'DELETE',
            'href': f'/api/pods/{namespace}/{pod_name}',
            'method': 'DELETE',
            'style': 'danger',
            'confirm': f'Are you sure you want to delete pod {pod_name}?',
            'description': 'Permanently delete the pod'
        })
    
    return actions


def format_cpu_usage(cpu_str):
    """Format CPU usage from metrics API."""
    if not cpu_str:
        return "N/A"
    
    # CPU can be in nanocores (n) or millicores (m)
    if cpu_str.endswith('n'):
        # Nanocores to millicores
        nanocores = int(cpu_str[:-1])
        millicores = nanocores / 1_000_000
        return f"{millicores:.1f}m"
    elif cpu_str.endswith('m'):
        # Already in millicores
        return cpu_str
    else:
        # Assume it's in cores, convert to millicores
        cores = float(cpu_str)
        return f"{cores * 1000:.1f}m"


def parse_memory_to_bytes(memory_str):
    """Convert memory string to bytes for calculations."""
    if not memory_str:
        return 0
    
    memory_str = memory_str.strip()
    if memory_str.endswith('Ki'):
        return int(float(memory_str[:-2]) * 1024)
    elif memory_str.endswith('Mi'):
        return int(float(memory_str[:-2]) * 1024 * 1024)
    elif memory_str.endswith('Gi'):
        return int(float(memory_str[:-2]) * 1024 * 1024 * 1024)
    elif memory_str.endswith('Ti'):
        return int(float(memory_str[:-2]) * 1024 * 1024 * 1024 * 1024)
    else:
        # Assume bytes
        return int(float(memory_str))


def parse_cpu_to_millicores(cpu_str):
    """Convert CPU string to millicores for calculations."""
    if not cpu_str:
        return 0
    
    cpu_str = cpu_str.strip()
    if cpu_str.endswith('n'):
        # Nanocores to millicores
        return float(cpu_str[:-1]) / 1_000_000
    elif cpu_str.endswith('m'):
        # Already in millicores
        return float(cpu_str[:-1])
    else:
        # Assume it's in cores, convert to millicores
        return float(cpu_str) * 1000


def format_memory_usage(memory_str):
    """Format memory usage from metrics API."""
    if not memory_str:
        return "N/A"
    
    bytes_val = parse_memory_to_bytes(memory_str)
    
    if bytes_val >= 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f}Gi"
    elif bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f}Mi"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f}Ki"
    return f"{bytes_val}B"


def format_memory_with_percentage(used_str, requested_str):
    """Format memory usage with percentage and ratio."""
    if not used_str:
        return "N/A"
    
    used_bytes = parse_memory_to_bytes(used_str)
    
    if not requested_str:
        # No limit/request specified, just show usage
        return format_memory_usage(used_str)
    
    requested_bytes = parse_memory_to_bytes(requested_str)
    
    if requested_bytes == 0:
        return format_memory_usage(used_str)
    
    percentage = (used_bytes / requested_bytes) * 100
    used_formatted = format_memory_usage(used_str)
    requested_formatted = format_memory_usage(requested_str)
    
    return f"{used_formatted} / {requested_formatted} ({percentage:.0f}%)"


def format_cpu_with_percentage(used_str, requested_str):
    """Format CPU usage with percentage and ratio."""
    if not used_str:
        return "N/A"
    
    used_millicores = parse_cpu_to_millicores(used_str)
    
    if not requested_str:
        # No limit/request specified, just show usage
        return format_cpu_usage(used_str)
    
    requested_millicores = parse_cpu_to_millicores(requested_str)
    
    if requested_millicores == 0:
        return format_cpu_usage(used_str)
    
    percentage = (used_millicores / requested_millicores) * 100
    used_formatted = format_cpu_usage(used_str)
    requested_formatted = format_cpu_usage(requested_str)
    
    return f"{used_formatted} / {requested_formatted} ({percentage:.0f}%)"


def get_pod_metrics(namespace, pod_name):
    """Get CPU and memory metrics for a pod."""
    try:
        metrics_api = get_metrics_client()
        
        # Get pod metrics from metrics-server API
        pod_metrics = metrics_api.get_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
            name=pod_name
        )
        
        containers_metrics = {}
        if 'containers' in pod_metrics:
            for container_metric in pod_metrics['containers']:
                container_name = container_metric['name']
                usage = container_metric.get('usage', {})
                
                containers_metrics[container_name] = {
                    'cpu': format_cpu_usage(usage.get('cpu', '')),
                    'memory': format_memory_usage(usage.get('memory', ''))
                }
        
        return containers_metrics
    except Exception as e:
        app.logger.warning(f"Could not fetch metrics for pod {pod_name}: {e}")
        return {}


@app.route('/api')
def api_root():
    """HATEOAS API root - provides entry points to all available API resources."""
    api_info = {
        'title': 'KubeSight API',
        'version': '1.0.0',
        'description': 'Kubernetes monitoring API with full HATEOAS support',
        '_links': {
            'self': {'href': '/api', 'method': 'GET'},
            'namespaces': {'href': '/api/namespaces', 'method': 'GET'},
            'pods': {'href': '/api/pods{?namespace,search}', 'method': 'GET', 'templated': True},
            'contexts': {'href': '/api/contexts', 'method': 'GET'},
            'dashboard': {'href': '/', 'method': 'GET'}
        },
        '_actions': [
            {
                'name': 'list_pods',
                'title': 'List Pods',
                'method': 'GET',
                'href': '/api/pods',
                'fields': [
                    {'name': 'namespace', 'type': 'text', 'required': False},
                    {'name': 'search', 'type': 'text', 'required': False}
                ]
            },
            {
                'name': 'switch_context',
                'title': 'Switch Context',
                'method': 'GET',
                'href': '/contexts/{context_name}',
                'templated': True
            }
        ]
    }
    
    return jsonify(api_info)


@app.route('/')
def index():
    """Home page with pod list and HATEOAS navigation."""
    # Check if we need to show context selection
    if not app.config.get('RUNNING_IN_CLUSTER') and not app.config.get('USE_MOCK_DATA'):
        if 'selected_context' not in session:
            return redirect(url_for('select_context'))
    
    # Add HATEOAS navigation actions
    nav_actions = [

    ]
    
    # Add context switching actions for base template
    context_actions = []
    if not app.config.get('RUNNING_IN_CLUSTER'):
        context_actions = [
            {
                'href': '/contexts',
                'style': 'secondary',
                'label': 'SWITCH CONTEXT'
            }
        ]
    
    # Add API endpoints for HTMX requests
    api_endpoints = {
        'namespaces': '/api/namespaces',
        'pods': '/api/pods'
    }
    
    return render_template('index.html', 
                         k8s_context=app.config.get('K8S_CONTEXT'),
                         k8s_message=app.config.get('K8S_MESSAGE'),
                         running_in_cluster=app.config.get('RUNNING_IN_CLUSTER'),
                         nav_actions=nav_actions,
                         context_actions=context_actions,
                         api_endpoints=api_endpoints)


@app.route('/contexts')
def select_context():
    """Show available Kubernetes contexts for selection with HATEOAS actions."""
    if app.config.get('RUNNING_IN_CLUSTER'):
        # Redirect to main page if running in cluster
        return redirect(url_for('index'))
    
    contexts, active_context = get_available_contexts()
    if not contexts:
        error_actions = [
            {
                'href': '/',
                'style': 'primary',
                'label': 'GO TO DASHBOARD'
            },
            {
                'href': '/contexts',
                'style': 'secondary',
                'label': 'REFRESH CONTEXTS'
            }
        ]
        
        return render_template('error.html', 
                             title='No Kubernetes Contexts Found',
                             message='No Kubernetes contexts found. Please check your kubeconfig file.',
                             error_actions=error_actions)
    
    # Add HATEOAS actions to each context
    for context in contexts:
        context['_links'] = {
            'self': {'href': f'/api/contexts/{context["name"]}', 'method': 'GET'},
            'use': {'href': f'/contexts/{context["name"]}', 'method': 'GET'},
            'refresh': {'href': '/contexts', 'method': 'GET'}
        }
        context['_actions'] = []
        
        if not context.get('is_active'):
            context['_actions'].append({
                'label': 'USE THIS CONTEXT',
                'href': f'/contexts/{context["name"]}',
                'method': 'GET',
                'style': 'primary',
                'description': f'Switch to {context["name"]} context'
            })
    
    # Add global actions
    global_actions = [
        {
            'label': 'REFRESH CONTEXTS',
            'href': '/contexts',
            'method': 'GET',
            'style': 'secondary',
            'description': 'Reload available contexts'
        }
    ]
    
    return render_template('context_selector.html', 
                         contexts=contexts, 
                         active_context=active_context,
                         global_actions=global_actions)


@app.route('/api/contexts')
def api_contexts():
    """Get available contexts as JSON with HATEOAS links."""
    if app.config.get('RUNNING_IN_CLUSTER'):
        return jsonify({
            'contexts': [],
            'message': 'Running in cluster mode',
            '_links': {
                'self': {'href': '/api/contexts'},
                'dashboard': {'href': '/'}
            }
        })
    
    contexts, active_context = get_available_contexts()
    for context in contexts:
        context['_links'] = {
            'self': {'href': f'/api/contexts/{context["name"]}'},
            'use': {'href': f'/contexts/{context["name"]}', 'method': 'GET'}
        }
    
    return jsonify({
        'contexts': contexts,
        'active_context': active_context,
        '_links': {
            'self': {'href': '/api/contexts'},
            'refresh': {'href': '/contexts', 'method': 'GET'}
        }
    })


@app.route('/contexts/<context_name>')
def use_context(context_name):
    """Switch to a specific Kubernetes context."""
    if app.config.get('RUNNING_IN_CLUSTER'):
        return redirect(url_for('index'))
    
    success, context, message = load_k8s_config(context_name)
    if success:
        session['selected_context'] = context_name
        app.config['K8S_CONTEXT'] = context
        app.config['K8S_MESSAGE'] = message
        app.logger.info(f"Switched to context: {context_name}")
        return redirect(url_for('index'))
    else:
        contexts, active_context = get_available_contexts()
        return render_template('context_selector.html', 
                             contexts=contexts, 
                             active_context=active_context,
                             error=f"Failed to switch context: {message}")


@app.route('/api/namespaces')
def get_namespaces():
    """Get list of namespaces as HTML options with HATEOAS links."""
    if app.config.get('USE_MOCK_DATA'):
        from kubesight.mock_data import get_mock_namespaces
        ns_list = get_mock_namespaces()['namespaces']
        # Add HATEOAS actions to each namespace
        for ns in ns_list:
            ns['_links'] = {
                'self': {'href': f'/api/namespaces/{ns["name"]}'},
                'pods': {'href': f'/api/pods?namespace={ns["name"]}'},
                'select': {'href': f'/api/namespaces/{ns["name"]}/select', 'method': 'POST'}
            }
        return render_template('namespace_options.html', namespaces=ns_list)
    
    try:
        v1 = get_k8s_client()
        namespaces = v1.list_namespace()
        
        ns_list = []
        for ns in namespaces.items:
            ns_data = {
                'name': ns.metadata.name,
                'status': ns.status.phase,
                'age': format_age(ns.metadata.creation_timestamp),
                '_links': {
                    'self': {'href': f'/api/namespaces/{ns.metadata.name}'},
                    'pods': {'href': f'/api/pods?namespace={ns.metadata.name}'},
                    'select': {'href': f'/api/namespaces/{ns.metadata.name}/select', 'method': 'POST'}
                }
            }
            ns_list.append(ns_data)
        
        return render_template('namespace_options.html', namespaces=ns_list)
    except Exception as e:
        app.logger.error(f"Error fetching namespaces: {e}")
        error_msg = 'Failed to fetch namespaces' if not app.debug else str(e)
        return f'<option value="default">Error: {error_msg}</option>', 500


@app.route('/api/pods')
def get_pods():
    """Get list of pods, optionally filtered by namespace."""
    namespace = request.args.get('namespace', 'default')
    search = request.args.get('search', '').lower()
    
    if app.config.get('USE_MOCK_DATA'):
        from kubesight.mock_data import get_mock_pods
        pod_list = get_mock_pods(namespace, search)
        return render_template('pods_table.html', pods=pod_list)
    
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
            
            pod_data = {
                'name': pod_name,
                'namespace': pod_ns,
                'status': get_pod_status(pod),
                'ready': f"{ready_containers}/{total_containers}",
                'restarts': restart_count,
                'age': format_age(pod.metadata.creation_timestamp),
                'node': pod.spec.node_name or 'N/A',
                '_links': {
                    'self': {'href': f'/pods/{pod_ns}/{pod_name}', 'method': 'GET'},
                    'logs': {'href': f'/pods/{pod_ns}/{pod_name}/logs', 'method': 'GET'},
                    'delete': {'href': f'/pods/{pod_ns}/{pod_name}/delete', 'method': 'POST'},
                    'restart': {'href': f'/pods/{pod_ns}/{pod_name}/restart', 'method': 'POST'}
                }
            }
            
            # Add conditional actions based on pod state
            pod_status = get_pod_status(pod)
            if pod_status in ['Running', 'Starting', 'Pending']:
                pod_data['_actions'] = get_available_actions({
                    'name': pod_name, 
                    'namespace': pod_ns, 
                    'status': pod_status,
                    'containers': []
                })
            
            pod_list.append(pod_data)
        
        # Return HTML for HTMX
        return render_template('pods_table.html', pods=pod_list)
    except Exception as e:
        app.logger.error(f"Error fetching pods: {e}")
        error_msg = 'Failed to fetch pods' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', 500


@app.route('/pods/<namespace>/<pod_name>')
def pod_details_page(namespace, pod_name):
    """Show detailed information about a specific pod as a full page."""
    if app.config.get('USE_MOCK_DATA'):
        from kubesight.mock_data import get_mock_pod_details
        pod_data = get_mock_pod_details(namespace, pod_name)
        return render_template('pod_details.html', pod=pod_data)
    
    try:
        v1 = get_k8s_client()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        
        # Get metrics for the pod
        pod_metrics = get_pod_metrics(namespace, pod_name)
        
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
                
                # Get metrics for this container
                container_metrics = pod_metrics.get(container.name, {})
                
                # Extract resource requests and limits
                cpu_request = None
                memory_request = None
                cpu_limit = None
                memory_limit = None
                
                if container.resources:
                    if container.resources.requests:
                        cpu_request = container.resources.requests.get('cpu')
                        memory_request = container.resources.requests.get('memory')
                    if container.resources.limits:
                        cpu_limit = container.resources.limits.get('cpu')
                        memory_limit = container.resources.limits.get('memory')
                
                # Format metrics with percentages
                cpu_usage_raw = container_metrics.get('cpu', '')
                memory_usage_raw = container_metrics.get('memory', '')
                
                # Use limit first, then request for percentage calculation
                cpu_base = cpu_limit or cpu_request
                memory_base = memory_limit or memory_request
                
                cpu_display = format_cpu_with_percentage(cpu_usage_raw, cpu_base) if cpu_base else format_cpu_usage(cpu_usage_raw)
                memory_display = format_memory_with_percentage(memory_usage_raw, memory_base) if memory_base else format_memory_usage(memory_usage_raw)
                
                containers.append({
                    'name': container.name,
                    'image': container.image,
                    'ready': container_status.ready if container_status else False,
                    'restart_count': container_status.restart_count if container_status else 0,
                    'state': str(container_status.state) if container_status else 'Unknown',
                    'cpu_usage': cpu_display,
                    'memory_usage': memory_display
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
        
        pod_data = {
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
        
        # Add HATEOAS-compliant actions based on pod state
        pod_data['actions'] = get_available_actions(pod_data)
        
        # Add HATEOAS navigation links
        pod_data['_links'] = {
            'self': {'href': f'/pods/{namespace}/{pod_name}'},
            'dashboard': {'href': '/', 'label': 'Dashboard'},
            'logs': {'href': f'/pods/{namespace}/{pod_name}/logs', 'method': 'GET'}
        }
        
        # Add container links
        for container in pod_data.get('containers', []):
            container['_links'] = {
                'logs': {'href': f'/pods/{namespace}/{pod_name}/logs/{container["name"]}'}
            }
        
        return render_template('pod_details.html', pod=pod_data)
    except ApiException as e:
        app.logger.error(f"Error fetching pod details: {e}")
        error_msg = 'Failed to fetch pod details' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', e.status
    except Exception as e:
        app.logger.error(f"Error fetching pod details: {e}")
        error_msg = 'Failed to fetch pod details' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', 500


@app.route('/pods/<namespace>/<pod_name>/logs/<container>')
def pod_logs_page(namespace, pod_name, container):
    """Show logs from a pod container as a full page."""
    tail_lines = request.args.get('tail', 100, type=int)
    
    if app.config.get('USE_MOCK_DATA'):
        from kubesight.mock_data import get_mock_pod_logs
        log_data = get_mock_pod_logs(namespace, pod_name, container)
        return render_template('logs.html', 
                             pod_name=pod_name, 
                             namespace=namespace,
                             container=container, 
                             logs=log_data['logs'])
    
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
        
        nav_links = {
            'back': {
                'href': f'/pods/{namespace}/{pod_name}',
                'label': 'BACK TO POD DETAILS'
            }
        }
        
        return render_template('logs.html', 
                             pod_name=pod_name, 
                             namespace=namespace,
                             container=container, 
                             logs=logs,
                             nav_links=nav_links)
    except ApiException as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        error_msg = 'Failed to fetch pod logs' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', e.status
    except Exception as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        error_msg = 'Failed to fetch pod logs' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', 500


@app.route('/api/pods/<namespace>/<pod_name>/logs')
def pod_logs_api(namespace, pod_name):
    """API endpoint for container logs - returns modal content via HTMX."""
    container = request.args.get('container')
    tail_lines = request.args.get('tail', 100, type=int)
    
    if not container:
        return '<div class="error">Container parameter required</div>', 400
    
    if app.config.get('USE_MOCK_DATA'):
        from kubesight.mock_data import get_mock_pod_logs
        log_data = get_mock_pod_logs(namespace, pod_name, container)
        return render_template('pod_logs_modal.html',
                             pod_name=pod_name,
                             namespace=namespace, 
                             container=container,
                             logs=log_data['logs'])
    
    try:
        v1 = get_k8s_client()
        
        # Get pod logs for the specific container
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
            timestamps=True
        )
        
        # Add HATEOAS navigation for modal
        nav_links = {
            'pod_details': f'/pods/{namespace}/{pod_name}',
            'full_logs': f'/pods/{namespace}/{pod_name}/logs/{container}',
            'dashboard': '/'
        }
        
        return render_template('pod_logs_modal.html',
                             pod_name=pod_name,
                             namespace=namespace,
                             container=container,
                             logs=logs,
                             nav_links=nav_links)
                             
    except ApiException as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        error_msg = 'Failed to fetch pod logs' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', e.status
    except Exception as e:
        app.logger.error(f"Error fetching pod logs: {e}")
        error_msg = 'Failed to fetch pod logs' if not app.debug else str(e)
        return f'<div class="error">Error: {error_msg}</div>', 500


@app.route('/pods/<namespace>/<pod_name>/delete')
def delete_pod(namespace, pod_name):
    """Delete a pod and redirect to main page."""
    if app.config.get('USE_MOCK_DATA'):
        from flask import redirect, url_for, flash
        flash(f'Pod {pod_name} deleted successfully (mock mode)', 'success')
        return redirect(url_for('index'))
    
    try:
        from flask import redirect, url_for, flash
        v1 = get_k8s_client()
        v1.delete_namespaced_pod(pod_name, namespace)
        
        flash(f'Pod {pod_name} deleted successfully', 'success')
        return redirect(url_for('index'))
    except ApiException as e:
        from flask import redirect, url_for, flash
        app.logger.error(f"Error deleting pod: {e}")
        error_msg = 'Failed to delete pod' if not app.debug else str(e)
        flash(f'Error: {error_msg}', 'error')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))
    except Exception as e:
        from flask import redirect, url_for, flash
        app.logger.error(f"Error deleting pod: {e}")
        error_msg = 'Failed to delete pod' if not app.debug else str(e)
        flash(f'Error: {error_msg}', 'error')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))


@app.route('/pods/<namespace>/<pod_name>/restart')
def restart_pod(namespace, pod_name):
    """Restart a pod by deleting it (it will be recreated by its controller)."""
    if app.config.get('USE_MOCK_DATA'):
        from flask import redirect, url_for, flash
        flash(f'Pod {pod_name} restarted successfully (mock mode)', 'success')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))
    
    try:
        from flask import redirect, url_for, flash
        v1 = get_k8s_client()
        v1.delete_namespaced_pod(pod_name, namespace)
        
        flash(f'Pod {pod_name} restarted successfully', 'success')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))
    except ApiException as e:
        from flask import redirect, url_for, flash
        app.logger.error(f"Error restarting pod: {e}")
        error_msg = 'Failed to restart pod' if not app.debug else str(e)
        flash(f'Error: {error_msg}', 'error')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))
    except Exception as e:
        from flask import redirect, url_for, flash
        app.logger.error(f"Error restarting pod: {e}")
        error_msg = 'Failed to restart pod' if not app.debug else str(e)
        flash(f'Error: {error_msg}', 'error')
        return redirect(url_for('pod_details_page', namespace=namespace, pod_name=pod_name))


@app.route('/api/pods/<namespace>/<pod_name>/metrics')
def get_pod_metrics_endpoint(namespace, pod_name):
    """Get CPU and memory metrics for a pod as JSON."""
    if app.config.get('USE_MOCK_DATA'):
        return jsonify({
            'nginx': {
                'cpu': '15.2m / 100m (15%)',
                'memory': '64Mi / 128Mi (50%)'
            }
        })
    
    try:
        metrics = get_pod_metrics(namespace, pod_name)
        return jsonify(metrics)
    except Exception as e:
        app.logger.error(f"Error fetching pod metrics: {e}")
        return jsonify({'error': 'Failed to fetch metrics'}), 500


if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
