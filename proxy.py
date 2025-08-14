#!/usr/bin/env python3
import requests
from flask import Flask, Response
import re
import os

app = Flask(__name__)

# vLLM metrics URL from environment variable
VLLM_METRICS_URL = os.getenv("VLLM_METRICS_URL")

@app.route('/metrics')
def metrics():
    try:
        # Fetch metrics from vLLM
        response = requests.get(VLLM_METRICS_URL, timeout=10, verify=False)
        
        if response.status_code == 200:
            # Replace colons in metric names with underscores
            content = response.text
            
            # Replace metric names like "vllm:num_requests_running" with "vllm_num_requests_running"
            # This regex looks for metric names at the start of lines (before any labels or values)
            cleaned_content = re.sub(r'^([a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z0-9_:]+)', r'\1_\2', content, flags=re.MULTILINE)
            
            # Also handle any remaining colons in metric names
            lines = []
            for line in cleaned_content.split('\n'):
                if line.startswith('# HELP') or line.startswith('# TYPE'):
                    # Replace colons in HELP and TYPE lines
                    # Format: # HELP metric_name description
                    # Format: # TYPE metric_name type
                    parts = line.split(' ', 3)
                    if len(parts) >= 3:
                        metric_name = parts[2]
                        metric_name = metric_name.replace(':', '_')
                        parts[2] = metric_name
                        line = ' '.join(parts)
                elif line and not line.startswith('#'):
                    # Find the metric name (everything before the first space or {)
                    match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_:]*)(.*)', line)
                    if match:
                        metric_name = match.group(1)
                        rest = match.group(2)
                        # Replace any colons in metric name
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
    print("Starting metrics proxy on http://0.0.0.0:9090/metrics")
    print(f"Proxying metrics from {VLLM_METRICS_URL}")
    app.run(host='0.0.0.0', port=9090)