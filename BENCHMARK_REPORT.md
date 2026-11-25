# Benchmark & Observability Report — Day 14

**Họ tên** Phan Nhật Trường

**Ngày chạy** 25/11/2026 (GMT+7)

**Môi trường** Windows, Python 3.11 và Docker Desktop với 16 CPU logic, 7.62 GiB RAM. Máy dùng Intel Core i5-12500H. Agent develop chạy trên loopback và stack production dùng mạng bridge của Docker Compose.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
| --- | --- | --- |
| p95 latency của /ask | ≤ 500 ms | Giữ độ trễ của phần lớn request dưới nửa giây trong bài load test local. |
| Error rate của /ask | ≤ 2% | Dùng ngưỡng lỗi mặc định của load test để phát hiện suy giảm. |
| Accuracy trên golden dataset | ≥ 85% cho CI, 100% cho bản sửa lab | Gate CI chặn bản chất lượng thấp. Bản sửa phải đúng đủ 23 câu và giữ các câu từng đúng. |

### 1.1 · Metrics của Exercise 7.1

- Counter http_requests_total tăng sau mỗi request. Sau lần gọi thử, series POST /ask với status 200 có giá trị 1.
- Gauge agent_in_flight_requests tăng giảm theo số request đang xử lý. Mẫu đọc sau khi request kết thúc có giá trị 0.
- Histogram agent_question_length_chars ghi phân bố chiều dài câu hỏi qua các bucket 20, 50, 100, 200, 500, 1000 và 2000. Một câu dài 40 ký tự cho count = 1 và sum = 40.

Middleware dùng template như /ask làm label route và gom URL không khớp vào unmatched. Nếu gắn từng URL thật vào label, mỗi URL lạ có thể tạo series riêng, làm tăng RAM, dung lượng và chi phí truy vấn.

## 2. Benchmark hiệu năng (develop, load_test.py)

### 2.1 · Concurrency và latency

Mỗi lần gửi 300 request với agent v2, model mock-llm-small, MOCK_SLOW_RATE=0.03 và MOCK_ERROR_RATE=0.01.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4.29 | 203.0 | 235.7 | 1,710.3 | 0.33% | PASS |
| 10 | 43.91 | 198.3 | 235.9 | 1,688.0 | 1.33% | PASS |
| 50 | 96.80 | 225.6 | 313.9 | 1,739.3 | 1.00% | PASS |
| 100 | 115.29 | 311.6 | 574.3 | 1,794.8 | 0.33% | FAIL |

RPS tăng từ 4.29 lên 43.91 khi tăng từ 1 lên 10 request đồng thời. Khi tăng từ 50 lên 100, RPS tăng từ 96.80 lên 115.29, còn p95 vượt SLO ở mức 100. Nhiều request phải chia sẻ tài nguyên của cùng một process. [Các report tải](reports/)

### 2.2 · Tail latency

Cả ba lần dùng concurrency 20 và 300 request. Agent v2 được khởi động lại sau mỗi thay đổi MOCK_SLOW_RATE.

| MOCK_SLOW_RATE | avg (ms) | p95 (ms) | p99 (ms) |
| ---: | ---: | ---: | ---: |
| 0 | 194.1 | 233.0 | 247.2 |
| 0.03 | 224.5 | 238.9 | 1,657.2 |
| 0.1 | 329.7 | 1,696.7 | 1,727.3 |

Khi slow rate tăng từ 0 lên 0.03, p99 tăng từ 247.2 lên 1,657.2 ms. Ở slow rate 0.1, nhóm request chậm đủ lớn để kéo cả p95 lên. Trung bình pha trộn hai nhóm nhanh và chậm. Percentile cho biết rõ hơn trải nghiệm ở đuôi phân bố. [Các report tail latency](reports/)

## 3. Benchmark chất lượng (develop, eval/run_eval.py)

