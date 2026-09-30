# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Gia Khánh
- **MSSV:** 2A20260289
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/khanhtg205/K4-L3-DAY13-TranGiaKhanh-2A202602689-Monitoring-LLMOps
- **Commit SHA cuối:** 8ead907
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A20260289`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 20/100 | 100/100 | Đạt tuyệt đối: JSON schema, Correlation ID, context enrichment, PII scrubbing |
| `validate_dashboard.py` | 6/6 | 6/6 | Hợp lệ toàn bộ 6/6 panel theo contract chuẩn |
| `pytest` | 22 passed | 22 passed | 100% test cases thành công |
| Số traces hợp lệ | 0 | 24 | Vượt yêu cầu tối thiểu >= 10 traces |
| Số PII leak | 0 | 0 | Không còn rò rỉ PII nguyên văn |
| Latency P95 / TTFT P95 | ~160ms / 50ms | ~160ms / 50ms | Đoạn baseline bình thường ổn định |
| Retrieval success rate | 100% | 100% | Tool retrieval hoạt động tốt ở baseline |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Nhận qua request header `x-request-id` trong `CorrelationIdMiddleware`; nếu client không gửi, middleware tự sinh mới theo định dạng `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`). Sau đó gán vào `structlog.contextvars` và trả ngược lại client qua hai header `x-request-id` và `x-correlation-id` kèm `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `user_id_hash` (băm SHA256 rút gọn từ `user_id`), `session_id`, `feature`, `model`, `env`, `service`, `event`, `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Xây dựng hàm `_scrub_value` duyệt đệ quy mọi trường chuỗi trong `event_dict`, áp dụng bộ regex lọc email, số điện thoại Việt Nam (+84, 09x, 03x...), CCCD (12 số), thẻ thanh toán (16 số), passport và thay bằng `[REDACTED_...]`. Đăng ký processor `scrub_event` trong `structlog` trước bước ghi file (`JsonlFileProcessor`) và render JSON.
- **Cách kiểm chứng kết quả:** Chạy script `python scripts/validate_logs.py` đạt điểm 100/100, kiểm tra trực tiếp file `data/logs.jsonl` không còn thông tin PII thô.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Toàn bộ trace được gửi về project Langfuse Cloud `day13-k4-l3b-2A20260289` thông qua API key cá nhân được cấu hình trong file `.env`.
- **Cấu trúc root/retrieval/generation observations:** Root observation là `lab-agent-run` (type `agent`), bên dưới gồm hai child observations: `retrieval` (type `retriever` đo thời gian và doc_count) và `generation` (type `generation` ghi nhận model, input/output tokens, cost chi tiết).
- **Cách nối trace với log:** Truyền `correlation_id` từ `request.state.correlation_id` vào `metadata={"correlation_id": correlation_id}` của root observation khi gọi `propagate_attributes()`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 / Label `baseline`
- **Version/label candidate:** Version 2 / Label `candidate`
- **Trace ID của mỗi version:**
  - Baseline v1: `282c8e93906f21bab587fb80ed1e838e` (correlation_id: `req-2f4201ca`)
  - Candidate v2 (Promote production): `80cea3c85e797b70e2c06d41e585cb46` (correlation_id: `req-04515dd2`)
  - Rollback v1 (Production): `7b634e40d3ad750fb98d878ebe7ae374` (correlation_id: `req-cd5d170d`)
- **Cách promote và rollback `production`:**
  - Khởi tạo prompt `day13-chat` v1 với label `baseline` và `production`, tạo v2 với label `candidate`.
  - Promote: Chuyển nhãn `production` từ v1 sang v2 trên Langfuse UI (hoặc `client.update_prompt(name='day13-chat', version=2, new_labels=['candidate', 'production'])`).
  - Rollback: Khi phát hiện sự cố, chuyển nhãn `production` từ v2 quay trở lại v1 (`client.update_prompt(name='day13-chat', version=1, new_labels=['baseline', 'production'])`).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng đúng 6 panel theo `config/dashboard.yaml`: Latency (P50/P95/P99, TTFT), Traffic (Request count), Errors (Error rate, Retrieval success), Cost (USD), Tokens (Tokens In/Out), Quality (Quality score proxy).
- **SLO và lý do chọn:** `99.5% request hoàn thành thành công và có latency <= 3000ms trong chu kỳ 28 ngày`. Lý do: Đảm bảo độ trễ trải nghiệm hội thoại tương tác cho người dùng cuối mà vẫn chừa ngưỡng an toàn cho luồng RAG và LLM generation.
- **Cách tính error budget:** SLO 99.5% trong 28 ngày nghĩa là error budget là 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép không đạt tiêu chuẩn (chậm hơn 3000ms hoặc bị lỗi).
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning, 5m): Kích hoạt khi `p95(latency_ms) > 2500ms` trong 5 phút. Runbook tại `docs/alerts.md#alert-1`.
  2. `HighErrorRate` (Critical, 3m): Kích hoạt khi `error_rate > 2%` trong 3 phút. Runbook tại `docs/alerts.md#alert-2`.
  3. `LowRetrievalSuccess` (Critical, 3m): Kích hoạt khi `retrieval_success_rate < 90%` trong 3 phút. Runbook tại `docs/alerts.md#alert-3`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 15:01:40 – 15:02:10 (08:01:40Z – 08:02:10Z, 30/09/2026)
