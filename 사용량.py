import sys
import os
import psutil

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout

try:
    import clr
    CLR_OK = True
except Exception:
    CLR_OK = False


class GaugeWidget(QWidget):
    def __init__(self, title, unit="°C", color=QColor("#1FA8FF"), bottom_label="사용량"):
        super().__init__()
        self.title = title
        self.unit = unit
        self.color = color
        self.bottom_label = bottom_label

        self.main_value = 0
        self.usage = 0
        self.bottom_value_text = "0%"

        self.setFixedSize(220, 270)

    def set_values(self, main_value, usage, bottom_value_text=None):
        self.main_value = main_value
        self.usage = max(0, min(100, int(usage))) if usage is not None else 0

        if bottom_value_text is None:
            self.bottom_value_text = f"{self.usage}%"
        else:
            self.bottom_value_text = str(bottom_value_text)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        center_x = w / 2
        gauge_y = 125
        radius = 70

        painter.setPen(self.color)
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(0, 10, w, 28, Qt.AlignCenter, self.title)

        rect = QRectF(center_x - radius, gauge_y - radius, radius * 2, radius * 2)

        pen = QPen(QColor("#2A3038"), 15)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 220 * 16, -260 * 16)

        angle = int(260 * (self.usage / 100))
        pen = QPen(self.color, 15)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 220 * 16, -angle * 16)

        painter.setPen(QColor("#F2F2F2"))
        painter.setFont(QFont("Arial", 28, QFont.Bold))
        painter.drawText(0, 105, w, 50, Qt.AlignCenter, str(self.main_value))

        painter.setPen(QColor("#CFCFCF"))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(0, 145, w, 25, Qt.AlignCenter, self.unit)

        painter.setPen(self.color)
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.drawText(0, 218, w, 32, Qt.AlignCenter, self.bottom_value_text)

        painter.setPen(QColor("#BDBDBD"))
        painter.setFont(QFont("Arial", 11))
        painter.drawText(0, 245, w, 22, Qt.AlignCenter, self.bottom_label)


class HardwareMonitor:
    def __init__(self):
        self.computer = None
        self.ok = False

        if not CLR_OK:
            print("pythonnet 설치 안 됨")
            return

        try:
            dll_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LibreHardwareMonitorLib.dll"
            )

            if not os.path.exists(dll_path):
                print("LibreHardwareMonitorLib.dll 파일이 없습니다.")
                return

            clr.AddReference(dll_path)
            from LibreHardwareMonitor import Hardware

            self.computer = Hardware.Computer()
            self.computer.IsGpuEnabled = True
            self.computer.Open()

            self.ok = True
            print("LibreHardwareMonitor 연결 성공")

        except Exception as e:
            print("LibreHardwareMonitor 연결 실패:", e)

    def get_gpu_data(self):
        gpu_temp = 0
        gpu_usage = 0

        if not self.ok or self.computer is None:
            return gpu_temp, gpu_usage

        try:
            for hardware in self.computer.Hardware:
                hardware.Update()

                hardware_type = str(hardware.HardwareType)
                hardware_name = str(hardware.Name)

                is_gpu = (
                    "Gpu" in hardware_type
                    or "GPU" in hardware_name
                    or "Radeon" in hardware_name
                    or "AMD" in hardware_name
                )

                if not is_gpu:
                    continue

                for sensor in hardware.Sensors:
                    sensor_name = str(sensor.Name)
                    sensor_type = str(sensor.SensorType)
                    value = sensor.Value

                    if value is None:
                        continue

                    if sensor_type == "Temperature" and sensor_name == "GPU Core":
                        gpu_temp = int(value)

                    elif sensor_type == "Load" and sensor_name == "GPU Core":
                        gpu_usage = int(value)

        except Exception as e:
            print("GPU 센서 읽기 실패:", e)

        return gpu_temp, gpu_usage

    def close(self):
        if self.computer:
            self.computer.Close()


class SystemMonitor(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("System Monitor")
        self.setFixedSize(780, 390)

        self.hw = HardwareMonitor()
        self.net_before = psutil.net_io_counters()

        self.setStyleSheet("""
            QWidget {
                background-color: #0B1117;
                color: white;
            }
            QLabel {
                color: #DDDDDD;
            }
        """)

        self.cpu_gauge = GaugeWidget("CPU", "°C", QColor("#1FA8FF"), "사용량")
        self.gpu_gauge = GaugeWidget("GPU", "°C", QColor("#43D95B"), "사용량")
        self.net_gauge = GaugeWidget("Network", "Mbps DOWN", QColor("#FF4FD8"), "Mbps UP")

        title = QLabel("⌁  System Monitor")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("padding-left: 28px; padding-top: 16px; color: #F2F2F2;")
        title.setFixedHeight(65)

        gauge_layout = QHBoxLayout()
        gauge_layout.setContentsMargins(20, 0, 20, 0)
        gauge_layout.setSpacing(18)
        gauge_layout.addWidget(self.cpu_gauge)
        gauge_layout.addWidget(self.gpu_gauge)
        gauge_layout.addWidget(self.net_gauge)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 5, 8, 8)
        main_layout.setSpacing(0)
        main_layout.addWidget(title)
        main_layout.addLayout(gauge_layout)

        self.setLayout(main_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

        self.update_data()

    def get_network_speed(self):
        net_now = psutil.net_io_counters()

        down_bytes = net_now.bytes_recv - self.net_before.bytes_recv
        up_bytes = net_now.bytes_sent - self.net_before.bytes_sent

        self.net_before = net_now

        down_mbps = (down_bytes * 8) / 1_000_000
        up_mbps = (up_bytes * 8) / 1_000_000

        return round(down_mbps, 1), round(up_mbps, 1)

    def update_data(self):
        cpu_usage = int(psutil.cpu_percent(interval=None))
        cpu_temp = 0

        gpu_temp, gpu_usage = self.hw.get_gpu_data()

        down_speed, up_speed = self.get_network_speed()

        # 네트워크 게이지는 100Mbps 기준
        network_percent = int((down_speed / 100) * 100)

        self.cpu_gauge.set_values(cpu_temp, cpu_usage, f"{cpu_usage}%")
        self.gpu_gauge.set_values(gpu_temp, gpu_usage, f"{gpu_usage}%")
        self.net_gauge.set_values(down_speed, network_percent, f"{up_speed} Mbps")

    def closeEvent(self, event):
        self.hw.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SystemMonitor()
    window.show()
    sys.exit(app.exec())