Ba lần eval giữ nguyên golden dataset và tắt lỗi upstream cùng độ trễ chậm ngẫu nhiên để đo chất lượng câu trả lời.

| Chỉ số | Agent v1 | Agent v2 trước sửa | Agent v2 sau sửa |
| --- | ---: | ---: | ---: |
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 56.4 | 109.1 | 114.0 |
| Latency p95 (ms) | 286.5 | 232.4 | 238.1 |
| Tổng cost (USD) | 0.000394 | 0.000762 | 0.000793 |
| Cost / câu đúng (USD) | 0.00039435 | 0.00003627 | 0.00003449 |
| Quality gate | FAIL (≥ 80%) | PASS (≥ 80%) | PASS (≥ 100%) |

| ID sai trước khi sửa | Keyword thiếu | Thay đổi trong knowledge base |
| --- | --- | --- |
| security-02 | token, hết hạn, chữ ký | Thêm mục JWT. Mô tả token có chữ ký và thời điểm hết hạn. |
| scaling-03 | cpu, memory, custom metrics | Thêm mục Kubernetes HPA. Mô tả scale pod theo CPU, memory hoặc custom metrics. |

Retrieval thêm context nên v2 dùng nhiều token hơn trên mỗi câu. Bản sửa trả lời đúng 23/23, giữ toàn bộ câu từng đúng và có chi phí trên mỗi câu đúng thấp hơn v2 trước sửa. Các lần eval có jitter và chi phí startup client, nên cần lặp lại phép đo để đánh giá chênh lệch latency nhỏ. [Eval v1](reports/eval_v1.json) · [Eval v2](reports/eval_v2.json) · [Eval sau sửa](reports/eval_v2_fixed.json)

**CI.** Chạy agent v2 với MOCK_ERROR_RATE=0, chờ GET /health trả 200 rồi chạy python eval/run_eval.py --min-accuracy 0.85 --baseline reports/eval_v2_fixed.json. Cấu hình job thành required status check. Exit code 1 khi accuracy dưới ngưỡng hoặc xuất hiện regression làm job fail và ngăn merge.

## 4. Observability stack (production)

### 4.1 · Dashboard và metrics

