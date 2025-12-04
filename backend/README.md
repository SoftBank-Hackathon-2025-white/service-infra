### requirements

fastapi
uvicorn
psutil

### installation

```bash
pip install -r requirements.txt
```

### endpoint

```bash
GET /metrics
```

### 예시 응답(json)

```json
{
  "timestamp": 1739960499.193848,
  "cpu_percent": 5.2,
  "memory": {
    "total": 33554432,
    "available": 23199744,
    "used": 10354688,
    "percent": 30.8
  },
  "disk": {
    "total": 107374182400,
    "used": 25369804800,
    "free": 819,
    "percent": 23.6
  }
}
```
