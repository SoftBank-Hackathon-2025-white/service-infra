const { exec } = require("child_process");
const fs = require("fs");
const AWS = require("aws-sdk");
const path = require("path");
const s3 = new AWS.S3();
const { v4: uuidv4 } = require("uuid");

/**
 * S3에서 파일 다운로드 + 원본 파일명 그대로 저장
 */
async function download(bucket, key) {
  // key에서 파일명 추출 (예: "users/123/code.js" → "code.js")
  const originalFilename = path.basename(key);

  // /runner/<원본파일명>
  const filePath = `/runner/${originalFilename}`;

  const data = await s3.getObject({ Bucket: bucket, Key: key }).promise();

  fs.writeFileSync(filePath, data.Body.toString());

  return filePath;
}

/**
 * Node.js 코드 실행
 */
function execute(filePath) {
  return new Promise(resolve => {
    exec(`node ${filePath}`, { timeout: 15000 }, (err, stdout, stderr) => {
      resolve({ stdout, stderr });
    });
  });
}

/**
 * 로그 업로드
 */
async function uploadLog(bucket, content) {
  const key = `logs/${uuidv4()}.txt`;

  await s3.putObject({
    Bucket: bucket,
    Key: key,
    Body: content
  }).promise();
}

/**
 * 메인 처리 흐름
 */
(async () => {
  const bucket = process.env.CODE_BUCKET;
  const key = process.env.CODE_KEY;
  const logBucket = process.env.LOG_BUCKET;

  const file = await download(bucket, key);
  const { stdout, stderr } = await execute(file);

  const logContent = `STDOUT:\n${stdout}\nSTDERR:\n${stderr}`;

  await uploadLog(logBucket, logContent);
})();