- [Grafana khi Locust đang tạo tải](screenshots/grafana-dashboard.png)
- [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [Trace HTTP 503 có event exception](screenshots/jaeger-error-trace.png)
- [Hai alert cùng firing trong Prometheus](screenshots/prometheus-alert-firing.png)

- Với Locust 30 users, ramp 5 users/giây, Prometheus đo p95 khoảng **293.8 ms**, avg **236.2 ms** và p95 LLM **198.2 ms**. Khoảng cách giữa avg và p95 phản ánh độ trễ cao hơn ở cuối phân bố.
- Hai replica đều nhận tải. 172.20.0.6:8000 đạt 9.04 req/s, 172.20.0.8:8000 đạt 9.00 req/s. Lưu lượng gần nhau trong cửa sổ đo.
- Input đạt **1,308.3 token/s** và output đạt **696.4 token/s**. Input gồm câu hỏi và context retrieval, còn output là câu trả lời của mock.
- GET /metrics qua Nginx trả **404**. Prometheus scrape từng agent ở cổng 8000 qua mạng nội bộ.

### 4.2 · Thí nghiệm lỗi

promtool test rules trên alert_rules_test.yml báo SUCCESS. Thời gian được đo từ lúc áp dụng thay đổi đến lần đầu API báo firing, với chu kỳ poll 2 giây.

| Thí nghiệm | Thay đổi | Alert firing | Thời gian phát hiện | Panel quan sát |
| --- | --- | --- | ---: | --- |
| A | MOCK_ERROR_RATE=0.20 trên hai agent | AgentHighErrorRate | 83.4 s | Error rate |
| D | Trong lúc A firing, pause k5-day14-observability-agent-1 | AgentInstanceDown | 40.4 s | Instances up |

A yêu cầu tỷ lệ HTTP 5xx của /ask vượt 5% liên tục 1 phút. D xuất hiện sau khi Prometheus không scrape được replica trong 30 giây. Tên agent bị pause vẫn được Docker DNS phân giải. Cả hai alert được quan sát cùng lúc. [Ảnh trang Alerts](screenshots/prometheus-alert-firing.png)

Chất lượng khi chuyển về v1 có thể suy giảm trong lúc các metric hạ tầng bình thường. Dùng golden dataset, chạy quality gate trước khi deploy và theo dõi accuracy trên bộ câu hỏi đại diện để phát hiện.

### 4.3 · Debug bằng trace

- Trace chậm **c5b4bed86488fcf42caa9b287cd9ca23** có tổng thời gian 1,743.52 ms. Span con chat mock-llm-small mất **1,714.44 ms** (98.3%), còn retrieval mất 25.75 ms.
- Trace lỗi **3afd9b670577a2fd8ab25bd2b0468850** có POST /ask trả HTTP 503. Span chat mock-llm-small ghi event exception với kiểu utils.mock_llm.LLMError và thông báo Upstream LLM error: 503 Service Unavailable (mock).

Hai dòng log JSON sau lấy từ agent và khớp với trace_id đã tra trong Jaeger. [Jaeger Query API v3](https://www.jaegertracing.io/docs/2.23/architecture/apis/)

```json
{"ts": "2026-11-25T10:55:15.389387+00:00", "level": "INFO", "service": "observable-agent", "instance": "4b9a44fe6106", "event": "llm_call", "trace_id": "c5b4bed86488fcf42caa9b287cd9ca23", "span_id": "682a8b466365a069", "request_id": "31bd6435112c", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1690.5}
{"ts": "2026-11-25T10:55:14.980492+00:00", "level": "INFO", "service": "observable-agent", "instance": "4b9a44fe6106", "event": "llm_error", "trace_id": "3afd9b670577a2fd8ab25bd2b0468850", "span_id": "336b92e032100404", "request_id": "108a46d79f54", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, Locust headless)

Mỗi cấu hình chạy 100 users, ramp 10 users/giây, trong 2 phút. Số liệu lấy từ dòng POST /ask của Locust. Hai lần đều giữ MOCK_ERROR_RATE=0.01 và MOCK_SLOW_RATE=0.03. Dữ liệu ba replica được lấy từ lần chạy lại đủ hai phút sau khi lần đo đầu bị gián đoạn.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 59.82 | 190.0 | 260.0 | 1,700.0 | 59 / 7118 |
| 3 | 60.01 | 190.0 | 230.0 | 1,700.0 | 70 / 7134 |

Scale từ một lên ba replica làm RPS thay đổi +0.3% và p95 thay đổi -30.0 ms trong lần đo. Workload phụ thuộc số user, thời gian nghỉ giữa các lượt và độ trễ mock LLM. Trace cho thấy phần lớn thời gian của request chậm nằm trong span LLM. Tăng số replica chia tải giữa các process, trong khi thời gian chờ của từng lời gọi mô phỏng vẫn phụ thuộc cấu hình mock. [CSV một replica](benchmark-results/scale_1_stats.csv) · [CSV ba replica](benchmark-results/scale_3_stats.csv)

## 6. Kết luận

1. Đọc RPS cùng p95 và p99. Throughput có thể tăng ngay cả khi tail latency vượt SLO.
2. Theo dõi accuracy và chi phí trên câu đúng để đánh giá tác động của retrieval.
3. Dùng metrics để tìm thời điểm xảy ra sự cố, trace để xác định bước chậm và log cùng trace_id để đối chiếu.

Khi triển khai thực tế, có thể bổ sung synthetic check qua Nginx để quan sát tỷ lệ lỗi phía client, theo dõi chi phí theo model và đặt alert theo tốc độ tiêu error budget.
