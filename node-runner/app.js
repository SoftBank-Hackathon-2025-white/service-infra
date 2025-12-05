const express = require("express");
const AWS = require("aws-sdk");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

const app = express();
const port = 3000;

const CODE_BUCKET = process.env.CODE_BUCKET;
const LOG_BUCKET = process.env.LOG_BUCKET;
const AWS_REGION = process.env.AWS_REGION;

AWS.config.update({ region: AWS_REGION });
const s3 = new AWS.S3();

app.get("/health", (req, res) => {
  console.log(`💚 [HEALTH] ${new Date().toISOString()}`);
  res.send("Node Runner is healthy");
});

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

async function uploadLogJson(key, data) {
  const params = {
    Bucket: LOG_BUCKET,
    Key: key,
    Body: JSON.stringify(data, null, 2),
    ContentType: "application/json",
  };
  await s3.putObject(params).promise();
}

app.get("/node/run", async (req, res) => {
  const codeKey = req.query.code_key;
  if (!codeKey) return res.status(400).json({ error: "Missing code_key" });

  try {
    const localPath = await downloadCode(CODE_BUCKET, codeKey);
    const command = `node ${localPath}`;

    const start = Date.now();
    const cpuStart = process.cpuUsage();

    exec(command, async (error, stdout, stderr) => {
      const end = Date.now();
      const cpuEnd = process.cpuUsage(cpuStart);

      const execTimeMs = end - start;
      const cpuPercent = ((cpuEnd.user + cpuEnd.system) / 1000).toFixed(2);
      const memoryMb = (process.memoryUsage().rss / 1024 / 1024).toFixed(2);

      const logKey = `logs/${Date.now()}-${Math.random()
        .toString(36)
        .substr(2, 9)}.json`;

      const logData = {
        stdout,
        stderr,
        execution_time_ms: execTimeMs,
        cpu_percent: cpuPercent,
        memory_mb: memoryMb,
        code_key: codeKey,
      };

      await uploadLogJson(logKey, logData);

      logData["log_key"] = logKey;
      res.json(logData);
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(port, () => {
  console.log(`🚀 Node Runner listening on port ${port}`);
});