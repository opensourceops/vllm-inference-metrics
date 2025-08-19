# vLLM Inference Metrics

A comprehensive metrics collection and monitoring solution for vLLM deployments using Fluent Bit and Parseable with Prometheus-format compatibility.

## Table of Contents

- [vLLM Inference Metrics](#vllm-inference-metrics)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Why Monitor vLLM Inference?](#why-monitor-vllm-inference)
  - [Architecture](#architecture)
  - [Components](#components)
    - [1. Metrics Proxy (`proxy.py`)](#1-metrics-proxy-proxypy)
    - [2. Fluent Bit](#2-fluent-bit)
    - [3. Parseable](#3-parseable)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [Configuration](#configuration)
  - [Monitoring](#monitoring)
  - [Metrics Format](#metrics-format)
  - [Troubleshooting](#troubleshooting)
  - [Development](#development)
  - [Security Notes](#security-notes)
  - [Production Considerations](#production-considerations)

## Overview

This repo provides a complete observability stack for vLLM services by:

- **Proxying vLLM metrics** with Prometheus-format compatibility fixes
- **Collecting metrics** using Fluent Bit
- **Storing metrics** in Parseable for analysis and visualization
- **Containerized deployment** with Podman Compose

## Why Monitor vLLM Inference?

Modern AI inference is the future of computational workloads. While open-source models like GPT-OSS-20B deployed on high-performance hardware (GPUs via RunPod) deliver exceptional capabilities, understanding what happens under the hood through metrics provides:

- **Performance optimization** - Identify bottlenecks and resource utilization patterns
- **Cost control** - Monitor GPU usage and request patterns for efficient scaling
- **Reliability insights** - Track error rates, response times, and system health
- **Capacity planning** - Understand throughput limits and scaling requirements

Metrics-driven inference operations transform black-box model serving into a transparent, controllable, and optimizable system.

## Architecture

```
vLLM Service → Metrics Proxy → Fluent Bit → Parseable
     ↓              ↓             ↓           ↓
   Metrics      Sanitization   Collection   Storage
```

## Components

### 1. Metrics Proxy (`proxy.py`)

- Flask-based HTTP proxy service
- Sanitizes vLLM metric names by replacing colons with underscores
- Ensures Prometheus-format compatibility
- Runs on port 9090

### 2. Fluent Bit

- Scrapes metrics from the proxy every 2 seconds
- Forwards metrics to Parseable via OpenTelemetry protocol
- Configured via `fluent-bit.conf`

### 3. Parseable

- Time-series data storage and analysis platform
- Web UI available on port 8080
- Stores metrics in the `vLLMmetrics` stream

## Prerequisites

- Podman with Podman Compose (or Docker with Docker Compose)
- Open ports: `9090` (proxy), `8080` (Parseable UI)
- vLLM metrics endpoint reachable from the host running the stack

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/opensourceops/vllm-inference-metrics.git
   cd vllm-inference-metrics
   ```

2. **Configure vLLM endpoint**

   Replace the `VLLM_METRICS_URL` in `compose.yml` with your vLLM deployment endpoint:

   ```yaml
   environment:
     - VLLM_METRICS_URL=https://your-vllm-endpoint/metrics
   ```

   For local vLLM deployments:

   ```yaml
   environment:
     - VLLM_METRICS_URL=http://localhost:8000/metrics
   ```

3. **Start the stack**

   ```bash
   podman compose up -d
   ```

   Using Docker instead of Podman:

   ```bash
   docker compose up -d
   ```

4. **Access services**
   - Parseable UI: http://localhost:8080 (admin/admin)
   - Metrics endpoint: http://localhost:9090/metrics

## Configuration

### Environment Variables

| Variable           | Description                    | Default        |
| ------------------ | ------------------------------ | -------------- |
| `VLLM_METRICS_URL` | vLLM metrics endpoint URL      | Required       |
| `P_USERNAME`       | Parseable username             | `admin`        |
| `P_PASSWORD`       | Parseable password             | `admin`        |
| `P_ADDR`           | Parseable listen address       | `0.0.0.0:8000` |
| `P_STAGING_DIR`    | Parseable staging dir (volume) | `/staging`     |

Note: Parseable-related environment variables are defined in `parseable.env` and loaded via `env_file` in `compose.yml`.

### Ports

| Service      | Container | Host |
| ------------ | --------- | ---- |
| Proxy        | 9090      | 9090 |
| Parseable UI | 8000      | 8080 |

### Fluent Bit Configuration

Key settings in `fluent-bit.conf`:

- **Scrape Interval**: 2 seconds
- **Target**: proxy:9090/metrics
- **Output**: Parseable OpenTelemetry endpoint

## Monitoring

### Health Checks

- Proxy service includes HTTP health check
- Services have dependency management and restart policies

### Logs

View service logs:

```bash
podman compose logs -f [service-name]
```

## Metrics Format

The proxy transforms vLLM metrics from:

```
vllm:num_requests_running 5
```

To Prometheus-compatible format:

```
vllm_num_requests_running 5
```

## Troubleshooting

### Common Issues

1. **Connection refused to vLLM**

   - Verify `VLLM_METRICS_URL` is accessible
   - Check network connectivity

2. **Parseable not receiving data**

   - Check Fluent Bit logs: `podman compose logs -f fluentbit`
   - Verify proxy health: `curl http://localhost:9090/metrics`

3. **Proxy errors**
   - Check SSL/TLS settings for vLLM endpoint
   - Verify vLLM metrics endpoint responds

### Service Dependencies

Services start in order:

1. Parseable
2. Proxy (with health check)
3. Fluent Bit

## Development

### Local Testing

Test the proxy standalone:

```bash
export VLLM_METRICS_URL=https://your-vllm-endpoint/metrics
pip install flask requests
python proxy.py
```

Stop and remove the stack:

```bash
podman compose down
```

### Configuration Changes

After modifying configurations:

```bash
podman compose down
podman compose up -d
```

## Security Notes

- Default credentials are `admin/admin` - change in production
- Proxy disables SSL verification - configure properly for production
- Consider network security for metric endpoints

## Production Considerations

This is a demo/development setup designed to get you started quickly. For production deployments, consider:

- **Security**: Replace default credentials, implement secrets management, enable SSL/TLS
- **Images**: Pin specific versions instead of `edge`/`latest` tags
- **Resources**: Add memory/CPU limits and proper resource allocation
- **Monitoring**: Implement logging, alerting, and backup strategies for the metrics stack itself
- **Networking**: Configure proper network security and access controls

The compose.yml provides a solid foundation - customize it based on your production requirements.

## License

MIT License
