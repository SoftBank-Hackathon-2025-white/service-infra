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

// --------------------------------
// 🔥 헬스체크 (로그 출력 추가)
// --------------------------------
app.get("/health", (req, res) => {
  const now = new Date().toISOString();
  console.log(`💚 [HEALTH CHECK] ${now} - Node Runner is healthy`);

  res.send("Node Runner is healthy");
});

// S3에서 JS 코드 다운로드
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

// S3에 로그 저장
async function uploadLog(key, content) {
  const params = {
    Bucket: LOG_BUCKET,
    Key: key,
    Body: content,
    ContentType: "text/plain",
  };
  await s3.putObject(params).promise();
}

// 실행 핸들러
app.get("/run", async (req, res) => {
  const codeKey = req.query.code_key;
  if (!codeKey) {
    return res.status(400).json({ error: "Missing code_key" });
  }

  try {
    const localPath = await downloadCode(CODE_BUCKET, codeKey);
    const command = `node ${localPath}`;

    exec(command, async (error, stdout, stderr) => {
      const logId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const logKey = `logs/${logId}.txt`;

      const logContent = `STDOUT:\n${stdout}\n\nSTDERR:\n${stderr}`;
      await uploadLog(logKey, logContent);

      console.log(`📝 [RUN DONE] stdout: ${stdout.trim()} | stderr: ${stderr.trim()}`);

      res.json({
        stdout,
        stderr,
        log_key: logKey,
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