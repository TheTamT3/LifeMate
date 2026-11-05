"""Small, source-verified clarifications for model-facing tool descriptions."""

_NOTES = {
    "food_delivery.order_history": "Runtime hiện tại không áp dụng limit; cần xét toàn bộ đơn trả về, không suy ra chỉ có limit đơn.",
    "bill_payment.schedule_autopay": "Công cụ này cấu hình tự động thanh toán; không thanh toán hóa đơn hiện tại.",
    "ride_hailing.get_quotes": "Công cụ này chỉ lấy báo giá; chưa đặt chuyến xe.",
    "ride_hailing.get_ride": "Không truyền ride_id thì công cụ trả chuyến hiện tại; truyền ride_id thì tra chính xác chuyến đó. Đối chiếu kết quả với yêu cầu trước khi hủy; không tự hủy chuyến hiện tại.",
    "bill_payment.pay": "Công cụ thanh toán toàn bộ hóa đơn từ một source. Không có tham số thanh toán một phần hoặc chia hóa đơn giữa nhiều source trong một lần gọi.",
    "calendar.update_event": (
        "Cập nhật sự kiện không tự khôi phục sự kiện đã bị hủy. Công cụ chỉ cập nhật các trường được truyền vào. "
        "Nếu bỏ end, giờ kết thúc cũ được giữ nguyên, không tự dời theo start. Khi người dùng yêu cầu giữ thời lượng "
        "và lịch cũ đã biết, tính cả start và end phù hợp."
    ),
    "home_security.list_alerts": "Tham số since là cận dưới: kết quả gồm cảnh báo tại hoặc sau thời điểm này.",
    "package_tracking.track": "Có tracking_id thì tra chính xác vận đơn đó; bỏ tham số thì trả danh sách vận đơn.",
    "smart_home.climate_set": "temperature là optional; nếu bỏ qua, runtime giữ nhiệt độ hiện tại. mode vẫn là tham số bắt buộc.",
    "tasks.add": "Nếu bỏ priority, runtime dùng mức normal.",
}


def tool_semantics_note(name: str) -> str:
    """Return a verified semantic note for an official catalog tool name."""
    return _NOTES.get(name, "")