- **Triệu chứng từ metrics:** Panel Latency ghi nhận Latency P99 nhảy vọt lên 3,934ms và P95 đạt 2,655ms (vượt ngưỡng cảnh báo 2,500ms của Alert `HighLatencyP95` và vi phạm ngưỡng SLO latency 3,000ms). Trong khi đó, Error rate vẫn bằng 0% và TTFT P95 ổn định ở mức 50ms.
- **Log line và correlation ID liên quan:**
  - Log kích hoạt sự cố: `{"event": "incident_enabled", "payload": {"name": "rag_slow"}, "level": "warning"}`
  - Log request đại diện bị ảnh hưởng: Event `response_sent` có `correlation_id="req-95fcb652"`, ghi nhận `latency_ms=3934`, `ttft_ms=50`, `feature="monitoring"`, `tool_name="retrieval"`, `tool_success=true` tại timestamp `2026-09-30T08:01:46.749726Z`.
- **Trace ID và span gây ảnh hưởng:**
  - Trace ID: `8b9d69c77b1c84a8d1321ba6a0fbaccd` (Session: `k4-l3b-challenge-s01`)
  - Cây waterfall bóc tách rõ: Span `retrieval` (type `RETRIEVER`) tốn **2.501s** (chiếm phần lớn thời gian trễ), trong khi span `generation` (type `GENERATION`) chỉ tốn **0.153s**. Tương tự cho các session s02–s05, span `retrieval` đều chậm cố định ~2.502s.
- **Root cause:** Thành phần Retrieval (Vector Store) bị nghẽn và phát sinh độ trễ 2.5s (do kịch bản sự cố `rag_slow`), dẫn đến tổng thời gian xử lý toàn request bị kéo dài vượt mức cam kết SLO. Model sinh câu trả lời LLM hoàn toàn bình thường (chỉ mất ~0.15s).
- **Fix action:** Thực hiện tắt sự cố thông qua lệnh `python scripts/inject_incident.py --disable` (hoặc gọi API `/incidents/rag_slow/disable`), kiểm tra lại kết nối và tài nguyên của dịch vụ Vector Database.
- **Preventive measure:**
  1. Kích hoạt cảnh báo `HighLatencyP95` (duration 5m) qua Slack `#k4-l3b-alerts` để phát hiện ngay khi tail latency vượt 2,500ms.
  2. Bổ sung cơ chế Timeout (ví dụ: giới hạn 800ms) cho hàm `retrieve()` kèm circuit breaker hoặc fallback trả về tài liệu cache/cục bộ để không chặn luồng LLM khi database bị nghẽn.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Quyết định phân cấp trace thành các child observation riêng biệt (`retrieval` kiểu retriever và `generation` kiểu generation). Lý do: Nếu gom chung vào root observation `lab-agent-run`, khi hệ thống bị chậm ta sẽ không thể biết độ trễ nằm ở cơ sở dữ liệu vector hay do mô hình LLM.
- **Một lỗi/blocker đã gặp:** Khi chạy validator log ban đầu, các bản ghi log cũ chưa redact PII vẫn nằm trong file `data/logs.jsonl` khiến điểm validator bị trừ.
- **Cách tìm nguyên nhân và xử lý:** Lưu kết quả baseline làm minh chứng, sau đó dọn dẹp file log cũ và cho tải chạy lại trên nền pipeline structlog đã tích hợp bộ lọc `scrub_event`, đưa điểm validator lên 100/100 tuyệt đối.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics đóng vai trò "triệu chứng bệnh" giúp nhận biết vấn đề và khung giờ xảy ra; Logs là "hồ sơ bệnh án" giúp lọc ra đúng mã định danh request (`correlation_id`) bị ảnh hưởng; Traces là "kết quả chụp phim" mổ xẻ cây thực thi để định vị chính xác span gây lỗi hoặc chậm trễ.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt ảnh hưởng trực tiếp đến chất lượng và tài nguyên; việc quản lý prompt theo version/label cho phép đội ngũ thực hiện rollback tức thời về bản ổn định khi bản mới gây hồi quy (regression) mà không phải can thiệp sửa code hay triển khai lại server.
- **Điều quan trọng nhất đã học:** Nắm vững tư duy vận hành hệ thống AI có khả năng quan sát toàn diện (Full Observability), bảo vệ dữ liệu người dùng (PII scrubbing) và phương pháp xử lý sự cố dựa trên chuỗi bằng chứng có thể kiểm chứng.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Các thành phần LLM và RAG hiện đang mô phỏng cục bộ; trong tương lai có thể mở rộng sang LLM gateway thực tế và tích hợp OpenTelemetry collector tập trung.

## 9. Checklist trước khi nộp

- [ x ] Kết quả và evidence thuộc commit SHA cuối.
- [ x ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ x ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ x ] Incident evidence nối đúng metric → log → trace.
- [ x ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ x ] Repository chạy lại được theo README.
- [ x ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ x ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
