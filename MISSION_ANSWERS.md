# Day 14 Lab — Mission Answers

## Part 1 · Localhost vs Production

### 1.1 · Anti-pattern trong bản develop

1. `app.py` dòng 17–18 đặt API key và thông tin đăng nhập database ngay trong mã. Nếu đây là giá trị thật, chúng có thể bị lộ qua repo, image hoặc bản sao mã nguồn.
2. Dòng 21–22 cố định `DEBUG` và `MAX_TOKENS` trong mã. Muốn đổi cấu hình giữa dev và production phải sửa source.
3. Dòng 33–38 dùng `print()` để ghi debug và in cả giá trị key, câu hỏi và phản hồi. Log khó truy vấn theo trường và có thể làm lộ dữ liệu.
4. App chỉ có `/` và `/ask`. Thiếu probe `/health` và `/ready` khiến nền tảng khó phân biệt process còn sống với instance đã sẵn sàng nhận traffic.
5. Dòng 51–52 bind vào `localhost` và cố định cổng `8000`. Trong container, bind loopback ngăn proxy bên ngoài container kết nối. Cổng cố định cũng bỏ qua biến `PORT` mà môi trường deploy cấp.
6. Dòng 53 luôn bật auto-reload. Bản develop cũng thiếu lifespan để đánh dấu trạng thái startup và dọn tài nguyên khi shutdown.

### 1.2 · Chạy bản develop

Bản develop nhận `question` qua query string. Ví dụ gọi khi chạy app ở cổng 8000:

```powershell
curl.exe -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"
```

Kết quả chạy bản develop trên loopback với cổng thử nghiệm riêng.

```text
HTTP 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

`GET /health` trả `404`. Gửi `question` chỉ trong JSON body trả `422` vì handler đang yêu cầu query parameter.

### 1.3 · So sánh develop và production

| Hạng mục | Develop | Production | Vì sao quan trọng |
| --- | --- | --- | --- |
| Cấu hình và secret | Key, thông tin database và tham số đặt cố định trong mã. | `config.py` đọc env. Môi trường đặt là `production` yêu cầu có `AGENT_API_KEY` khi khởi tạo cấu hình. | Dùng cùng một mã ở nhiều môi trường và quản lý secret tại nơi triển khai. |
| Bind, cổng và debug | `localhost:8000`, luôn bật reload. | `HOST` mặc định `0.0.0.0`, `PORT` đọc từ env và debug mặc định tắt. | Proxy truy cập được container, cổng khớp với nền tảng và tránh reload ngoài ý muốn. |
| Health và readiness | Chưa có probe. | `/health` trả liveness, `/ready` dựa vào cờ readiness từ lifespan. | Nền tảng có tín hiệu riêng để theo dõi process và quyết định gửi traffic. |
| Log | Ghi bằng `print()`, gồm key và nội dung yêu cầu. | Dùng `logging` với format JSON và ghi sự kiện cùng độ dài câu hỏi, phản hồi. | Log có trường để lọc, giảm dữ liệu nhạy cảm lưu trong log. |
| Shutdown | Không có lifecycle dọn tài nguyên của ứng dụng. | Lifespan đặt `is_ready = False` khi shutdown và có bước cleanup. Uvicorn xử lý vòng đời server. | Có điểm để hoàn thành request và đóng tài nguyên khi thay instance. |

Đối chiếu mã cụ thể ở `01-localhost-vs-production/develop/app.py` dòng 52 với `production/app.py` dòng 197. Bản develop gắn cứng `8000`, bản production dùng `settings.port` lấy từ `PORT`. Bài thử bản production xác nhận `/health`, `/ready` và `POST /ask` gửi JSON đều trả `200`.

## Part 2 · Docker Containerization

### 2.1 · Dockerfile cơ bản

1. **Base image** là `python:3.11`. Image này cung cấp trình thông dịch Python 3.11 và môi trường hệ thống để cài dependencies.
2. **Working directory** là `/app`, được đặt bằng `WORKDIR /app`. Các lệnh sau đó chạy trong thư mục này. Chẳng hạn, đích `.` trong lệnh `COPY` trỏ tới `/app`.
3. **Copy `requirements.txt` trước mã nguồn** để Docker có thể dùng lại layer `RUN pip install` khi chỉ sửa `app.py`. Nếu `requirements.txt` thay đổi, Docker sẽ chạy lại bước cài dependencies.
4. **`ENTRYPOINT`** đặt chương trình chính của container. **`CMD`** đặt lệnh mặc định khi Dockerfile dùng riêng `CMD`, hoặc đối số mặc định khi kết hợp với `ENTRYPOINT`. Đối số sau tên image trong `docker run` có thể ghi đè `CMD`. Dockerfile develop dùng `CMD ["python", "app.py"]`.

### 2.2 · Build và chạy bản develop

Build context là gốc repo vì Dockerfile lấy `02-docker/develop/app.py` và `utils/mock_llm.py` theo đường dẫn từ gốc. Container lắng nghe ở cổng `8000`, được ánh xạ sang cổng `18000` trên máy. Route `/ask` của bản develop nhận `question` qua query string.

```powershell
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run --rm -d --name k5-day14-docker-dev -p 127.0.0.1:18000:8000 my-agent:develop
curl.exe -i http://127.0.0.1:18000/health
curl.exe -i -X POST "http://127.0.0.1:18000/ask?question=What%20is%20Docker%3F"
```

Trích output kiểm tra, theo thứ tự `/health` và `/ask`.

```text
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":415.9,"container":true}

HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### 2.3 · Multi-stage build

- Stage `builder` dùng `python:3.11-slim`, cài `gcc`, `libpq-dev` và cài các package Python vào `/root/.local`.
- Stage `runtime` dùng một base `python:3.11-slim` riêng, chép các package đã cài và mã ứng dụng. Nó chạy Uvicorn dưới user `appuser`. `gcc` và `libpq-dev` nằm ở builder, nên image cuối nhỏ hơn.

```powershell
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

| Image | `SIZE` từ `docker images` |
| --- | ---: |
| `my-agent:develop` | 1.67 GB |
| `my-agent:advanced` | 240 MB |

Quy đổi theo đơn vị thập phân, `1.67 GB ≈ 1 670 MB`. Image advanced giảm khoảng **85,6%**, tính bằng `(1 670 − 240) / 1 670 × 100` từ hai số hiển thị đã làm tròn.

### 2.4 · Docker Compose và Nginx

```text
Luồng HTTP
Máy chạy lab :18080 → Nginx :80 → Agent :8000 → Mock LLM

Điều kiện khởi động
Agent ── depends_on (service_healthy) ──→ Redis :6379
      └─ depends_on (service_healthy) ──→ Qdrant :6333
```

Compose khởi động bốn service `nginx`, `agent`, `redis` và `qdrant`. Chúng dùng chung mạng `internal`. Nginx chuyển HTTP đến `agent:8000` bằng tên service. Redis và Qdrant phải healthy trước khi agent khởi động. Trong ví dụ này, handler `/ask` gọi mock LLM trực tiếp.

Kết quả kiểm tra cho thấy cả bốn container đang chạy. Agent, Redis và Qdrant đều báo `healthy`. Nginx được kiểm tra qua cổng `18080` trên máy.

```powershell
curl.exe -i http://127.0.0.1:18080/health
'{"question":"Explain microservices"}' |
    curl.exe -i http://127.0.0.1:18080/ask -H "Content-Type: application/json" --data-binary '@-'
```

Trích output kiểm tra qua Nginx, theo thứ tự `/health` và `/ask`.

```text
HTTP/1.1 200 OK
Server: nginx
{"status":"ok","uptime_seconds":185.8,"version":"2.0.0","timestamp":"2026-11-25T09:17:34.374199"}

HTTP/1.1 200 OK
Server: nginx
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

## Part 3 · Cloud Deployment

### 3.1 · Railway

Đã thử Railway trên gói dùng thử. Railway từ chối tạo service agent vì workspace bị giới hạn. Deployment Redis trong project `day14-agent` báo `FAILED`.

### 3.2 · Render Free và so sánh với Railway

Đã deploy agent Part 6 lên **Render Free**. Web service và Render Key Value chạy cùng vùng Singapore. Render build Dockerfile từ thư mục `06-lab-complete/` trên nhánh `codex/day14-render` tại commit `2f8865f5bece092767fe8c4f3fe6e72abfc5b6b6`.

