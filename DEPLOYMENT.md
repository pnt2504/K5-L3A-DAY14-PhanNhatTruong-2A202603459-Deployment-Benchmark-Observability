# Day 14 · Deployment

## Public URL

[https://day14-ai-agent-b3mi.onrender.com](https://day14-ai-agent-b3mi.onrender.com)

## Nền tảng

**Render Free** · Singapore · Web service `day14-ai-agent` · Key Value `day14-agent-cache`.

| Mục | Giá trị |
| --- | --- |
| Nhánh deploy | `codex/day14-render` |
| Commit | `2f8865f5bece092767fe8c4f3fe6e72abfc5b6b6` |
| Thư mục gốc | `06-lab-complete/` |
| Runtime | Docker |
| Health check | `GET /health` |
| Trạng thái | `Live` |

[Render Dashboard](https://dashboard.render.com/web/srv-dc3bh7m7bikc73cnf530) · [Deploy đã xác minh](https://dashboard.render.com/web/srv-dc3bh7m7bikc73cnf530/deploys/dep-dc3bh7u7bikc73cnf5qg)

## Biến môi trường

| Biến | Cấu hình |
| --- | --- |
| `PORT` | `10000` |
| `ENVIRONMENT` | `production` |
| `REDIS_URL` | URL nội bộ của Render Key Value cùng vùng |
| `AGENT_API_KEY` | Secret trong Environment của web service |

## Kết quả xác minh

Bốn yêu cầu HTTPS được kiểm tra lúc **2026-11-25 17:31:22 +07:00**.

| Endpoint | Trường hợp | HTTP thực tế |
| --- | --- | --- |
| `GET /health` | Liveness | `200` |
| `GET /ready` | Redis readiness | `200` |
| `POST /ask` | Thiếu API key | `401` |
| `POST /ask` | Có API key | `200` |

Phản hồi xác thực thành công cho `POST /ask`.

```json
{
  "question": "Hello",
  "answer": "Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."
}
```

### Chạy lại kiểm tra từ PowerShell

Nạp API key của service vào biến môi trường `AGENT_API_KEY` trong terminal. Các lệnh dưới đây chỉ in mã HTTP.

```powershell
$base = 'https://day14-ai-agent-b3mi.onrender.com'
curl.exe -sS -o NUL -w '%{http_code}\n' "$base/health"
curl.exe -sS -o NUL -w '%{http_code}\n' "$base/ready"
'{"question":"Hello"}' | curl.exe -sS -o NUL -w '%{http_code}\n' "$base/ask" -H 'Content-Type: application/json' --data-binary '@-'
'{"question":"Hello"}' | curl.exe -sS -o NUL -w '%{http_code}\n' "$base/ask" -H 'Content-Type: application/json' -H "X-API-Key: $env:AGENT_API_KEY" --data-binary '@-'
```

## Ảnh bằng chứng

- [Render Dashboard hiển thị bản deploy Live](screenshots/dashboard.png)
- [Service public trả HTTP 200 cho GET /health](screenshots/running.png)
- [Bốn kết quả HTTP qua URL public](screenshots/test.png)
