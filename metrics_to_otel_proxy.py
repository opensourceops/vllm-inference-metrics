#!/usr/bin/env python3
import requests
from flask import Flask, Response, jsonify
import re
import time
import json

app = Flask(__name__)

# Local metrics proxy URL (already has cleaned metrics)
METRICS_URL = "http://127.0.0.1:9090/metrics"

def prometheus_to_otel_json(prometheus_text):
    """Convert Prometheus text format to OpenTelemetry JSON format"""
    
    # Initialize the structure
    otel_json = {
        "resourceMetrics": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "vllm-metrics"}},
                    {"key": "service.instance.id", "value": {"stringValue": "runpod-instance"}},
                    {"key": "source", "value": {"stringValue": "prometheus"}}
                ]
            },
            "scopeMetrics": [{
                "scope": {
                    "name": "prometheus-receiver",
                    "version": "1.0.0"
                },
                "metrics": []
            }]
        }]
    }
    
    metrics_dict = {}
    histogram_descriptions = {}  # Store descriptions for histogram base metrics
    current_metric = None
    
    for line in prometheus_text.split('\n'):
        line = line.strip()
        
        if not line or line.startswith('#'):
            # Handle HELP and TYPE lines
            if line.startswith('# HELP'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    metric_name = parts[2].replace(':', '_')
                    description = parts[3]
                    if metric_name not in metrics_dict:
                        metrics_dict[metric_name] = {
                            "name": metric_name,
                            "description": description,
                            "dataPoints": []
                        }
            elif line.startswith('# TYPE'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    metric_name = parts[2].replace(':', '_')
                    metric_type = parts[3]
                    if metric_name in metrics_dict:
                        metrics_dict[metric_name]["type"] = metric_type
                    # For histogram metrics, store the base description
                    if metric_type == "histogram" and metric_name in metrics_dict:
                        histogram_descriptions[metric_name] = metrics_dict[metric_name].get("description", "")
            continue
        
        # Parse metric line
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_:]*)\s*(?:\{([^}]*)\})?\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(?:(\d+))?', line)
        if match:
            metric_name = match.group(1).replace(':', '_')
            labels = match.group(2)
            value = float(match.group(3))
            timestamp = match.group(4)
            
            # Initialize metric if not exists
            if metric_name not in metrics_dict:
                # Check if this is a histogram component
                base_name = None
                description = ""
                if metric_name.endswith(('_bucket', '_count', '_sum')):
                    # Find the base metric name
                    for suffix in ['_bucket', '_count', '_sum']:
                        if metric_name.endswith(suffix):
                            base_name = metric_name[:-len(suffix)]
                            break
                    # Use the histogram description if available
                    if base_name and base_name in histogram_descriptions:
                        description = histogram_descriptions[base_name]
                
                metrics_dict[metric_name] = {
                    "name": metric_name,
                    "description": description,
                    "dataPoints": [],
                    "type": "gauge"  # default type
                }
            
            # Parse labels
            attributes = []
            if labels:
                # Parse label pairs
                label_pairs = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', labels)
                for key, val in label_pairs:
                    attributes.append({
                        "key": key,
                        "value": {"stringValue": val}
                    })
            
            # Create data point
            current_time_nano = int(time.time() * 1e9)
            data_point = {
                "attributes": attributes,
                "timeUnixNano": str(current_time_nano),
                "asDouble": value
            }
            
            # Add startTimeUnixNano for cumulative metrics
            if metrics_dict[metric_name].get("type") in ["counter"]:
                start_time_nano = current_time_nano - int(60 * 1e9)  # 1 minute ago
                data_point["startTimeUnixNano"] = str(start_time_nano)
            
            metrics_dict[metric_name]["dataPoints"].append(data_point)
    
    # Convert metrics_dict to OTEL format
    for metric_name, metric_data in metrics_dict.items():
        otel_metric = {
            "name": metric_name,
            "description": metric_data.get("description", "")
        }
        
        # Set the metric type specific fields
        metric_type = metric_data.get("type", "gauge")
        if metric_type == "counter":
            otel_metric["sum"] = {
                "dataPoints": metric_data["dataPoints"],
                "aggregationTemporality": 2,  # AGGREGATION_TEMPORALITY_CUMULATIVE
                "isMonotonic": True
            }
        elif metric_type == "histogram":
            otel_metric["histogram"] = {
                "dataPoints": metric_data["dataPoints"],
                "aggregationTemporality": 2
            }
        else:  # gauge
            otel_metric["gauge"] = {
                "dataPoints": metric_data["dataPoints"]
            }
        
        otel_json["resourceMetrics"][0]["scopeMetrics"][0]["metrics"].append(otel_metric)
    
    return otel_json

@app.route('/metrics/otel')
def metrics_otel():
    try:
        # Fetch metrics from local proxy
        response = requests.get(METRICS_URL, timeout=10)
        
        if response.status_code == 200:
            # Convert to OTEL JSON format
            otel_json = prometheus_to_otel_json(response.text)
            
            return jsonify(otel_json)
        else:
            return jsonify({"error": f"Failed to fetch metrics: HTTP {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to fetch metrics: {str(e)}"}), 500

@app.route('/metrics')
def metrics():
    """Keep the original cleaned Prometheus metrics endpoint"""
    try:
        response = requests.get(METRICS_URL, timeout=10)
        
        if response.status_code == 200:
            content = response.text
            cleaned_content = re.sub(r'^([a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z0-9_:]+)', r'\1_\2', content, flags=re.MULTILINE)
            
            lines = []
            for line in cleaned_content.split('\n'):
                if line.startswith('# HELP') or line.startswith('# TYPE'):
                    parts = line.split(' ', 3)
                    if len(parts) >= 3:
                        metric_name = parts[2]
                        metric_name = metric_name.replace(':', '_')
                        parts[2] = metric_name
                        line = ' '.join(parts)
                elif line and not line.startswith('#'):
                    match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_:]*)(.*)', line)
                    if match:
                        metric_name = match.group(1)
                        rest = match.group(2)
                        metric_name = metric_name.replace(':', '_')
                        line = metric_name + rest
                lines.append(line)
            
            cleaned_content = '\n'.join(lines)
            return Response(cleaned_content, mimetype='text/plain')
        else:
            return Response(f"# Error fetching metrics: HTTP {response.status_code}", 
                          mimetype='text/plain', status=500)
    except Exception as e:
        return Response(f"# Error fetching metrics: {str(e)}", 
                      mimetype='text/plain', status=500)

if __name__ == '__main__':
    print("Starting metrics proxy with OTEL JSON endpoint on http://127.0.0.1:9091/metrics/otel")
    print("Original Prometheus endpoint still available at http://127.0.0.1:9091/metrics")
    print(f"Proxying metrics from {METRICS_URL}")
    app.run(host='127.0.0.1', port=9091)
