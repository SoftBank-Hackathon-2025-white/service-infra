const express = require("express");
const AWS = require("aws-sdk");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

const app = express();
const port = 3000;

// 환경변수
const CODE_BUCKET = process.env.CODE_BUCKET;
const LOG_BUCKET = process.env.LOG_BUCKET;
const AWS_REGION = process.env.AWS_REGION;

AWS.config.update({ region: AWS_REGION });
const s3 = new AWS.S3();

// ------------------------------
// 헬스체크
// ------------------------------
app.get("/health", (req, res) => {
  console.log(`💚 [HEALTH] ${new Date().toISOString()}`);
  res.send("Node Runner is healthy");
});

// ------------------------------
// S3에서 JS코드 다운로드
// ------------------------------
async function downloadCode(bucket, key) {
  const localPath = `/tmp/${path.basename(key)}`;
  const file = fs.createWriteStream(localPath);

  const params = { Bucket: bucket, Key: key };
  return new Promise((resolve, reject) => {
    s3.getObject(params)
      .createReadStream()
      .pipe(file)
      .on("close", () => resolve(localPath))
      .on("error", reject);
  });
}

// ------------------------------
// S3 로그 업로드
// ------------------------------
async function uploadLog(key, content) {
  const params = {
    Bucket: LOG_BUCKET,
    Key: key,
    Body: content,
    ContentType: "text/plain",
  };
  await s3.putObject(params).promise();
}

// ------------------------------
// 실행 핸들러
// ------------------------------
app.get("/node/run", async (req, res) => {
  const codeKey = req.query.code_key;
  if (!codeKey) {
    return res.status(400).json({ error: "Missing code_key" });
  }

  try {
    const localPath = await downloadCode(CODE_BUCKET, codeKey);
    const command = `node ${localPath}`;

    // 실행 시작 CPU/Memory 기준점
    const start = Date.now();
    const cpuStart = process.cpuUsage();
    const memStart = process.memoryUsage().rss;

    exec(command, async (error, stdout, stderr) => {
      // 실행 끝
      const end = Date.now();
      const cpuEnd = process.cpuUsage(cpuStart);
      const memEnd = process.memoryUsage().rss;

      const execTimeMs = end - start;
      const cpuPercent = ((cpuEnd.user + cpuEnd.system) / 1000).toFixed(2);
      const memoryMb = (memEnd / 1024 / 1024).toFixed(2);

      const logId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const logKey = `logs/${logId}.txt`;

      await uploadLog(
        logKey,
        `STDOUT:\n${stdout}\n\nSTDERR:\n${stderr}\n\n` +
        `execution_time_ms: ${execTimeMs}\n` +
        `cpu_percent: ${cpuPercent}\n` +
        `memory_mb: ${memoryMb}\n` +
        `code_key: ${codeKey}\n`
      );

      res.json({
        stdout,
        stderr,
        log_key: logKey,
        execution_time_ms: execTimeMs,
        cpu_percent: cpuPercent,
        memory_mb: memoryMb,
        code_key: codeKey,
      });
    });
  } catch (err) {
    console.error("❌ Error executing run:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(port, () => {
  console.log(`🚀 Node Runner listening on port ${port}`);
});