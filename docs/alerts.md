# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: HighLatencyP95
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Latency P95 của `response_sent.latency_ms` <= 3000ms
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2500ms` trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng nhận câu trả lời chậm, trải nghiệm hội thoại bị gián đoạn.
- Ba bước kiểm tra đầu tiên:
  1. Mở Panel Latency trên dashboard để xác nhận P50/P95/P99 và TTFT.
  2. Lọc `data/logs.jsonl` tìm correlation ID có `latency_ms` cao nhất.
  3. Mở Trace trên Langfuse bằng `correlation_id` đó để xem span nào (retrieval hay generation) bị chậm.
- Mitigation tạm thời: Rollback prompt về version trước nếu do prompt mới, hoặc khởi động lại vector store nếu retrieval bị nghẽn.
- Owner: `student-2A20260289`

## Alert 2

- Tên: HighErrorRate
- Severity: critical
- Duration: 3m
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ thành công >= 99.5% (Error rate <= 0.5%)
- Điều kiện và thời gian duy trì: `error_rate > 2%` trong 3 phút
- Ảnh hưởng tới người dùng: Nhiều người dùng nhận lỗi HTTP 500, không nhận được phản hồi.
- Ba bước kiểm tra đầu tiên:
  1. Mở Panel Errors trên dashboard để kiểm tra số lượng lỗi và loại ngoại lệ (`error_type`).
  2. Lọc file `data/logs.jsonl` theo `level: "error"` và sự kiện `request_failed` để xem chi tiết `payload.detail`.
  3. Tìm `correlation_id` của request lỗi và kiểm tra Trace tương ứng trên Langfuse.
- Mitigation tạm thời: Tắt kịch bản lỗi nếu đang bật injection, hoặc chuyển hướng traffic sang cụm dự phòng.
- Owner: `student-2A20260289`

## Alert 3

- Tên: LowRetrievalSuccess
- Severity: critical
- Duration: 3m
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Retrieval success rate >= 90% (theo guardrail trong slo.yaml)
- Điều kiện và thời gian duy trì: `retrieval_success_rate < 90%` trong 3 phút
- Ảnh hưởng tới người dùng: RAG không tìm được tài liệu ngữ cảnh phù hợp, câu trả lời bị fallback hoặc giảm chất lượng.
- Ba bước kiểm tra đầu tiên:
  1. Mở Panel Errors và Panel Quality trên dashboard để kiểm tra retrieval success và quality score.
  2. Lọc `data/logs.jsonl` các dòng `response_sent` có `tool_success: false` hoặc `request_failed` có `tool_name: "retrieval"`.
  3. Xem trace trên Langfuse để kiểm tra span `retrieval` có bị timeout hoặc lỗi kết nối vector store hay không.
- Mitigation tạm thời: Kiểm tra trạng thái vector store, tắt scenario lỗi nếu do diễn tập, hoặc dùng fallback corpus cục bộ.
- Owner: `student-2A20260289`