Kiểm tra qua URL public lúc 2026-11-25 17:31:22 +07:00 xác nhận `GET /health` và `GET /ready` cùng trả `200`. `POST /ask` thiếu API key trả `401`. Với API key đúng, `POST /ask` trả `200` và có nội dung `answer`. [URL dịch vụ](https://day14-ai-agent-b3mi.onrender.com) · [Kết quả và ảnh bằng chứng](DEPLOYMENT.md)

| Hạng mục | Railway của Part 6 | Blueprint Render mẫu |
| --- | --- | --- |
| Khai báo build | `railway.toml` đặt `[build] builder = "DOCKERFILE"`. Dockerfile cài dependencies và chạy Uvicorn theo `PORT`. | `render.yaml` mẫu khai báo `type: web`, `runtime: python`, `buildCommand` và `startCommand`. Khi dùng Dockerfile của Part 6 trên Render, dùng `runtime: docker`. |
| Health check | `[deploy] healthcheckPath = "/health"`. | `healthCheckPath: /health` nằm trong khai báo web service. |
| Redis | Tạo Redis trong cùng project, rồi tham chiếu `REDIS_URL` nội bộ từ service agent. | Blueprint có thể khai báo web service và Key Value trong cùng file. Mẫu dùng alias `type: redis`, tên loại hiện dùng là `type: keyvalue`. |
| Secret | Đặt `AGENT_API_KEY` trong biến môi trường của service và tham chiếu biến Redis. | `envVars` có thể dùng `generateValue: true` để sinh key, hoặc `sync: false` để người triển khai nhập. |

Railway đặt cấu hình build và health check ở cấp service. Render Blueprint có thể mô tả cả web service, kho Key Value và cách cấp biến môi trường trong một file. [Tài liệu Railway Redis](https://docs.railway.com/databases/redis) · [Tài liệu Render Blueprint](https://render.com/docs/blueprint-spec)

### 3.3 · Pipeline Cloud Run

1. `cloudbuild.yaml` chạy bước test bằng Python, cài dependencies và gọi `pytest`.
2. Bước build dùng Docker để tạo image với tag `$COMMIT_SHA` và `latest`, rồi bước push đưa cả hai tag lên registry được cấu hình trong mẫu.
3. Bước deploy gọi `gcloud run deploy` với image gắn `$COMMIT_SHA` ở `asia-southeast1`, kèm cấu hình tài nguyên, scale và biến môi trường.
4. `service.yaml` mô tả service Cloud Run, gồm cổng `8000`, concurrency, giới hạn số instance, secret từ Secret Manager và hai probe `/health`, `/ready`.

## Part 4 · API Security

### 4.1 · API key authentication

`verify_api_key()` trong `04-api-gateway/develop/app.py` đọc header `X-API-Key` qua `APIKeyHeader`. `POST /ask` gọi hàm này qua `Depends` trước khi xử lý câu hỏi. Thiếu key trả `401`, sai key trả `403`, key đúng và body hợp lệ trả `200`.

Để xoay key, tạo key mới, cập nhật biến môi trường `AGENT_API_KEY` của service, rồi khởi động lại vì app đọc biến khi nạp module. Cập nhật cấu hình client để các lần gọi sau gửi key mới.

Trích output `curl -i` khi lần lượt gọi `POST /ask` với key thiếu, sai và đúng.

```text
HTTP/1.1 401 Unauthorized

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

HTTP/1.1 403 Forbidden

{"detail":"Invalid API key."}

HTTP/1.1 200 OK

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### 4.2 · JWT authentication

`POST /auth/token` xác thực tài khoản mẫu `student` và phát JWT được ký bằng `HS256`. Token chứa `sub` (tên người dùng), `role`, `iat` và `exp`, có hiệu lực 60 phút. Client gửi token trong `Authorization: Bearer <token>`. `verify_token()` xác minh chữ ký và hạn dùng rồi lấy tên người dùng và role để xử lý request.

Trích output `curl -i` khi gọi `/ask` thiếu Bearer token, đăng nhập và gọi `/ask` với Bearer token vừa nhận. Phản hồi `200` cuối là request số 1 trong bài 4.3.

```text
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

HTTP/1.1 200 OK

{"access_token":"<đã che>","token_type":"bearer","expires_in_minutes":60}

HTTP/1.1 200 OK

{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":0.000019}}
```

Trong phản hồi của mã mẫu, trường `usage.budget_remaining_usd` lấy giá trị `total_cost_usd`. Số dư ngân sách được tính riêng trong `GET /me/usage`.

### 4.3 · Rate limiting

Mã mẫu dùng **sliding window** trên danh sách timestamp của từng user. Mỗi lần gọi, limiter bỏ các timestamp cũ hơn 60 giây, đếm các request còn trong cửa sổ và thêm timestamp nếu còn quota.

Quota của tài khoản thường là **10 request trong 60 giây**. Role `admin` đã xác minh từ JWT được chọn limiter riêng **100 request trong 60 giây**. Nếu chính sách yêu cầu miễn quota cho admin, chỉ gọi limiter trong nhánh dành cho role thường sau khi xác minh token.

Trong một vòng lặp với 20 lần gọi bằng JWT của `student`, lần 1–10 trả `200` và lần 11–20 trả `429`. Sau lần 10, `requests_remaining = 0`. Trích output `curl -i` ở lần 11.

```text
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### 4.4 · Cost guard

`cost_guard.py` trong ví dụ đang lưu usage theo ngày trong RAM. `check_budget()` kiểm tra trước khi gọi LLM và `record_usage()` ghi số token cùng chi phí sau khi gọi. Khi chạm hạn mức của user, guard trả lỗi `402 Payment Required`. Khi chạm hạn mức tổng, guard trả `503`.

Kiểm tra riêng lớp `CostGuard` với ngân sách ngày thử nghiệm `$0.0006`. Lần kiểm tra đầu được chấp nhận. Sau khi ghi nhận 1.000 output token, lần kiểm tra tiếp theo phát sinh HTTPException `402` với thông báo `Daily budget exceeded`.

Để áp dụng yêu cầu **10 USD mỗi user mỗi tháng** bằng Redis:

1. Dùng khóa `budget:<user_id>:<YYYY-MM>` theo UTC. Đặt thời điểm hết hạn vào đầu tháng tiếp theo. Lưu chi phí bằng đơn vị nguyên, chẳng hạn micro-USD.
2. Trước khi gọi LLM, chạy một thao tác nguyên tử trong Redis, chẳng hạn Lua. Nếu `spent + estimated_cost > budget`, từ chối với `402`. Nếu còn ngân sách, cộng khoản dự trù ngay trong cùng thao tác để các request đồng thời dùng chung một hạn mức.
3. Khi LLM trả kết quả, tính chi phí từ token thực tế và đối soát khoản dự trù. Nếu cuộc gọi thất bại trước khi phát sinh chi phí, hoàn khoản dự trù. Dùng mã request để mỗi khoản chỉ được đối soát một lần.

Rate limit kiểm soát số lần gọi trong một cửa sổ thời gian. Cost guard kiểm soát số tiền đã dùng, kể cả khi một số ít request tiêu thụ nhiều token.

## Part 5 · Scaling & Reliability

### 5.1 · Liveness và readiness

`GET /health` dùng để kiểm tra process còn phục vụ được HTTP. Probe liveness thất bại có thể kích hoạt khởi động lại. `GET /ready` cho biết instance có thể nhận traffic mới. Khi dependency bắt buộc như Redis đang lỗi, readiness trả `503` để bộ điều phối rút instance khỏi danh sách nhận traffic.

Ở bản `develop`, lifespan đặt `_is_ready` thành `True` sau startup. Kiểm tra HTTP sau startup cho thấy `/health` trả `200` với `status=ok` và `/ready` trả `200` với `ready=true`.

Ở bản `production`, agent đã kết nối Redis lúc startup. Sau khi dừng Redis, truy vấn trực tiếp agent từ trong container cho thấy:

```text
GET /health -> 200, status=degraded, redis_connected=false
GET /ready  -> 503, detail="Redis not available"
```

Qua Nginx, `/health` cũng trả `200` với trạng thái `degraded`. Khi Redis ngừng chạy và một replica vẫn đang dừng, `/ready` qua Nginx trả `502`. Log ghi nhận các agent còn chạy trả `503`, rồi Nginx thử tiếp upstream và gặp địa chỉ của replica đã dừng.

### 5.2 · Graceful shutdown

Uvicorn nhận `SIGTERM`, ngừng nhận kết nối mới và cho request đang xử lý hoàn tất trong thời gian graceful shutdown. Lifespan cập nhật cờ readiness và thực hiện bước dọn dẹp trước khi tiến trình thoát.

Chạy bản develop trong container Linux và gửi `SIGTERM` sau **0,55 giây**, khi `POST /ask?question=Long%20task` đang chờ phản hồi. Request trả **HTTP 200 sau 3,03 giây** tính từ lúc gửi request. Tiến trình thoát với mã **0**.

Trích log Uvicorn và ứng dụng.

```text
INFO:     Shutting down
INFO:     127.0.0.1:39266 - "POST /ask?question=Long%20task HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
```

### 5.3 · Stateless session

Mỗi replica có RAM riêng. Khi request thứ nhất lưu lịch sử vào RAM của A, replica B sẽ thiếu lịch sử nếu nhận request tiếp theo của cùng session. Bản production lưu lịch sử trong Redis theo khóa `session:<session_id>`. Client gửi lại cùng `session_id` để bất kỳ replica nào cũng đọc và ghi cùng dữ liệu. Mã mẫu giữ tối đa 20 tin nhắn và đặt lại TTL 3.600 giây mỗi lần ghi. Lệnh Redis `TTL` trả `3600` ngay sau bài kiểm tra.

### 5.4 · Load balancing qua Nginx

Trong `05-scaling-reliability/production/`, chạy:

```powershell
docker compose -p k5-day14-scaling up -d --build --scale agent=3 --wait --wait-timeout 150
docker compose -p k5-day14-scaling ps
```

Compose báo cả ba agent và Redis healthy. Client gọi `POST /chat` ở cổng `8080`. Nginx chuyển tiếp request đến các agent trên cổng `8000`. Trong lần chạy, trường `served_by` đổi giữa cả ba instance, đúng với thứ tự round-robin quan sát được.

### 5.5 · Kiểm tra session qua ba replica

Chạy `python -X utf8 -B test_stateless.py` với stack đang hoạt động. Script gửi năm câu hỏi trong một session rồi đọc history.

```text
Session ID: cb938fb2-f0fc-4f3c-b69b-a643223f1c1f
Request 1: [instance-915fff]
Request 2: [instance-97ca91]
Request 3: [instance-6ecec7]
Request 4: [instance-915fff]
Request 5: [instance-97ca91]
Total requests: 5
Instances used: {'instance-97ca91', 'instance-6ecec7', 'instance-915fff'}
--- Conversation History ---
Total messages: 10
```

Năm lượt chat tạo năm tin nhắn user và năm tin nhắn assistant. Để kiểm tra thêm, dừng container `k5-day14-scaling-agent-3` (`instance-915fff`) từng phục vụ session này, rồi gửi câu hỏi mới với cùng `session_id` qua Nginx. Replica `instance-97ca91` trả **HTTP 200**. History cũng trả **HTTP 200**, giữ nguyên 10 tin nhắn cũ và tăng lên 12 tin nhắn.

## Part 6 · Production-ready Agent

Agent chạy trong `06-lab-complete/` với hai worker Uvicorn và một Redis dùng chung. `/health` trả `200` khi tiến trình đang chạy. `/ready` trả `503` khi Redis mất kết nối. `/ask` xác thực `X-API-Key`, rồi kiểm tra rate limit và ngân sách trước khi gọi mock LLM.

- Rate limit dùng sliding window 60 giây bằng sorted set trong Redis. Thao tác kiểm tra và ghi lượt gọi chạy nguyên tử để hai worker dùng cùng một quota. Quota mặc định là 10 request/phút.
- Cost guard mặc định dùng ngân sách toàn service 10 USD/tháng theo UTC. Có thể đặt thêm ngân sách ngày. Redis giữ trước chi phí ước tính và đối soát theo phản hồi mock, để nhiều request đồng thời kiểm tra cùng một ngân sách.
- Ứng dụng ghi log JSON và dùng lifecycle của FastAPI cùng graceful shutdown của Uvicorn. Cấu hình Railway dùng Dockerfile và health check `/health`.

### Kết quả bộ chấm

Chạy `python check_production_ready.py --redis-url redis://127.0.0.1:16386/0` trong container Linux có Docker. Redis dùng cho lần chấm là một container tạm trên localhost. Kết quả dưới đây là từ lần chấm đầy đủ.

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Image đo được **63 MB** theo script. Khi gửi `SIGTERM` lúc có request, request vẫn trả `200` và tiến trình thoát mã `0`. Bài kiểm tra `docker stop` trả mã `0` sau **0,7 giây**.

### Kiểm tra thêm với Docker Compose

- Gửi 12 request đồng thời ở quota 3 request/phút. Có 3 phản hồi `200` và 9 phản hồi `429`.
- Gửi 10 request đồng thời với ngân sách thử nghiệm đủ cho một khoản dự trù. Có 1 phản hồi `200` và 9 phản hồi `402`. Cả bộ đếm ngày và tháng đều ghi 9.450 nano-USD sau khi đối soát.

## AI log

- **Yêu cầu.** Hỏi Codex cách làm và kiểm tra Part 2, sau đó nhờ soạn mục trả lời.
- **Hỗ trợ.** Codex đối chiếu Dockerfile và Compose, giải thích cache và multi-stage, rồi soạn câu trả lời dựa trên kích thước và phản hồi API thực tế.
- **Kiểm tra.** Codex chạy `docker images`, kiểm tra trạng thái container và gọi lại bốn endpoint trên các container của bài đang chạy. Output trong mục Part 2 lấy từ các lệnh đó.

### Part 4

- **Yêu cầu.** Nhờ Codex thực hiện các bài kiểm tra và điền câu trả lời Part 4.
- **Hỗ trợ.** Codex đọc mã mẫu, giải thích API key, JWT, sliding window và thiết kế cost guard theo tháng bằng Redis.
- **Kiểm tra.** Codex chạy hai app mẫu trên localhost, gọi `curl -i` cho các trường hợp API key, lấy JWT của `student`, gửi 20 request và che token trong báo cáo. Codex cũng kiểm tra riêng nhánh `402` của lớp `CostGuard` với ngân sách thử nghiệm.

### Part 5

- **Yêu cầu.** Nhờ Codex làm Part 5 và ghi kết quả vào `MISSION_ANSWERS.md`.
- **Hỗ trợ.** Codex đối chiếu ví dụ K5, giải thích liveness, readiness, graceful shutdown và cách các replica dùng chung Redis.
- **Kiểm tra.** Codex chạy bản develop trong container Linux, gửi `SIGTERM` khi đang có request, dựng stack ba replica và chạy `test_stateless.py`. Codex kiểm tra thêm history khi dừng một replica và hai endpoint khi Redis mất kết nối.

### Part 6

- **Yêu cầu.** Nhờ Codex hoàn thiện agent Part 6 và xác minh với bộ chấm.
- **Hỗ trợ.** Codex triển khai health, readiness, API key, rate limit và cost guard Redis, log JSON, cấu hình Docker Compose và Railway.
- **Kiểm tra.** Codex chạy nguyên bản script chấm trên Linux với Docker và Redis, xác nhận `PASS 12/12`, rồi kiểm tra thêm các request đồng thời bằng Docker Compose.

### Part 3

- **Yêu cầu.** Nhờ Codex làm Part 3 và triển khai agent Part 6.
- **Hỗ trợ.** Codex đối chiếu cấu hình Railway và Blueprint Render, đọc pipeline Cloud Run, chuẩn bị quy trình kiểm tra endpoint và mở phiên xác nhận Railway CLI.
- **Kiểm tra.** Codex xác minh hạn chế workspace Railway, đối chiếu nhánh GitHub với mã Part 6, tạo Render Web Service và Key Value gói Free, xác nhận đúng commit đang Live, kiểm tra bốn phản hồi HTTPS và chụp ảnh bằng chứng.

### Part 1

- **Yêu cầu.** Nhờ Codex hoàn tất câu trả lời Part 1.
- **Hỗ trợ và kiểm tra.** Codex đọc hai bản mẫu, chạy chúng trên loopback, kiểm tra mã phản hồi HTTP và điền bảng so sánh từ kết quả thực tế.

### Part 7

- **Yêu cầu.** Nhờ Codex hoàn tất benchmark, eval và observability của Day 14.
- **Hỗ trợ.** Codex thêm histogram chiều dài câu hỏi, bổ sung mục JWT và HPA trong knowledge base bản develop, sửa đường dẫn gói Python để image observability chạy được và soạn báo cáo từ số đo.
- **Kiểm tra.** Codex chạy ba lần eval trên golden dataset gốc, bảy lần load test, hai benchmark Locust, kiểm tra quy tắc Prometheus, đối chiếu log với Jaeger và chụp bốn ảnh Part 7. Lần đo ba replica bị gián đoạn đã được chạy lại đủ thời lượng.
