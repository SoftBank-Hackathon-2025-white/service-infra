const express = require("express");
const AWS = require("aws-sdk");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");
const os = require("os");

const app = express();
const port = 3000;

const CODE_BUCKET = process.env.CODE_BUCKET;
const LOG_BUCKET = process.env.LOG_BUCKET;
const AWS_REGION = process.env.AWS_REGION;

AWS.config.update({ region: AWS_REGION });
const s3 = new AWS.S3();

/**
 * 공통 JSON 응답 헬퍼
 */
function sendJson(res, statusCode, data) {
  res.status(statusCode).json(data);
}

/**
 * 헬스 체크
 */
app.get("/health", (req, res) => {
  console.log(`💚 [HEALTH] ${new Date().toISOString()} - Node Runner is healthy`);
  res.send("Node Runner is healthy");
});

/**
 * 시스템 CPU 사용률 계산 (약간의 샘플링)
 */
function getSystemCpuPercent() {
  return new Promise((resolve) => {
    const startMeasures = os.cpus();

    setTimeout(() => {
      const endMeasures = os.cpus();
      let idleDiff = 0;
      let totalDiff = 0;

      for (let i = 0; i < startMeasures.length; i++) {
        const start = startMeasures[i].times;
        const end = endMeasures[i].times;

        const idle = end.idle - start.idle;
        const totalStart = start.user + start.nice + start.sys + start.irq + start.idle;
        const totalEnd = end.user + end.nice + end.sys + end.irq + end.idle;
        const total = totalEnd - totalStart;

        idleDiff += idle;
        totalDiff += total;
      }

      const cpuPercent = totalDiff > 0 ? (1 - idleDiff / totalDiff) * 100 : 0;
      resolve(Number(cpuPercent.toFixed(2)));
    }, 100); // 100ms 샘플링
  });
}

/**
 * /node/status
 * - Python Runner 의 /python/status 와 최대한 동일한 구조
 */
app.get("/node/status", async (req, res) => {
  try {
    const vmTotalMb = os.totalmem() / (1024 * 1024);
    const vmFreeMb = os.freemem() / (1024 * 1024);
    const vmUsedMb = vmTotalMb - vmFreeMb;

    const cpuPercentSystem = await getSystemCpuPercent();

    // 프로세스 기준 리소스
    const procMem = process.memoryUsage();
    const procMemMb = procMem.rss / (1024 * 1024);

    const cpuUsage = process.cpuUsage();
    const userMs = cpuUsage.user / 1000; // micro → ms
    const sysMs = cpuUsage.system / 1000;
    const uptimeMs = process.uptime() * 1000;
    const procCpuPercent =
      uptimeMs > 0 ? Number((((userMs + sysMs) / uptimeMs) * 100).toFixed(2)) : 0;

    const data = {
      timestamp: new Date().toISOString(),
      system: {
        cpu_percent: cpuPercentSystem,
        memory_total_mb: Number(vmTotalMb.toFixed(2)),
        memory_used_mb: Number(vmUsedMb.toFixed(2)),
        memory_percent: Number(((vmUsedMb / vmTotalMb) * 100).toFixed(2)),
      },
      process: {
        cpu_percent: procCpuPercent,
        memory_mb: Number(procMemMb.toFixed(2)),
      },
    };

    sendJson(res, 200, data);
  } catch (e) {
    console.error("❌ /node/status error:", e);
    sendJson(res, 500, { error: e.message });
  }
});

/**
 * S3에서 JS 코드 다운로드
 */
async function downloadCode(bucket, key) {
  const localPath = `/tmp/${path.basename(key)}`;
  const file = fs.createWriteStream(localPath);

  return new Promise((resolve, reject) => {
    s3.getObject({ Bucket: bucket, Key: key })
      .createReadStream()
      .pipe(file)
      .on("close", () => resolve(localPath))
      .on("error", reject);
  });
}

/**
 * S3에 JSON 로그 업로드
 *  - Python Runner 의 upload_log_json 과 동일한 역할
 */
async function uploadLogJson(data) {
  const logKey = `logs/${Date.now()}-${Math.random().toString(36).substr(2, 9)}.json`;

  const params = {
    Bucket: LOG_BUCKET,
    Key: logKey,
    Body: JSON.stringify(data, null, 2),
    ContentType: "application/json",
  };

  await s3.putObject(params).promise();
  return logKey;
}

/**
 * /node/run
 *  - 코드 실행 + 실행시간/CPU/MEM 측정
 *  - S3 에 JSON 로그 저장
 *  - Python Runner 의 /python/run 과 응답 구조 동일
 */
app.get("/node/run", async (req, res) => {
  const codeKey = req.query.code_key;
  if (!codeKey) {
    return sendJson(res, 400, { error: "Missing code_key parameter" });
  }

  try {
    const localPath = await downloadCode(CODE_BUCKET, codeKey);
    const command = `node ${localPath}`;

    const start = Date.now();
    const cpuStart = process.cpuUsage();

    exec(command, async (error, stdout, stderr) => {
      const end = Date.now();
      const cpuEnd = process.cpuUsage(cpuStart);

      const execTimeMs = end - start;

      // cpuUsage: microseconds
      const totalCpuMs = (cpuEnd.user + cpuEnd.system) / 1000;
      const cpuPercent =
        execTimeMs > 0 ? Number(((totalCpuMs / execTimeMs) * 100).toFixed(2)) : 0;

      const memoryMb = process.memoryUsage().rss / 1024 / 1024;

      // Python Runner 의 response_data 와 동일한 구조
      const logData = {
        stdout,
        stderr,
        execution_time_ms: execTimeMs,
        cpu_percent: cpuPercent,
        memory_mb: Number(memoryMb.toFixed(2)),
        code_key: codeKey,
      };

      // S3 에 JSON 로그 저장 (log_key 없이)
      const logKey = await uploadLogJson(logData);

      // 클라이언트 응답에는 log_key 추가
      const response = {
        ...logData,
        log_key: logKey,
      };

      console.log(
        `📝 [NODE RUN DONE] code_key=${codeKey}, time=${execTimeMs}ms, cpu=${cpuPercent}%, mem=${response.memory_mb}MB`
      );

      sendJson(res, 200, response);
    });
  } catch (err) {
    console.error("❌ /node/run error:", err);
    sendJson(res, 500, { error: err.message });
  }
});

app.listen(port, () => {
  console.log(`🚀 Node Runner running on port ${port}`);
});