from fastapi import FastAPI
import psutil
import time

app = FastAPI()

def get_metrics():
    cpu_percent = psutil.cpu_percent(interval=0.2)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage("/")

    metrics = {
        "timestamp": time.time(),
        "cpu_percent": cpu_percent,
        "memory": {
            "total": memory_info.total,
            "available": memory_info.available,
            "used": memory_info.used,
            "percent": memory_info.percent
        },
        "disk": {
            "total": disk_info.total,
            "used": disk_info.used,
            "free": disk_info.free,
            "percent": disk_info.percent
        }
    }
    return metrics

@app.get("/metrics")
def read_metrics():
    return get_metrics()
